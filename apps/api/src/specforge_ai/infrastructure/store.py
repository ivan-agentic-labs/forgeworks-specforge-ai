from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from specforge_ai.domain.explicit_endpoints import EndpointDeclarationError, explicit_paths
from specforge_ai.domain.openapi_semantics import canonical_json, sha256_json, validate_generated_openapi

TENANT = "00000000-0000-0000-0000-000000000001"
USER = "00000000-0000-0000-0000-000000000010"
_NAMESPACE = uuid.UUID("5d4e5d6e-2b3e-4d7b-a4d0-0b1f9b0a1d10")


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _uuid(value: str) -> str:
    return str(uuid.UUID(value))


class Store:
    """SQLite adapter used for the disposable MVP and deterministic test harness.

    All state transitions are explicit and persisted.  The production PostgreSQL
    adapter remains a separate G2/G4 item; this store never contacts a provider.
    """

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def conn(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def init(self) -> None:
        with self.lock, self.conn() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY, slug TEXT, status TEXT);
                CREATE TABLE IF NOT EXISTS memberships(tenant_id TEXT, user_id TEXT, role TEXT, status TEXT, PRIMARY KEY(tenant_id,user_id));
                CREATE TABLE IF NOT EXISTS sets_(tenant_id TEXT, id TEXT, title TEXT, source_version INTEGER, source_digest TEXT, owner_id TEXT, status TEXT, version INTEGER, PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS requirements(tenant_id TEXT, id TEXT, set_id TEXT, statement TEXT, source_span TEXT, req_type TEXT, provenance_digest TEXT, PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS ambiguities(tenant_id TEXT, id TEXT, requirement_id TEXT, severity TEXT, question TEXT, status TEXT, version INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS decisions(tenant_id TEXT, id TEXT, ambiguity_id TEXT, actor_id TEXT, decision_hash TEXT, source_reference TEXT, decision_text TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS revisions(tenant_id TEXT, id TEXT, set_id TEXT, source_version INTEGER, source_digest TEXT NOT NULL DEFAULT '', status TEXT, spec_json TEXT, spec_sha TEXT, version INTEGER, source_decision_digest TEXT NOT NULL DEFAULT '', validator_report_json TEXT NOT NULL DEFAULT '{}', validator_report_sha TEXT NOT NULL DEFAULT '', traceability_report_json TEXT NOT NULL DEFAULT '{}', traceability_report_sha TEXT NOT NULL DEFAULT '', stale_reason TEXT, created_at TEXT NOT NULL DEFAULT '', approved_at TEXT, approver_id TEXT, PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS acceptance_cases(tenant_id TEXT, id TEXT, revision_id TEXT, requirement_id TEXT, case_key TEXT, description TEXT, status TEXT, PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS jobs(tenant_id TEXT, id TEXT, revision_id TEXT, state TEXT, created_at TEXT, state_version INTEGER NOT NULL DEFAULT 1, attempt_count INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3, next_attempt_at TEXT, last_error_code TEXT, last_error_message TEXT, updated_at TEXT NOT NULL DEFAULT '', PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS artifacts(tenant_id TEXT, id TEXT, kind TEXT, filename TEXT, declared_media_type TEXT, sha256 TEXT, size_bytes INTEGER, status TEXT, object_generation TEXT, created_at TEXT, expires_at TEXT, rejected_reason TEXT, PRIMARY KEY(tenant_id,id));
                CREATE TABLE IF NOT EXISTS idempotency_records(tenant_id TEXT, key TEXT, request_hash TEXT, response_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(tenant_id,key));
                """
            )
            self._ensure_columns(db, "ambiguities", {"version": "INTEGER NOT NULL DEFAULT 1"})
            self._ensure_columns(db, "decisions", {"decision_text": "TEXT NOT NULL DEFAULT ''", "version": "INTEGER NOT NULL DEFAULT 1", "created_at": "TEXT NOT NULL DEFAULT ''"})
            self._ensure_columns(db, "revisions", {
                "source_digest": "TEXT NOT NULL DEFAULT ''", "source_decision_digest": "TEXT NOT NULL DEFAULT ''", "validator_report_json": "TEXT NOT NULL DEFAULT '{}'",
                "validator_report_sha": "TEXT NOT NULL DEFAULT ''", "traceability_report_json": "TEXT NOT NULL DEFAULT '{}'",
                "traceability_report_sha": "TEXT NOT NULL DEFAULT ''", "stale_reason": "TEXT", "created_at": "TEXT NOT NULL DEFAULT ''",
                "approved_at": "TEXT", "approver_id": "TEXT",
            })
            self._ensure_columns(db, "jobs", {
                "state_version": "INTEGER NOT NULL DEFAULT 1", "attempt_count": "INTEGER NOT NULL DEFAULT 0",
                "max_attempts": "INTEGER NOT NULL DEFAULT 3", "next_attempt_at": "TEXT", "last_error_code": "TEXT",
                "last_error_message": "TEXT", "updated_at": "TEXT NOT NULL DEFAULT ''",
            })

    @staticmethod
    def _ensure_columns(db: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def seed(self) -> None:
        with self.lock, self.conn() as db:
            db.execute("INSERT OR IGNORE INTO tenants VALUES(?,?,?)", (TENANT, "synthetic-demo", "ACTIVE"))
            db.execute("INSERT OR IGNORE INTO memberships VALUES(?,?,?,?)", (TENANT, USER, "editor", "ACTIVE"))

    def member_role(self, tenant: str, user: str) -> str | None:
        """Read current ACTIVE member role without trusting JWT-supplied role."""
        with self.conn() as db:
            row = db.execute(
                "SELECT role FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'",
                (tenant, user),
            ).fetchone()
            return str(row["role"]) if row else None

    def member(self, tenant_id: str, user_id: str) -> bool:
        with self.conn() as db:
            return db.execute("SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'", (tenant_id, user_id)).fetchone() is not None

    def create_set(self, tenant_id: str, title: str, digest: str, owner: str, source_text: str | None = None) -> sqlite3.Row:
        set_id = str(uuid.uuid4())
        statements = []
        source = source_text if source_text is not None else f"Implement {title}\nTBD: What is the success response shape?"
        for line_number, line in enumerate(source.splitlines(), 1):
            statement = line.strip().lstrip("-* ").strip()
            if statement:
                statements.append((line_number, statement))
        if len(statements) > 100 or any(len(statement) > 2000 for _, statement in statements):
            raise ValueError("SOURCE_REQUIREMENT_LIMIT_EXCEEDED")
        if not statements:
            raise ValueError("SOURCE_HAS_NO_REQUIREMENTS")
        with self.lock, self.conn() as db:
            db.execute("INSERT INTO sets_ VALUES(?,?,?,?,?,?,?,?)", (tenant_id, set_id, title, 1, digest, owner, "OPEN", 1))
            for line_number, statement in statements:
                requirement_id = str(uuid.uuid4())
                provenance = hashlib.sha256(f"{digest}:{line_number}:{statement}".encode()).hexdigest()
                db.execute("INSERT INTO requirements VALUES(?,?,?,?,?,?,?)", (tenant_id, requirement_id, set_id, statement, f"source:{line_number}-{line_number}", "functional", provenance))
                if "?" in statement or "tbd" in statement.lower() or "unknown" in statement.lower():
                    ambiguity_id = str(uuid.uuid4())
                    db.execute("INSERT INTO ambiguities(tenant_id,id,requirement_id,severity,question,status,version) VALUES(?,?,?,?,?,?,?)", (tenant_id, ambiguity_id, requirement_id, "HIGH", statement, "OPEN", 1))
        return self.get_set(tenant_id, set_id)

    def get_set(self, tenant_id: str, set_id: str) -> sqlite3.Row | None:
        with self.conn() as db:
            return db.execute("SELECT * FROM sets_ WHERE tenant_id=? AND id=?", (tenant_id, set_id)).fetchone()

    def reqs(self, tenant_id: str, set_id: str) -> list[sqlite3.Row]:
        with self.conn() as db:
            return db.execute("SELECT * FROM requirements WHERE tenant_id=? AND set_id=? ORDER BY id", (tenant_id, set_id)).fetchall()

    def amb(self, tenant_id: str, set_id: str) -> list[sqlite3.Row]:
        with self.conn() as db:
            return db.execute("SELECT a.* FROM ambiguities a JOIN requirements r ON r.id=a.requirement_id AND r.tenant_id=a.tenant_id WHERE a.tenant_id=? AND r.set_id=? ORDER BY a.id", (tenant_id, set_id)).fetchall()

    def _decision_snapshot(self, db: sqlite3.Connection, tenant_id: str, set_id: str) -> str:
        rows = db.execute(
            "SELECT a.id,a.status,a.version,d.decision_hash,d.source_reference,d.version AS decision_version "
            "FROM ambiguities a JOIN requirements r ON r.id=a.requirement_id AND r.tenant_id=a.tenant_id "
            "LEFT JOIN decisions d ON d.tenant_id=a.tenant_id AND d.ambiguity_id=a.id AND d.version=a.version-1 "
            "WHERE a.tenant_id=? AND r.set_id=? ORDER BY a.id", (tenant_id, set_id)
        ).fetchall()
        snapshot = [dict(row) for row in rows]
        return hashlib.sha256(canonical_json(snapshot).encode()).hexdigest()

    def decide(self, tenant_id: str, ambiguity_id: str, actor: str, text: str, source_reference: str, expected_version: int) -> tuple[dict[str, Any] | None, str]:
        decision_id = str(uuid.uuid4())
        with self.lock, self.conn() as db:
            if isinstance(db, sqlite3.Connection):
                db.execute("BEGIN IMMEDIATE")
            ambiguity = db.execute("SELECT * FROM ambiguities WHERE tenant_id=? AND id=?", (tenant_id, ambiguity_id)).fetchone()
            if not ambiguity:
                return None, "NOT_FOUND"
            if ambiguity["version"] != expected_version:
                return dict(ambiguity), "STALE"
            decision_version = int(ambiguity["version"])
            decision_hash = hashlib.sha256(canonical_json({"decision_text": text, "source_reference": source_reference}).encode()).hexdigest()
            changed = db.execute("UPDATE ambiguities SET status='RESOLVED',version=version+1 WHERE tenant_id=? AND id=? AND version=?", (tenant_id, ambiguity_id, expected_version)).rowcount
            if changed != 1:
                return dict(ambiguity), "STALE"
            db.execute("INSERT INTO decisions(tenant_id,id,ambiguity_id,actor_id,decision_hash,source_reference,decision_text,version,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (tenant_id, decision_id, ambiguity_id, actor, decision_hash, source_reference, text, decision_version, now()))
            requirement = db.execute("SELECT set_id FROM requirements WHERE tenant_id=? AND id=?", (tenant_id, ambiguity["requirement_id"])).fetchone()
            if requirement:
                # A decision changes the source snapshot.  Previously generated or approved
                # revisions are no longer publishable and retain an audit reason.
                snapshot = self._decision_snapshot(db, tenant_id, requirement["set_id"])
                db.execute("UPDATE revisions SET status='STALE',stale_reason='STAKEHOLDER_DECISION_CHANGED',version=version+1 WHERE tenant_id=? AND set_id=? AND status IN ('GENERATED','APPROVED','WAITING_APPROVAL') AND source_decision_digest<>?", (tenant_id, requirement["set_id"], snapshot))
                db.execute("UPDATE acceptance_cases SET status='INVALIDATED' WHERE tenant_id=? AND revision_id IN (SELECT id FROM revisions WHERE tenant_id=? AND set_id=? AND status='STALE')", (tenant_id, tenant_id, requirement["set_id"]))
        return {"id": decision_id, "decision_hash": decision_hash, "version": decision_version}, "OK"

    def revision(self, tenant_id: str, set_id: str, source_version: int, profile: str) -> tuple[sqlite3.Row | None, str]:
        with self.lock, self.conn() as db:
            requirement_set = db.execute("SELECT * FROM sets_ WHERE tenant_id=? AND id=?", (tenant_id, set_id)).fetchone()
            if not requirement_set:
                return None, "NOT_FOUND"
            if int(requirement_set["source_version"]) != source_version:
                return None, "SOURCE_VERSION_STALE"
            open_ambiguities = [a for a in self.amb(tenant_id, set_id) if a["status"] == "OPEN" and a["severity"] in {"HIGH", "CRITICAL"}]
            if open_ambiguities:
                return None, "OPEN_AMBIGUITY"
            if profile not in {"openapi31", "openapi31-explicit-v1"}:
                return None, "OUTPUT_PROFILE_UNSUPPORTED"
            requirements = self.reqs(tenant_id, set_id)
            snapshot = self._decision_snapshot(db, tenant_id, set_id)
            revision_id, job_id = str(uuid.uuid4()), str(uuid.uuid4())
            cases: list[tuple[str, str]] = []
            for requirement in requirements:
                case_id = str(uuid.uuid5(_NAMESPACE, f"{tenant_id}:{revision_id}:{requirement['id']}"))
                cases.append((case_id, requirement["id"]))
            paths: dict[str, Any] = {}
            for requirement, (case_id, _) in zip(requirements, cases):
                path = f"/requirements/{requirement['id']}"
                operation_id = f"requirement_{requirement['id'].replace('-', '')[:12]}"
                paths[path] = {
                    "get": {
                        "operationId": operation_id,
                        "summary": requirement["statement"],
                        "x-requirement-id": requirement["id"],
                        "x-acceptance-case-ids": [case_id],
                        "responses": {"200": {"description": "Successful response"}},
                    }
                }
            if profile == "openapi31-explicit-v1":
                try:
                    paths = explicit_paths(requirements, cases)
                except EndpointDeclarationError as error:
                    return None, str(error)
            spec = {
                "openapi": "3.1.0",
                "info": {"title": requirement_set["title"], "version": "0.1.0"},
                "x-deterministic-output": True,
                "x-generator": "specforge-ai.explicit.v1" if profile == "openapi31-explicit-v1" else "specforge-ai.deterministic.v1",
                "x-output-profile": profile,
                "paths": paths,
            }
            report = validate_generated_openapi(spec, [r["id"] for r in requirements], [case[0] for case in cases])
            trace = self._trace_report(requirements, spec, cases, open_ambiguities)
            raw_spec = canonical_json(spec)
            spec_sha = hashlib.sha256(raw_spec.encode()).hexdigest()
            report_sha = sha256_json(report)
            trace_sha = sha256_json(trace)
            created = now()
            db.execute("INSERT INTO revisions(tenant_id,id,set_id,source_version,source_digest,status,spec_json,spec_sha,version,source_decision_digest,validator_report_json,validator_report_sha,traceability_report_json,traceability_report_sha,stale_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id, revision_id, set_id, source_version, requirement_set["source_digest"], "GENERATED" if report["valid"] else "VALIDATION_FAILED", raw_spec, spec_sha, 1, snapshot, canonical_json(report), report_sha, canonical_json(trace), trace_sha, None, created))
            for case_id, requirement_id in cases:
                db.execute("INSERT INTO acceptance_cases VALUES(?,?,?,?,?,?,?)", (tenant_id, case_id, revision_id, requirement_id, f"{revision_id}:{requirement_id}", "Verify the source-declared HTTP operation and response; schema and behavior require stakeholder acceptance." if profile == "openapi31-explicit-v1" else "The generated operation satisfies the source requirement with a successful response.", "PENDING"))
            db.execute("INSERT INTO jobs(tenant_id,id,revision_id,state,created_at,state_version,attempt_count,max_attempts,next_attempt_at,last_error_code,last_error_message,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id, job_id, revision_id, "PENDING", created, 1, 0, 3, created, None, None, created))
        # The deterministic local job is executed after its durable row is committed.
        self.run_job(tenant_id, job_id)
        return self.get_revision(tenant_id, revision_id), "OK"

    @staticmethod
    def _trace_report(requirements: list[sqlite3.Row], spec: dict[str, Any], cases: list[tuple[str, str]], open_ambiguities: list[sqlite3.Row]) -> dict[str, Any]:
        operations = [(path, method, op) for path, item in spec.get("paths", {}).items() for method, op in item.items() if method in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}]
        requirement_ids = {requirement["id"] for requirement in requirements}
        case_ids = {case[0] for case in cases}
        linked: set[str] = set()
        linked_cases: set[str] = set()
        operation_ids: set[str] = set()
        linked_operation_ids: set[str] = set()
        linked_operations = 0
        for _, _, operation in operations:
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if isinstance(operation_id, str):
                operation_ids.add(operation_id)
            requirement_id = operation.get("x-requirement-id")
            if isinstance(requirement_id, str) and requirement_id in requirement_ids:
                linked.add(requirement_id)
                linked_operations += 1
                if isinstance(operation_id, str):
                    linked_operation_ids.add(operation_id)
            case_refs = operation.get("x-acceptance-case-ids", [])
            if isinstance(case_refs, list):
                linked_cases.update(case_id for case_id in case_refs if isinstance(case_id, str) and case_id in case_ids)
        linked_requirement_count = len(linked & requirement_ids)
        linked_case_count = len(linked_cases & case_ids)
        total_operations = len(operations)
        total_requirements = len(requirement_ids)
        total_cases = len(case_ids)
        operation_ratio = linked_operations / total_operations if total_operations else 0.0
        requirement_ratio = linked_requirement_count / total_requirements if total_requirements else 0.0
        return {
            "status": "VERIFIED" if total_operations > 0 and total_requirements > 0 and total_cases > 0 and linked_operations == total_operations and linked == requirement_ids and linked_cases == case_ids and not open_ambiguities else "INCOMPLETE",
            "operation_coverage": {"linked": linked_operations, "total": total_operations, "ratio": operation_ratio},
            "requirement_coverage": {"linked": linked_requirement_count, "total": total_requirements, "ratio": requirement_ratio},
            "total_requirements": total_requirements,
            "linked_requirements": linked_requirement_count,
            "unlinked_operation_ids": sorted(operation_ids - linked_operation_ids),
            "critical_open_ambiguities": len(open_ambiguities),
            "total_acceptance_cases": total_cases,
            "linked_acceptance_cases": linked_case_count,
            "unlinked_acceptance_case_ids": sorted(case_ids - linked_cases),
        }

    def run_job(self, tenant_id: str, job_id: str) -> str:
        with self.lock, self.conn() as db:
            if isinstance(db, sqlite3.Connection):
                db.execute("BEGIN IMMEDIATE")
            job = db.execute("SELECT * FROM jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()
            if not job:
                return "NOT_FOUND"
            if job["state"] not in {"PENDING", "FAILED_RETRYABLE"}:
                return job["state"]
            if job["next_attempt_at"] and job["next_attempt_at"] > now():
                return job["state"]
            if int(job["attempt_count"]) >= int(job["max_attempts"]):
                db.execute("UPDATE jobs SET state='FAILED_TERMINAL',state_version=state_version+1, "
                           "next_attempt_at=NULL,last_error_code='MAX_ATTEMPTS_EXCEEDED', "
                           "last_error_message='Retry budget exhausted',updated_at=? WHERE tenant_id=? AND id=?",
                           (now(), tenant_id, job_id))
                return "FAILED_TERMINAL"
            attempt = int(job["attempt_count"]) + 1
            changed = db.execute("UPDATE jobs SET state='RUNNING',attempt_count=?,state_version=state_version+1,updated_at=? WHERE tenant_id=? AND id=? AND state IN ('PENDING','FAILED_RETRYABLE')", (attempt, now(), tenant_id, job_id)).rowcount
            if changed != 1:
                return db.execute("SELECT state FROM jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()["state"]
            revision = db.execute("SELECT * FROM revisions WHERE tenant_id=? AND id=?", (tenant_id, job["revision_id"])).fetchone()
            if not revision:
                db.execute("UPDATE jobs SET state='FAILED_TERMINAL',state_version=state_version+1,last_error_code='REVISION_NOT_FOUND',updated_at=? WHERE tenant_id=? AND id=?", (now(), tenant_id, job_id))
                return "FAILED_TERMINAL"
            report = json.loads(revision["validator_report_json"] or "{}")
            if not report.get("valid"):
                db.execute("UPDATE jobs SET state='FAILED_TERMINAL',state_version=state_version+1,last_error_code='OPENAPI_SEMANTIC_INVALID',last_error_message=?,updated_at=? WHERE tenant_id=? AND id=?", ("; ".join(report.get("errors", [])), now(), tenant_id, job_id))
                db.execute("UPDATE revisions SET status='VALIDATION_FAILED' WHERE tenant_id=? AND id=?", (tenant_id, revision["id"]))
                return "FAILED_TERMINAL"
            db.execute("UPDATE jobs SET state='SUCCEEDED',state_version=state_version+1,next_attempt_at=NULL,updated_at=? WHERE tenant_id=? AND id=?", (now(), tenant_id, job_id))
            return "SUCCEEDED"

    def record_job_failure(self, tenant_id: str, job_id: str, error_code: str, message: str, retryable: bool = True) -> str:
        """Persist one worker failure; backoff and terminal transition are durable."""
        with self.lock, self.conn() as db:
            job = db.execute("SELECT * FROM jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()
            if not job:
                return "NOT_FOUND"
            if job["state"] in {"SUCCEEDED", "FAILED_TERMINAL", "CANCELLED"}:
                return job["state"]
            attempt = int(job["attempt_count"])
            terminal = not retryable or attempt >= int(job["max_attempts"])
            state = "FAILED_TERMINAL" if terminal else "FAILED_RETRYABLE"
            next_at = None if terminal else (datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** max(attempt, 0)))).isoformat().replace("+00:00", "Z")
            db.execute("UPDATE jobs SET state=?,state_version=state_version+1,next_attempt_at=?,last_error_code=?,last_error_message=?,updated_at=? WHERE tenant_id=? AND id=?", (state, next_at, error_code, message, now(), tenant_id, job_id))
            return state

    def get_revision(self, tenant_id: str, revision_id: str) -> sqlite3.Row | None:
        with self.conn() as db:
            return db.execute("SELECT * FROM revisions WHERE tenant_id=? AND id=?", (tenant_id, revision_id)).fetchone()

    def trace(self, tenant_id: str, revision_id: str) -> dict[str, Any] | None:
        revision = self.get_revision(tenant_id, revision_id)
        if not revision:
            return None
        with self.conn() as db:
            cases = db.execute("SELECT id,requirement_id FROM acceptance_cases WHERE tenant_id=? AND revision_id=? ORDER BY id", (tenant_id, revision_id)).fetchall()
            requirements = db.execute("SELECT * FROM requirements WHERE tenant_id=? AND set_id=? ORDER BY id", (tenant_id, revision["set_id"])).fetchall()
            ambiguities = [a for a in self.amb(tenant_id, revision["set_id"]) if a["status"] == "OPEN" and a["severity"] in {"HIGH", "CRITICAL"}]
        stored = json.loads(revision["traceability_report_json"] or "{}")
        spec = json.loads(revision["spec_json"])
        fresh = self._trace_report(requirements, spec, [(c["id"], c["requirement_id"]) for c in cases], ambiguities)
        fresh["status"] = "VERIFIED" if fresh["status"] == "VERIFIED" and revision["status"] == "GENERATED" else ("STALE" if revision["status"] == "STALE" else fresh["status"])
        fresh.update({"id": revision_id, "revision_id": revision_id, "created_at": revision["created_at"] or now()})
        return fresh

    def approve(self, tenant_id: str, revision_id: str, spec_sha: str, expected_version: int, actor: str) -> tuple[sqlite3.Row | None, str]:
        with self.lock, self.conn() as db:
            if isinstance(db, sqlite3.Connection):
                db.execute("BEGIN IMMEDIATE")
            revision = db.execute("SELECT * FROM revisions WHERE tenant_id=? AND id=?", (tenant_id, revision_id)).fetchone()
            if not revision:
                return None, "NOT_FOUND"
            if revision["version"] != expected_version:
                return revision, "STALE"
            if revision["spec_sha"] != spec_sha:
                return revision, "DIGEST_MISMATCH"
            requirement_set = db.execute("SELECT * FROM sets_ WHERE tenant_id=? AND id=?", (tenant_id, revision["set_id"])).fetchone()
            current_snapshot = self._decision_snapshot(db, tenant_id, revision["set_id"])
            if revision["status"] == "STALE" or revision["source_decision_digest"] != current_snapshot or revision["source_version"] != requirement_set["source_version"] or revision["source_digest"] != requirement_set["source_digest"]:
                db.execute("UPDATE revisions SET status='STALE',stale_reason='SOURCE_SNAPSHOT_CHANGED',version=version+1 WHERE tenant_id=? AND id=?", (tenant_id, revision_id))
                db.execute("UPDATE acceptance_cases SET status='INVALIDATED' WHERE tenant_id=? AND revision_id=?", (tenant_id, revision_id))
                return db.execute("SELECT * FROM revisions WHERE tenant_id=? AND id=?", (tenant_id, revision_id)).fetchone(), "STALE"
            report = json.loads(revision["validator_report_json"] or "{}")
            trace = self.trace(tenant_id, revision_id)
            if not report.get("valid"):
                return revision, "VALIDATION_FAILED"
            if not trace or trace["status"] != "VERIFIED":
                return revision, "TRACEABILITY_INCOMPLETE"
            if revision["status"] == "APPROVED":
                return revision, "ALREADY"
            changed = db.execute("UPDATE revisions SET status='APPROVED',approved_at=?,approver_id=?,version=version+1 WHERE tenant_id=? AND id=? AND version=? AND status='GENERATED'", (now(), actor, tenant_id, revision_id, expected_version)).rowcount
            if changed != 1:
                return revision, "STALE"
            db.execute("UPDATE acceptance_cases SET status='ACCEPTED' WHERE tenant_id=? AND revision_id=?", (tenant_id, revision_id))
            return db.execute("SELECT * FROM revisions WHERE tenant_id=? AND id=?", (tenant_id, revision_id)).fetchone(), "OK"

    def job(self, tenant_id: str, job_id: str) -> sqlite3.Row | None:
        with self.conn() as db:
            return db.execute("SELECT * FROM jobs WHERE tenant_id=? AND id=?", (tenant_id, job_id)).fetchone()

    def job_for_revision(self, tenant_id: str, revision_id: str) -> sqlite3.Row | None:
        with self.conn() as db:
            return db.execute("SELECT * FROM jobs WHERE tenant_id=? AND revision_id=? ORDER BY created_at DESC LIMIT 1", (tenant_id, revision_id)).fetchone()

    def idempotency_lookup(self, tenant_id: str, key: str, request_hash: str) -> tuple[dict[str, Any] | None, str]:
        """Return a committed response, or distinguish a miss from key reuse."""
        with self.conn() as db:
            row = db.execute(
                "SELECT request_hash,response_json FROM idempotency_records WHERE tenant_id=? AND key=?",
                (tenant_id, key),
            ).fetchone()
        if not row:
            return None, "MISS"
        if row["request_hash"] != request_hash:
            return None, "CONFLICT"
        return json.loads(row["response_json"]), "REPLAY"

    def idempotency_store(self, tenant_id: str, key: str, request_hash: str, response: dict[str, Any]) -> None:
        """Persist the exact successful response used for subsequent replays."""
        with self.conn() as db:
            db.execute(
                "INSERT INTO idempotency_records(tenant_id,key,request_hash,response_json,created_at) VALUES(?,?,?,?,?)",
                (tenant_id, key, request_hash, canonical_json(response), now()),
            )

    def create_artifact_intent(self, tenant_id: str, kind: str, filename: str, size_bytes: int, sha256: str, media_type: str | None) -> sqlite3.Row:
        artifact_id = str(uuid.uuid4())
        created = now()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
        with self.lock, self.conn() as db:
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id, artifact_id, kind, filename, media_type, sha256, size_bytes, "INTENT_ISSUED", None, created, expires, None))
        return self.artifact(tenant_id, artifact_id)

    def artifact(self, tenant_id: str, artifact_id: str) -> sqlite3.Row | None:
        with self.conn() as db:
            return db.execute("SELECT * FROM artifacts WHERE tenant_id=? AND id=?", (tenant_id, artifact_id)).fetchone()

    def commit_artifact(self, tenant_id: str, artifact_id: str, sha256: str, size_bytes: int, generation: str) -> tuple[sqlite3.Row | None, str]:
        result_status = "OK"
        with self.lock, self.conn() as db:
            artifact = db.execute("SELECT * FROM artifacts WHERE tenant_id=? AND id=?", (tenant_id, artifact_id)).fetchone()
            if not artifact:
                return None, "NOT_FOUND"
            if artifact["sha256"] != sha256 or artifact["size_bytes"] != size_bytes:
                db.execute("UPDATE artifacts SET status='REJECTED',rejected_reason='DIGEST_OR_SIZE_MISMATCH' WHERE tenant_id=? AND id=?", (tenant_id, artifact_id))
                result_status = "DIGEST_MISMATCH"
            elif artifact["status"] == "AVAILABLE":
                return artifact, "ALREADY"
            else:
                # Without a configured object store/scanner, retain a quarantine record;
                # the digest and generation are durable but publication is fail-closed.
                db.execute("UPDATE artifacts SET status='QUARANTINED',object_generation=? WHERE tenant_id=? AND id=?", (generation, tenant_id, artifact_id))
        return self.artifact(tenant_id, artifact_id), result_status

    def make_artifact_available(self, tenant_id: str, artifact_id: str, generation: str) -> sqlite3.Row | None:
        with self.lock, self.conn() as db:
            db.execute("UPDATE artifacts SET status='AVAILABLE' WHERE tenant_id=? AND id=? AND status='QUARANTINED' AND object_generation=?", (tenant_id, artifact_id, generation))
        return self.artifact(tenant_id, artifact_id)

    def download_intent(self, tenant_id: str, artifact_id: str) -> tuple[sqlite3.Row | None, str]:
        artifact = self.artifact(tenant_id, artifact_id)
        if not artifact:
            return None, "NOT_FOUND"
        if artifact["status"] != "AVAILABLE":
            return artifact, "NOT_AVAILABLE"
        return artifact, "OK"
