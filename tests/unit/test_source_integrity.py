import hashlib

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from specforge_ai.infrastructure.local_artifacts import LocalArtifacts
from specforge_ai.infrastructure.store import Store, TENANT, USER
from specforge_ai.main import create_app
from test_hardening import headers, upload_source


@pytest.mark.parametrize("content", [b'{broken}', b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'])
def test_json_sources_reject_invalid_ambiguous_and_nonfinite_values(content):
    with pytest.raises(HTTPException) as error:
        LocalArtifacts.validate_source(content, "application/json")
    assert error.value.status_code == 422
    assert error.value.detail["code"] == "ARTIFACT_VALIDATION_FAILED"


def test_valid_json_source_is_preserved_exactly():
    body = b'{"requirement": "Return JSON", "enabled": true}'
    assert LocalArtifacts.validate_source(body, "application/json").encode() == body


def test_source_provenance_preserves_original_line_numbers(tmp_path):
    store = Store(str(tmp_path / "db.sqlite"))
    text = "\n- Return JSON\n\n* Require authorization\n"
    digest = hashlib.sha256(text.encode()).hexdigest()
    result = store.create_set(TENANT, "Source", digest, USER, text)
    rows = {row["statement"]: row for row in store.reqs(TENANT, result["id"])}
    assert rows["Return JSON"]["source_span"] == "source:2-2"
    assert rows["Require authorization"]["source_span"] == "source:4-4"
    assert rows["Return JSON"]["provenance_digest"] == hashlib.sha256(f"{digest}:2:Return JSON".encode()).hexdigest()


@pytest.mark.parametrize("text", ["\n".join(["Requirement"] * 101), "x" * 2001, "-\n*\n"])
def test_source_limits_are_explicit_without_partial_writes(tmp_path, text):
    app = create_app(str(tmp_path / "db.sqlite"), seed=True)
    with TestClient(app) as client:
        artifact, digest = upload_source(client, text)
        result = client.post("/v1/requirement-sets", headers=headers("requirements:create"), json={"title":"Source", "source_artifact_id":artifact, "source_sha256":digest})
        assert result.status_code == 422, result.text
        assert result.json()["code"] in {"SOURCE_REQUIREMENT_LIMIT_EXCEEDED", "SOURCE_HAS_NO_REQUIREMENTS"}
    with app.state.store.conn() as db:
        assert db.execute("SELECT count(*) FROM sets_").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM requirements").fetchone()[0] == 0
