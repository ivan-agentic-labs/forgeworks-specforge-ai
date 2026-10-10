"""Membership role and JWT scope are independent allow conditions."""
import pytest
from fastapi import HTTPException
from specforge_ai import main as api
from specforge_ai.presentation.role_policy import role_scope_allowed


class Stub:
    def __init__(self, role):
        self.role=role
    def member_role(self, tenant, subject):
        assert tenant=="tenant-1" and subject=="user-1"
        return self.role


@pytest.mark.parametrize(("role","scope_name","allowed"), [
    ("viewer","job:read",True),
    ("VIEWER", "job:read", True),
    ("VIEWER", "artifact:create", False),
    ("OWNER", "artifact:create", True),
    ("REVOKED", "job:read", False),
    ("viewer","artifact:read",True),
    ("viewer","artifact:create",False),
    ("viewer","report:approve",False),
    ("editor","artifact:create",True),
    ("owner","artifact:create",True),
    ("admin","artifact:create",True),
    ("auditor","job:read",False),
    ("","job:read",False),
    (None,"job:read",False),
])
def test_role_allowlist(role,scope_name,allowed):
    assert role_scope_allowed(role,scope_name) is allowed


def test_viewer_cannot_use_over_scoped_jwt(monkeypatch):
    monkeypatch.setattr(api,"verify_session",lambda *_: None)
    claims={"tenant_id":"tenant-1","sub":"user-1","scope":"job:read artifact:create"}
    with pytest.raises(HTTPException) as exc:
        api.scope("artifact:create", Stub("viewer"))(claims)
    assert exc.value.status_code==403
    assert exc.value.detail["code"]=="ROLE_FORBIDDEN"
    assert api.scope("job:read",Stub("viewer"))(claims)==claims


def test_scope_still_required_for_editor(monkeypatch):
    monkeypatch.setattr(api,"verify_session",lambda *_: None)
    claims={"tenant_id":"tenant-1","sub":"user-1","scope":"job:read"}
    with pytest.raises(HTTPException) as exc:
        api.scope("artifact:create",Stub("editor"))(claims)
    assert exc.value.detail["code"]=="INSUFFICIENT_SCOPE"


def test_absent_membership_rejected_even_with_valid_scope(monkeypatch):
    monkeypatch.setattr(api,"verify_session",lambda *_: None)
    claims={"tenant_id":"tenant-1","sub":"user-1","scope":"job:read"}
    with pytest.raises(HTTPException) as exc:
        api.scope("job:read",Stub(None))(claims)
    assert exc.value.detail["code"]=="TENANT_CONTEXT_INVALID"
