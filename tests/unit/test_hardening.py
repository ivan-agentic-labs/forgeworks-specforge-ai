from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from specforge_ai.domain.openapi_semantics import validate_generated_openapi
from specforge_ai.infrastructure.store import TENANT, USER, Store
from specforge_ai.main import create_app

SECRET = "forgeworks-development-secret-32-plus"
ISSUER = "https://issuer.synthetic.invalid"
AUDIENCE = "forgeworks-api"


def headers(scope: str):
    token = jwt.encode({"sub": USER, "tenant_id": TENANT, "scope": scope, "iss": ISSUER, "aud": AUDIENCE, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def setup_revision(tmp_path):
    app = create_app(str(tmp_path / "db.sqlite"), seed=True)
    client = TestClient(app)
    created = client.post("/v1/requirement-sets", headers=headers("requirements:create"), json={"title": "Orders API", "source_artifact_id": "33333333-3333-3333-3333-333333333333", "source_sha256": "a" * 64})
    sid = created.json()["id"]
    ambiguity = client.get(f"/v1/requirement-sets/{sid}/ambiguities", headers=headers("requirements:read")).json()["items"][0]
    client.post(f"/v1/ambiguities/{ambiguity['id']}/decisions", headers=headers("requirements:decide"), json={"decision_text": "HTTP 200 JSON", "source_reference": "owner:synthetic", "expected_version": 1})
    generation = client.post(f"/v1/requirement-sets/{sid}/spec-revisions", headers=headers("spec:generate"), json={"source_version": 1, "output_profile": "openapi31"})
    return app, client, sid, ambiguity, generation.json()


def test_revision_and_approval_are_invalidated_by_new_decision(tmp_path):
    app, client, sid, ambiguity, generation = setup_revision(tmp_path)
    revision_id = generation["id"]
    with app.state.store.conn() as db:
        sha = db.execute("SELECT spec_sha FROM revisions WHERE id=?", (revision_id,)).fetchone()["spec_sha"]
    approved = client.post(f"/v1/spec-revisions/{revision_id}/approve", headers=headers("spec:approve"), json={"spec_sha256": sha, "expected_version": 1})
    assert approved.status_code == 201
    changed = client.post(f"/v1/ambiguities/{ambiguity['id']}/decisions", headers=headers("requirements:decide"), json={"decision_text": "HTTP 201 JSON", "source_reference": "owner:synthetic-2", "expected_version": 2})
    assert changed.status_code == 201
    stale = client.post(f"/v1/spec-revisions/{revision_id}/approve", headers=headers("spec:approve"), json={"spec_sha256": sha, "expected_version": 1})
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"


def test_generated_revision_records_deterministic_validation_and_acceptance_trace(tmp_path):
    _, client, _, _, generation = setup_revision(tmp_path)
    assert generation["status"] == "GENERATED"
    report = client.get(f"/v1/spec-revisions/{generation['id']}/traceability", headers=headers("spec:read")).json()
    assert report["status"] == "VERIFIED"
    assert report["total_acceptance_cases"] == report["linked_acceptance_cases"] == 1


def test_independent_validator_rejects_unlinked_requirement():
    report = validate_generated_openapi({"openapi": "3.1.0", "info": {"title": "x", "version": "1"}, "x-deterministic-output": True, "paths": {}}, {"req-1"}, {"case-1"})
    assert report["valid"] is False
    assert any("paths" in error for error in report["errors"])


def test_artifact_commit_persists_digest_and_fails_closed(tmp_path):
    app = create_app(str(tmp_path / "db.sqlite"), seed=True)
    with TestClient(app) as client:
        intent = client.post("/v1/artifacts/upload-intents", headers=headers("artifact:write"), json={"kind": "source", "filename": "requirements.txt", "size_bytes": 3, "sha256": "b" * 64}).json()
        committed = client.post(f"/v1/artifacts/{intent['artifact_id']}/commit", headers=headers("artifact:write"), json={"sha256": "b" * 64, "size_bytes": 3, "object_generation": "local-test-generation"})
        assert committed.status_code == 201
        assert committed.json()["status"] == "QUARANTINED"
        download = client.post(f"/v1/artifacts/{intent['artifact_id']}/download-intents", headers=headers("artifact:download"))
        assert download.status_code == 409


def test_job_retry_is_durable_and_terminal_after_budget(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    store.seed()
    with store.lock, store.conn() as db:
        job_id = "job-test"
        db.execute("INSERT INTO jobs(tenant_id,id,revision_id,state,created_at,state_version,attempt_count,max_attempts,next_attempt_at,last_error_code,last_error_message,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (TENANT, job_id, "missing-revision", "RUNNING", "2026-01-01T00:00:00Z", 1, 3, 3, None, None, None, "2026-01-01T00:00:00Z"))
    assert store.record_job_failure(TENANT, job_id, "TIMEOUT", "worker timeout", retryable=True) == "FAILED_TERMINAL"
    row = store.job(TENANT, job_id)
    assert row["state"] == "FAILED_TERMINAL"
    assert row["attempt_count"] == 3
    assert row["last_error_code"] == "TIMEOUT"
