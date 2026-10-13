"""Offline synthetic coverage for the high-risk local verification scenarios."""
from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient

from specforge_ai.domain.openapi_semantics import canonical_json
from specforge_ai.main import create_app
from tests.unit.test_hardening import headers, setup_revision, upload_source


def test_sf_t01_unreferenced_endpoint_cannot_be_approved(tmp_path):
    app, client, _, _, generation = setup_revision(tmp_path)
    revision_id = generation["id"]
    with app.state.store.conn() as db:
        row = db.execute("SELECT spec_json FROM revisions WHERE id=?", (revision_id,)).fetchone()
        spec = json.loads(row["spec_json"])
        spec["paths"]["/unreferenced"] = {
            "get": {
                "operationId": "unreferenced_fixture_operation",
                "responses": {"200": {"description": "Synthetic orphan endpoint"}},
            }
        }
        raw = canonical_json(spec)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        db.execute("UPDATE revisions SET spec_json=?, spec_sha=? WHERE id=?", (raw, digest, revision_id))

    approval = client.post(
        f"/v1/spec-revisions/{revision_id}/approve",
        headers=headers("spec:approve"),
        json={"spec_sha256": digest, "expected_version": 1},
    )
    assert approval.status_code == 409
    assert approval.json()["code"] == "TRACEABILITY_INCOMPLETE"
    assert client.get(f"/v1/spec-revisions/{revision_id}/download", headers=headers("spec:read")).status_code == 409


def test_sf_t02_ambiguous_refund_cutoff_requires_decision(tmp_path):
    app = create_app(str(tmp_path / "refund.sqlite"), seed=True)
    with TestClient(app) as client:
        artifact_id, digest = upload_source(client, "Refunds are allowed until TBD cutoff")
        created = client.post(
            "/v1/requirement-sets",
            headers=headers("requirements:create"),
            json={"title": "Refund API", "source_artifact_id": artifact_id, "source_sha256": digest},
        )
        assert created.status_code == 201, created.text
        set_id = created.json()["id"]
        ambiguities = client.get(f"/v1/requirement-sets/{set_id}/ambiguities", headers=headers("requirements:read"))
        assert ambiguities.status_code == 200
        item = ambiguities.json()["items"][0]
        assert item["resolution_status"] == "OPEN" and item["severity"] == "HIGH"

        blocked = client.post(
            f"/v1/requirement-sets/{set_id}/spec-revisions",
            headers=headers("spec:generate"),
            json={"source_version": 1, "output_profile": "openapi31"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "OPEN_AMBIGUITY"

        decided = client.post(
            f"/v1/ambiguities/{item['id']}/decisions",
            headers=headers("requirements:decide"),
            json={
                "decision_text": "Refunds are allowed through 23:59 UTC on the purchase date",
                "source_reference": "owner:synthetic-refund-policy-1",
                "expected_version": 1,
            },
        )
        assert decided.status_code == 201, decided.text
        generated = client.post(
            f"/v1/requirement-sets/{set_id}/spec-revisions",
            headers=headers("spec:generate"),
            json={"source_version": 1, "output_profile": "openapi31"},
        )
        assert generated.status_code == 202
        assert generated.json()["status"] == "GENERATED"


def test_sf_t04_source_digest_change_invalidates_approval(tmp_path):
    app, client, set_id, _, generation = setup_revision(tmp_path)
    revision_id = generation["id"]
    source_sha = generation["spec_sha256"]
    approved = client.post(
        f"/v1/spec-revisions/{revision_id}/approve",
        headers=headers("spec:approve"),
        json={"spec_sha256": source_sha, "expected_version": 1},
    )
    assert approved.status_code == 201, approved.text

    with app.state.store.conn() as db:
        db.execute("UPDATE sets_ SET source_digest=? WHERE tenant_id=? AND id=?", ("f" * 64, "00000000-0000-0000-0000-000000000001", set_id))
        revision = db.execute("SELECT spec_sha FROM revisions WHERE id=?", (revision_id,)).fetchone()

    stale = client.post(
        f"/v1/spec-revisions/{revision_id}/approve",
        headers=headers("spec:approve"),
        json={"spec_sha256": revision["spec_sha"], "expected_version": 2},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_VERSION"
    assert client.get(f"/v1/spec-revisions/{revision_id}/download", headers=headers("spec:read")).status_code == 409


def test_sf_t05_secret_in_source_sample_is_blocked_without_echo(tmp_path):
    app = create_app(str(tmp_path / "secret.sqlite"), seed=True)
    secret = "synthetic-not-for-publication-123456789"
    body = f"Example request\nAWS_SECRET_ACCESS_KEY={secret}".encode()
    digest = hashlib.sha256(body).hexdigest()
    with TestClient(app) as client:
        intent = client.post(
            "/v1/artifacts/upload-intents",
            headers=headers("artifact:create"),
            json={
                "kind": "source",
                "filename": "sensitive-requirements.txt",
                "size_bytes": len(body),
                "sha256": digest,
                "declared_media_type": "text/plain",
            },
        )
        assert intent.status_code == 201, intent.text
        uploaded = client.put(intent.json()["upload_url"], content=body)
        assert uploaded.status_code == 201, uploaded.text
        rejected = client.post(
            f"/v1/artifacts/{intent.json()['artifact_id']}/commit",
            headers=headers("artifact:commit"),
            json={"sha256": digest, "size_bytes": len(body), "object_generation": uploaded.json()["object_generation"]},
        )
        assert rejected.status_code == 422
        assert rejected.json()["code"] == "ARTIFACT_SENSITIVE_DATA"
        assert secret not in rejected.text
