"""Public console configuration must never disclose a privileged API key."""
from fastapi.testclient import TestClient
from specforge_ai.main import create_app


def test_public_login_config_and_console(tmp_path,monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY","sb_secret_misconfigured")
    app=create_app(str(tmp_path/"console.db"),seed=True)
    with TestClient(app) as client:
        value=client.get("/v1/auth/config").json()
        assert value["publishable_key"]=="" and value["enabled"] is False
        assert "sb_secret" not in str(value)
        assert client.get("/").status_code==200
        assert client.get('/'+"auth-panel.js").status_code==200
        monkeypatch.setenv("AUTH_MODE","supabase")
        monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY","sb_publishable_synthetic")
        value=client.get("/v1/auth/config").json()
        assert value["enabled"] is True
        assert value["publishable_key"]=="sb_publishable_synthetic"
