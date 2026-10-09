from __future__ import annotations
from specforge_ai.presentation.authentication import decode_bearer

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from specforge_ai.infrastructure.store import Store
from specforge_ai.domain.openapi_semantics import canonical_json

ROOT = Path(__file__).resolve().parents[4]


class NewSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1)
    source_artifact_id: UUID
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_text: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class Generate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_version: int = Field(ge=1)
    output_profile: str = Field(min_length=1)


class Approve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_version: int = Field(ge=1)


class CreateUploadIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    declared_media_type: str | None = None


class CommitUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    object_generation: str = Field(min_length=1)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def reject(status: int, code: str, detail: str) -> None:
    raise HTTPException(status_code=status, detail={"type": "about:blank", "title": "Request rejected", "status": status, "code": code, "detail": detail, "request_id": "runtime"})


def auth(authorization: Annotated[str | None, Header()] = None):
    return decode_bearer(authorization)


def scope(required: str, store: Store):
    def dependency(claims=Depends(auth)):
        if not claims.get("tenant_id") or not claims.get("sub") or not store.member(claims["tenant_id"], claims["sub"]):
            reject(403, "TENANT_CONTEXT_INVALID", "Verified membership is required")
        if required not in set(str(claims.get("scope", "")).split()):
            reject(403, "INSUFFICIENT_SCOPE", f"Scope {required} is required")
        return claims
    return dependency


def artifact_response(row) -> dict:
    return {
        "id": row["id"], "status": row["status"], "kind": row["kind"], "sha256": row["sha256"],
        "size_bytes": row["size_bytes"], "created_at": row["created_at"], "rejected_reason": row["rejected_reason"],
    }


def job_response(row) -> dict:
    return {
        "id": row["id"], "kind": "spec_generation", "state": row["state"], "created_at": row["created_at"],
        "state_version": row["state_version"], "attempt_count": row["attempt_count"], "last_error_code": row["last_error_code"],
        "max_attempts": row["max_attempts"], "next_attempt_at": row["next_attempt_at"],
    }


def idempotency_header(value: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> str | None:
    if value is not None and not 16 <= len(value) <= 128:
        reject(400, "INVALID_IDEMPOTENCY_KEY", "Idempotency-Key must contain 16 to 128 characters")
    return value


def create_app(db_path: str | None = None, seed: bool = False):
    store = Store(db_path or os.getenv("SPECFORGE_DB_PATH", str(ROOT / ".runtime/specforge.db")))
    if seed:
        store.seed()
    app = FastAPI(title="SpecForge AI MVP", version="0.2.0")
    app.state.store = store

    def idempotent(claims, action: str, key: str | None, payload: dict, operation):
        """Serialize a command and replay its successful response for duplicate delivery."""
        if key is None:
            return operation()
        request_hash = hashlib.sha256(canonical_json({"action": action, "actor": claims["sub"], "payload": payload}).encode()).hexdigest()
        with store.lock:
            replay, status = store.idempotency_lookup(claims["tenant_id"], key, request_hash)
            if status == "CONFLICT":
                reject(409, "IDEMPOTENCY_CONFLICT", "Idempotency-Key was already used with a different request")
            if status == "REPLAY":
                return replay
            response = operation()
            store.idempotency_store(claims["tenant_id"], key, request_hash, response)
            return response

    @app.exception_handler(HTTPException)
    async def errors(_, exc):
        return JSONResponse(status_code=exc.status_code, content=exc.detail if isinstance(exc.detail, dict) else {"type": "about:blank", "title": "Request rejected", "status": exc.status_code, "code": "REQUEST_REJECTED", "detail": str(exc.detail), "request_id": "runtime"})

    @app.get("/healthz")
    def health():
        return {"status": "ok", "service": "specforge-ai"}

    @app.post("/v1/requirement-sets", status_code=201)
    def create(body: NewSet, claims=Depends(scope("requirements:create", store))):
        row = store.create_set(claims["tenant_id"], body.title, body.source_sha256, claims["sub"])
        return {"id": row["id"], "status": row["status"], "created_at": iso_now(), "title": row["title"], "source_version": row["source_version"], "source_digest": row["source_digest"], "owner_id": row["owner_id"]}

    @app.get("/v1/requirement-sets/{sid}/requirements")
    def requirements(sid: UUID, claims=Depends(scope("requirements:read", store))):
        if not store.get_set(claims["tenant_id"], str(sid)):
            reject(404, "RESOURCE_NOT_FOUND", "Requirement set is not visible")
        items = [{"id": r["id"], "set_id": r["set_id"], "source_span": r["source_span"], "statement": r["statement"], "requirement_type": r["req_type"], "provenance_digest": r["provenance_digest"]} for r in store.reqs(claims["tenant_id"], str(sid))]
        return {"items": items, "next_cursor": None, "has_more": False}

    @app.get("/v1/requirement-sets/{sid}/ambiguities")
    def ambiguities(sid: UUID, claims=Depends(scope("requirements:read", store))):
        if not store.get_set(claims["tenant_id"], str(sid)):
            reject(404, "RESOURCE_NOT_FOUND", "Requirement set is not visible")
        items = [{"id": a["id"], "requirement_id": a["requirement_id"], "severity": a["severity"], "question": a["question"], "resolution_status": a["status"], "version": a["version"]} for a in store.amb(claims["tenant_id"], str(sid))]
        return {"items": items, "next_cursor": None, "has_more": False}

    @app.post("/v1/ambiguities/{aid}/decisions", status_code=201)
    def decision(aid: UUID, body: Decision, claims=Depends(scope("requirements:decide", store)), idempotency_key: str | None = Depends(idempotency_header)):
        def operation():
            result, status = store.decide(claims["tenant_id"], str(aid), claims["sub"], body.decision_text, body.source_reference, body.expected_version)
            if status == "NOT_FOUND":
                reject(404, "RESOURCE_NOT_FOUND", "Ambiguity is not visible")
            if status == "STALE":
                reject(409, "STALE_VERSION", "Ambiguity version is stale")
            return {"id": result["id"], "status": "RECORDED", "created_at": iso_now(), "ambiguity_id": str(aid), "actor_id": claims["sub"], "decision_hash": result["decision_hash"], "source_reference": body.source_reference}
        return idempotent(claims, f"decision:{aid}", idempotency_key, body.model_dump(), operation)

    @app.post("/v1/requirement-sets/{sid}/spec-revisions", status_code=202)
    def generate(sid: UUID, body: Generate, claims=Depends(scope("spec:generate", store)), idempotency_key: str | None = Depends(idempotency_header)):
        def operation():
            revision, status = store.revision(claims["tenant_id"], str(sid), body.source_version, body.output_profile)
            if status == "NOT_FOUND":
                reject(404, "RESOURCE_NOT_FOUND", "Requirement set is not visible")
            if status == "OPEN_AMBIGUITY":
                reject(409, "OPEN_AMBIGUITY", "Resolve all high-impact ambiguities before generation")
            if status == "SOURCE_VERSION_STALE":
                reject(409, "STALE_VERSION", "Requirement source version is stale")
            job_row = store.job_for_revision(claims["tenant_id"], revision["id"])
            if not job_row:
                reject(503, "JOB_NOT_PERSISTED", "Durable generation job was not persisted")
            return {"id": revision["id"], "status": revision["status"], "created_at": revision["created_at"], "requirement_set_id": str(sid), "input_version": revision["source_version"], "job_id": job_row["id"], "spec_sha256": revision["spec_sha"]}
        return idempotent(claims, f"generate:{sid}", idempotency_key, body.model_dump(), operation)

    @app.get("/v1/spec-revisions/{rid}/traceability")
    def trace(rid: UUID, claims=Depends(scope("spec:read", store))):
        report = store.trace(claims["tenant_id"], str(rid))
        if not report:
            reject(404, "RESOURCE_NOT_FOUND", "Revision is not visible")
        return report

    @app.post("/v1/spec-revisions/{rid}/approve", status_code=201)
    def approve(rid: UUID, body: Approve, claims=Depends(scope("spec:approve", store)), idempotency_key: str | None = Depends(idempotency_header)):
        def operation():
            revision, status = store.approve(claims["tenant_id"], str(rid), body.spec_sha256, body.expected_version, claims["sub"])
            if status == "NOT_FOUND":
                reject(404, "RESOURCE_NOT_FOUND", "Revision is not visible")
            if status == "STALE":
                reject(409, "STALE_VERSION", "Revision or source snapshot is stale")
            if status == "DIGEST_MISMATCH":
                reject(409, "DIGEST_MISMATCH", "Spec digest does not match revision")
            if status == "VALIDATION_FAILED":
                reject(422, "OPENAPI_SEMANTIC_INVALID", "Generated OpenAPI failed independent semantic validation")
            if status == "TRACEABILITY_INCOMPLETE":
                reject(409, "TRACEABILITY_INCOMPLETE", "Every requirement and acceptance case must be linked")
            approved_at = revision["approved_at"] or iso_now()
            return {"id": str(rid), "status": "APPROVED", "created_at": revision["created_at"], "revision_id": str(rid), "spec_sha256": revision["spec_sha"], "approver_id": claims["sub"], "approved_at": approved_at}
        return idempotent(claims, f"approve:{rid}", idempotency_key, body.model_dump(), operation)

    @app.post("/v1/artifacts/upload-intents", status_code=201)
    def upload_intent(body: CreateUploadIntent, claims=Depends(scope("artifact:write", store))):
        row = store.create_artifact_intent(claims["tenant_id"], body.kind, body.filename, body.size_bytes, body.sha256, body.declared_media_type)
        return {"artifact_id": row["id"], "status": "INTENT_ISSUED", "upload_url": f"https://object-store.invalid/upload/{row['id']}", "expires_at": row["expires_at"], "required_headers": {"Content-Type": body.declared_media_type or "application/octet-stream", "X-Artifact-SHA256": body.sha256}}

    @app.post("/v1/artifacts/{artifact_id}/commit", status_code=201)
    def commit_artifact(artifact_id: UUID, body: CommitUpload, claims=Depends(scope("artifact:write", store))):
        row, status = store.commit_artifact(claims["tenant_id"], str(artifact_id), body.sha256, body.size_bytes, body.object_generation)
        if status == "NOT_FOUND":
            reject(404, "RESOURCE_NOT_FOUND", "Artifact is not visible")
        if status == "DIGEST_MISMATCH":
            reject(409, "DIGEST_MISMATCH", "Committed artifact metadata does not match the intent")
        return artifact_response(row)

    @app.get("/v1/artifacts/{artifact_id}")
    def get_artifact(artifact_id: UUID, claims=Depends(scope("artifact:read", store))):
        row = store.artifact(claims["tenant_id"], str(artifact_id))
        if not row:
            reject(404, "RESOURCE_NOT_FOUND", "Artifact is not visible")
        return artifact_response(row)

    @app.post("/v1/artifacts/{artifact_id}/download-intents", status_code=201)
    def download_intent(artifact_id: UUID, claims=Depends(scope("artifact:download", store))):
        row, status = store.download_intent(claims["tenant_id"], str(artifact_id))
        if status == "NOT_FOUND":
            reject(404, "RESOURCE_NOT_FOUND", "Artifact is not visible")
        if status == "NOT_AVAILABLE":
            reject(409, "ARTIFACT_NOT_AVAILABLE", "Artifact remains quarantined until validation")
        return {"artifact_id": row["id"], "download_url": f"https://object-store.invalid/download/{row['id']}", "expires_at": (datetime.now(timezone.utc).replace(microsecond=0)).isoformat().replace("+00:00", "Z"), "object_generation": row["object_generation"]}

    @app.get("/v1/jobs/{jid}")
    def job(jid: UUID, claims=Depends(scope("job:read", store))):
        row = store.job(claims["tenant_id"], str(jid))
        if not row:
            reject(404, "RESOURCE_NOT_FOUND", "Job is not visible")
        return job_response(row)

    # The review console is static and calls only the explicit /v1 API above.
    # No provider or server-side rendering path is introduced by this mount.
    web_dir = ROOT / "apps" / "web"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

    return app


app = create_app(seed=os.getenv("SPECFORGE_SEED_FIXTURE", "0") == "1")

