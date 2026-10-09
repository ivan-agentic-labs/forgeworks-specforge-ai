from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from specforge_ai.infrastructure.store import TENANT, USER
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


def test_static_console_and_api_complete_approved_flow_with_typed_gates(tmp_path):
    app = create_app(str(tmp_path / "e2e.sqlite"), seed=True)
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/app.js")
        assert page.status_code == 200
        assert "Requirements" in page.text and "Approve revision" in page.text
        assert script.status_code == 200
        assert "/v1/requirement-sets/" in script.text
        assert "OPEN_AMBIGUITY" in script.text
        assert "STALE_VERSION" in script.text
        assert "provider-free" in script.text

        created = client.post(
            "/v1/requirement-sets",
            headers=headers("requirements:create", "set-create-00000001"),
            json={
                "title": "Orders API",
                "source_artifact_id": "33333333-3333-3333-3333-333333333333",
                "source_sha256": "a" * 64,
            },
        )
        assert created.status_code == 201
        set_id = created.json()["id"]
        requirements = client.get(f"/v1/requirement-sets/{set_id}/requirements", headers=headers("requirements:read"))
        ambiguities = client.get(f"/v1/requirement-sets/{set_id}/ambiguities", headers=headers("requirements:read"))
        assert requirements.status_code == ambiguities.status_code == 200
        assert len(requirements.json()["items"]) == 1
        ambiguity = ambiguities.json()["items"][0]

        blocked = client.post(
            f"/v1/requirement-sets/{set_id}/spec-revisions",
            headers=headers("spec:generate", "generate-blocked-0001"),
            json={"source_version": 1, "output_profile": "openapi31"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["code"] == "OPEN_AMBIGUITY"

        decision_body = {
            "decision_text": "Return a JSON object with HTTP 200",
            "source_reference": "product-owner:orders",
            "expected_version": 1,
        }
        decision = client.post(
            f"/v1/ambiguities/{ambiguity['id']}/decisions",
            headers=headers("requirements:decide", "decision-orders-0001"),
            json=decision_body,
        )
        assert decision.status_code == 201
        stale_decision = client.post(
            f"/v1/ambiguities/{ambiguity['id']}/decisions",
            headers=headers("requirements:decide", "decision-orders-0002"),
            json=decision_body,
        )
        assert stale_decision.status_code == 409
        assert stale_decision.json()["code"] == "STALE_VERSION"

        generation_body = {"source_version": 1, "output_profile": "openapi31"}
        generation = client.post(
            f"/v1/requirement-sets/{set_id}/spec-revisions",
            headers=headers("spec:generate", "generate-orders-0001"),
            json=generation_body,
        )
        duplicate = client.post(
            f"/v1/requirement-sets/{set_id}/spec-revisions",
            headers=headers("spec:generate", "generate-orders-0001"),
            json=generation_body,
        )
        assert generation.status_code == duplicate.status_code == 202
        assert generation.json() == duplicate.json()
        payload = generation.json()
        assert payload["status"] == "GENERATED"
        assert len(payload["spec_sha256"]) == 64
        with app.state.store.conn() as db:
            assert db.execute("SELECT COUNT(*) FROM revisions WHERE tenant_id=?", (TENANT,)).fetchone()[0] == 1
            assert db.execute("SELECT COUNT(*) FROM jobs WHERE tenant_id=?", (TENANT,)).fetchone()[0] == 1
            spec = json.loads(db.execute("SELECT spec_json FROM revisions WHERE id=?", (payload["id"],)).fetchone()[0])
        assert spec["x-deterministic-output"] is True
        assert spec["x-generator"] == "specforge-ai.deterministic.v1"

        trace = client.get(f"/v1/spec-revisions/{payload['id']}/traceability", headers=headers("spec:read"))
        assert trace.status_code == 200
        assert trace.json()["status"] == "VERIFIED"
        assert trace.json()["linked_requirements"] == trace.json()["total_requirements"] == 1
        assert trace.json()["linked_acceptance_cases"] == trace.json()["total_acceptance_cases"] == 1

        approval_body = {"spec_sha256": payload["spec_sha256"], "expected_version": 1}
        approval = client.post(
            f"/v1/spec-revisions/{payload['id']}/approve",
            headers=headers("spec:approve", "approve-orders-0001"),
            json=approval_body,
        )
        replay = client.post(
            f"/v1/spec-revisions/{payload['id']}/approve",
            headers=headers("spec:approve", "approve-orders-0001"),
            json=approval_body,
        )
        assert approval.status_code == replay.status_code == 201
        assert approval.json() == replay.json()
        assert approval.json()["status"] == "APPROVED"

        changed = client.post(
            f"/v1/ambiguities/{ambiguity['id']}/decisions",
            headers=headers("requirements:decide", "decision-orders-0003"),
            json={
                "decision_text": "Return a JSON object with HTTP 201",
                "source_reference": "product-owner:orders-v2",
                "expected_version": 2,
            },
        )
        assert changed.status_code == 201
        stale_approval = client.post(
            f"/v1/spec-revisions/{payload['id']}/approve",
            headers=headers("spec:approve", "approve-orders-0002"),
            json=approval_body,
        )
        assert stale_approval.status_code == 409
        assert stale_approval.json()["code"] == "STALE_VERSION"
