"""A signed artifact transfer URL cannot survive Supabase logout."""
import os
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from specforge_ai.main import create_app
from test_specforge_flow import h, source


def bind_session(url, session_id):
    path = urlsplit(url).path
    old = parse_qs(urlsplit(url).query)["token"][0]
    secret = os.environ["ARTIFACT_SIGNING_SECRET"]
    claims = jwt.decode(old, secret, algorithms=["HS256"],
                        issuer="specforge-artifacts", audience="artifact-transfer")
    claims["session_id"] = session_id
    return path + "?token=" + jwt.encode(claims, secret, algorithm="HS256")


def test_artifact_download_rejects_revoked_session(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "db.sqlite"), seed=True)
    with TestClient(app) as client:
        aid, _ = source(client)
        response = client.post(f"/v1/artifacts/{aid}/download-intents",
                               headers=h("artifact:download"))
        assert response.status_code == 201, response.text
        url = response.json()["download_url"]
        assert client.get(url).status_code == 200
        sid = str(uuid4())
        authenticated_url = bind_session(url, sid)
        monkeypatch.setenv("AUTH_MODE", "supabase")
        monkeypatch.setattr(app.state.store, "session_active",
                            lambda tenant, actor, session: False, raising=False)
        denied = client.get(authenticated_url)
        assert denied.status_code == 401
        assert denied.json()["code"] == "SESSION_REVOKED"
        monkeypatch.setattr(app.state.store, "session_active",
                            lambda tenant, actor, session: True)
        assert client.get(authenticated_url).status_code == 200
        unbound = client.get(url)
        assert unbound.status_code == 403
        assert unbound.json()["code"] == "ARTIFACT_SESSION_REQUIRED"


def test_artifact_upload_rejects_revoked_session(tmp_path, monkeypatch):
    import hashlib
    body = b"fake source contents"
    digest = hashlib.sha256(body).hexdigest()
    app = create_app(str(tmp_path / "db.sqlite"), seed=True)
    with TestClient(app) as client:
        response = client.post("/v1/artifacts/upload-intents", headers=h("artifact:create"),
            json={"kind":"source","filename":"requirements.txt","size_bytes":len(body),
                  "sha256":digest,"declared_media_type":"text/plain"})
        assert response.status_code == 201, response.text
        url = response.json()["upload_url"]
        sid = str(uuid4())
        authenticated_url = bind_session(url, sid)
        monkeypatch.setenv("AUTH_MODE", "supabase")
        monkeypatch.setattr(app.state.store, "session_active",
                            lambda tenant, actor, session: False, raising=False)
        denied = client.put(authenticated_url, content=body)
        assert denied.status_code == 401
        assert denied.json()["code"] == "SESSION_REVOKED"
        monkeypatch.setattr(app.state.store, "session_active",
                            lambda tenant, actor, session: True)
        assert client.put(authenticated_url, content=body).status_code == 201
