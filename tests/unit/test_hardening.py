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


def upload_source(client, text="Create one endpoint\nTBD: What is the success response shape?"):
    body = text.encode()
    digest = hashlib.sha256(body).hexdigest()
    intent = client.post("/v1/artifacts/upload-intents", headers=headers("artifact:create"), json={"kind": "source", "filename": "requirements.txt", "size_bytes": len(body), "sha256": digest, "declared_media_type": "text/plain"})
    assert intent.status_code == 201, intent.text
    uploaded = client.put(intent.json()["upload_url"], content=body)
    assert uploaded.status_code == 201, uploaded.text
    committed = client.post(f"/v1/artifacts/{intent.json()['artifact_id']}/commit", headers=headers("artifact:commit"), json={"sha256": digest, "size_bytes": len(body), "object_generation": uploaded.json()["object_generation"]})
    assert committed.status_code == 201 and committed.json()["status"] == "AVAILABLE", committed.text
    return intent.json()["artifact_id"], digest


def setup_revision(tmp_path):
    app = create_app(str(tmp_path / "db.sqlite"), seed=True)
    client = TestClient(app)
    artifact_id, digest = upload_source(client)
    created = client.post("/v1/requirement-sets", headers=headers("requirements:create"), json={"title": "Orders API", "source_artifact_id": artifact_id, "source_sha256": digest})
    assert created.status_code == 201, created.text
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
    assert report["total_acceptance_cases"] == report["linked_acceptance_cases"] == 2


def test_independent_validator_rejects_unlinked_requirement():
    report = validate_generated_openapi({"openapi": "3.1.0", "info": {"title": "x", "version": "1"}, "x-deterministic-output": True, "paths": {}}, {"req-1"}, {"case-1"})
    assert report["valid"] is False
    assert any("paths" in error for error in report["errors"])


def test_artifact_bytes_are_verified_and_downloadable(tmp_path):
    app = create_app(str(tmp_path / "db.sqlite"), seed=True)
    with TestClient(app) as client:
        artifact_id, digest = upload_source(client, "The API returns JSON")
        download = client.post(f"/v1/artifacts/{artifact_id}/download-intents", headers=headers("artifact:download"))
        assert download.status_code == 201, download.text
        fetched = client.get(download.json()["download_url"])
        assert fetched.status_code == 200 and fetched.content == b"The API returns JSON"
        # A capability issued before revocation must not remain usable.
        with client.app.state.store.conn() as db:
            db.execute("UPDATE memberships SET status='REVOKED' WHERE tenant_id=? AND user_id=?", (TENANT, USER))
        revoked = client.get(download.json()["download_url"])
        assert revoked.status_code == 403 and revoked.json()["code"] == "MEMBERSHIP_REVOKED"
        with client.app.state.store.conn() as db:
            db.execute("UPDATE memberships SET status='ACTIVE' WHERE tenant_id=? AND user_id=?", (TENANT, USER))
        rejected = client.post("/v1/requirement-sets", headers=headers("requirements:create"), json={"title": "Wrong digest", "source_artifact_id": artifact_id, "source_sha256": "0" * 64})
        assert rejected.status_code == 409 and rejected.json()["code"] == "SOURCE_DIGEST_MISMATCH"


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

