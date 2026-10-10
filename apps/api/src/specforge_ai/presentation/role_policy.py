"""Fail-closed role restrictions applied in addition to signed JWT scopes.

Only role labels explicitly accepted here may authorize a request. This policy
does not grant any permissions absent from the independently verified JWT.
"""
def role_scope_allowed(role: str | None, scope: str) -> bool:
    if not isinstance(role, str) or role != role.strip():
        return False
    normalized = role.casefold()
    if normalized == "viewer":
        return scope.endswith(":read")
    return normalized in {"editor", "owner", "admin"}
