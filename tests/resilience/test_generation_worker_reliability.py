from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from specforge_ai.infrastructure.store import TENANT, USER, Store, now
from specforge_ai.main import create_app

SECRET = "forgeworks-development-secret-32-plus"
ISSUER = "https://issuer.synthetic.invalid"
AUDIENCE = "forgeworks-api"


def headers(scope: str, key: str | None = None) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": USER,
            "tenant_id": TENANT,
            "scope": scope,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET,
        algorithm="HS256",
    )
    result = {"Authorization": f"Bearer {token}"}
    if key:
        result["Idempotency-Key"] = key
    return result


def create_set_and_decision(client: TestClient) -> tuple[str, str]:
    created = client.post(
        "/v1/requirement-sets",
        headers=headers("requirements:create", "resilience-set-0001"),
        json={
            "title": "Reliability API",
            "source_artifact_id": "33333333-3333-3333-3333-333333333333",
            "source_sha256": "a" * 64,
        },
    )
    sid = created.json()["id"]
    ambiguity = client.get(f"/v1/requirement-sets/{sid}/ambiguities", headers=headers("requirements:read")).json()["items"][0]
    decision = client.post(
        f"/v1/ambiguities/{ambiguity['id']}/decisions",
        headers=headers("requirements:decide", "resilience-decision-0001"),
        json={"decision_text": "HTTP 200 JSON", "source_reference": "owner:reliability", "expected_version": 1},
    )
    assert decision.status_code == 201
    return sid, ambiguity["id"]


def insert_job(store: Store, job_id: str, revision_id: str, state: str = "PENDING", attempts: int = 0, max_attempts: int = 3):
    timestamp = now()
    with store.lock, store.conn() as db:
        db.execute(
            "INSERT INTO jobs(tenant_id,id,revision_id,state,created_at,state_version,attempt_count,max_attempts,next_attempt_at,last_error_code,last_error_message,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (TENANT, job_id, revision_id, state, timestamp, 1, attempts, max_attempts, timestamp, None, None, timestamp),
        )


def test_generation_duplicate_is_replayed_and_conflicting_key_is_rejected(tmp_path):
    app = create_app(str(tmp_path / "duplicate.sqlite"), seed=True)
    with TestClient(app) as client:
        sid, _ = create_set_and_decision(client)
        body = {"source_version": 1, "output_profile": "openapi31"}
        first = client.post(f"/v1/requirement-sets/{sid}/spec-revisions", headers=headers("spec:generate", "generation-retry-0001"), json=body)
        replay = client.post(f"/v1/requirement-sets/{sid}/spec-revisions", headers=headers("spec:generate", "generation-retry-0001"), json=body)
        conflict = client.post(
            f"/v1/requirement-sets/{sid}/spec-revisions",
            headers=headers("spec:generate", "generation-retry-0001"),
            json={"source_version": 1, "output_profile": "different-profile"},
        )
        assert first.status_code == replay.status_code == 202
        assert first.json() == replay.json()
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
        with app.state.store.conn() as db:
            assert db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_worker_retryable_and_terminal_failures_persist_attempt_and_state_versions(tmp_path):
    store = Store(str(tmp_path / "worker.sqlite"))
    store.seed()

    retry_id = "00000000-0000-0000-0000-000000000101"
    insert_job(store, retry_id, "missing-revision", state="RUNNING", attempts=1)
    assert store.record_job_failure(TENANT, retry_id, "TIMEOUT", "temporary worker outage", retryable=True) == "FAILED_RETRYABLE"
    retry_row = store.job(TENANT, retry_id)
    assert retry_row["state"] == "FAILED_RETRYABLE"
    assert retry_row["attempt_count"] == 1
    assert retry_row["state_version"] == 2
    assert retry_row["next_attempt_at"] is not None
    with store.lock, store.conn() as db:
        db.execute("UPDATE jobs SET next_attempt_at=? WHERE tenant_id=? AND id=?", ("2000-01-01T00:00:00Z", TENANT, retry_id))
    assert store.run_job(TENANT, retry_id) == "FAILED_TERMINAL"
    retry_after_run = store.job(TENANT, retry_id)
    assert retry_after_run["attempt_count"] == 2
    assert retry_after_run["state_version"] == 4
    assert retry_after_run["last_error_code"] == "REVISION_NOT_FOUND"

    terminal_id = "00000000-0000-0000-0000-000000000102"
    insert_job(store, terminal_id, "missing-revision", state="RUNNING", attempts=1)
    assert store.record_job_failure(TENANT, terminal_id, "SCHEMA_INVALID", "permanent input error", retryable=False) == "FAILED_TERMINAL"
    terminal_row = store.job(TENANT, terminal_id)
    assert terminal_row["state"] == "FAILED_TERMINAL"
    assert terminal_row["attempt_count"] == 1
    assert terminal_row["state_version"] == 2
    assert terminal_row["next_attempt_at"] is None


def test_decision_change_marks_revision_stale_and_invalidates_acceptance_cases(tmp_path):
    app = create_app(str(tmp_path / "stale.sqlite"), seed=True)
    with TestClient(app) as client:
        sid, ambiguity_id = create_set_and_decision(client)
        generated = client.post(
            f"/v1/requirement-sets/{sid}/spec-revisions",
            headers=headers("spec:generate", "stale-generation-0001"),
            json={"source_version": 1, "output_profile": "openapi31"},
        )
        assert generated.status_code == 202
        revision_id = generated.json()["id"]
        digest = generated.json()["spec_sha256"]
        changed = client.post(
            f"/v1/ambiguities/{ambiguity_id}/decisions",
            headers=headers("requirements:decide", "stale-decision-0001"),
            json={"decision_text": "HTTP 201 JSON", "source_reference": "owner:revised", "expected_version": 2},
        )
        assert changed.status_code == 201
        stale_approval = client.post(
            f"/v1/spec-revisions/{revision_id}/approve",
            headers=headers("spec:approve", "stale-approval-0001"),
            json={"spec_sha256": digest, "expected_version": 1},
        )
        assert stale_approval.status_code == 409
        assert stale_approval.json()["code"] == "STALE_VERSION"
        with app.state.store.conn() as db:
            revision = db.execute("SELECT status,stale_reason,version FROM revisions WHERE id=?", (revision_id,)).fetchone()
            cases = db.execute("SELECT status FROM acceptance_cases WHERE revision_id=?", (revision_id,)).fetchall()
        assert tuple(revision) == ("STALE", "STAKEHOLDER_DECISION_CHANGED", 2)
        assert cases and {row["status"] for row in cases} == {"INVALIDATED"}


def test_artifact_commit_remains_quarantined_and_download_fails_closed(tmp_path):
    app = create_app(str(tmp_path / "artifact.sqlite"), seed=True)
    with TestClient(app) as client:
        intent = client.post(
            "/v1/artifacts/upload-intents",
            headers=headers("artifact:write", "artifact-intent-0001"),
            json={"kind": "source", "filename": "requirements.md", "size_bytes": 8, "sha256": "b" * 64},
        )
        assert intent.status_code == 201
        artifact_id = intent.json()["artifact_id"]
        committed = client.post(
            f"/v1/artifacts/{artifact_id}/commit",
            headers=headers("artifact:write", "artifact-commit-0001"),
            json={"sha256": "b" * 64, "size_bytes": 8, "object_generation": "generation-1"},
        )
        assert committed.status_code == 201
        assert committed.json()["status"] == "QUARANTINED"
        download = client.post(f"/v1/artifacts/{artifact_id}/download-intents", headers=headers("artifact:download"))
        assert download.status_code == 409
        assert download.json()["code"] == "ARTIFACT_NOT_AVAILABLE"
        with app.state.store.conn() as db:
            row = db.execute("SELECT status,object_generation,sha256 FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        assert tuple(row) == ("QUARANTINED", "generation-1", "b" * 64)
