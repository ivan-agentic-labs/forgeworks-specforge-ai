"""Bounded, integrity-checked source byte store for development and tests."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException

MAX_BYTES = 1024 * 1024
TTL = 300


def reject(code: str, detail: str, status: int = 409):
    raise HTTPException(status_code=status, detail={"type": "about:blank", "title": "Artifact rejected", "status": status, "code": code, "detail": detail, "request_id": "runtime"})


class LocalArtifacts:
    def __init__(self, root: Path):
        if root.is_symlink():
            raise ValueError("Artifact root cannot be a symlink")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database = self.root / "objects.sqlite"
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS objects(tenant TEXT,id TEXT,generation TEXT,sha256 TEXT,size INTEGER,PRIMARY KEY(tenant,id))")

    def connection(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def secret(self) -> str:
        if os.getenv("APP_ENV", "development") not in {"development", "test"}:
            reject("LOCAL_STORAGE_FORBIDDEN", "Local storage is restricted to development/test", 503)
        secret = os.getenv("ARTIFACT_SIGNING_SECRET", "")
        if len(secret.encode()) < 32 or secret == os.getenv("DEV_AUTH_SECRET"):
            reject("STORAGE_NOT_CONFIGURED", "A separate artifact signing secret of at least 32 bytes is required", 503)
        return secret

    def path(self, tenant: str, artifact_id: str) -> Path:
        target = self.root / f"{UUID(tenant)}_{UUID(artifact_id)}.object"
        if target.is_symlink():
            reject("ARTIFACT_INTEGRITY_FAILURE", "Unsafe object path")
        return target

    def intent(self, tenant: str, actor: str, artifact_id: str, action: str, generation: str | None = None):
        expires = int(time.time()) + TTL
        token = jwt.encode({"iss": "specforge-artifacts", "aud": "artifact-transfer", "sub": artifact_id, "tenant_id": tenant, "actor": actor, "action": action, "generation": generation, "jti": str(uuid4()), "exp": expires}, self.secret(), algorithm="HS256")
        return f"/v1/artifact-transfers/{artifact_id}?token={token}", expires

    def capability(self, token: str, artifact_id: str, action: str) -> dict:
        try:
            claims = jwt.decode(token, self.secret(), algorithms=["HS256"], issuer="specforge-artifacts", audience="artifact-transfer", options={"require": ["exp", "sub", "tenant_id", "actor", "action", "jti"]})
            if claims["sub"] != artifact_id or claims["action"] != action:
                raise jwt.InvalidTokenError("wrong capability binding")
            self.path(claims["tenant_id"], claims["sub"])
            return claims
        except (jwt.PyJWTError, ValueError):
            reject("INVALID_ARTIFACT_CAPABILITY", "Artifact capability is invalid or expired", 403)

    def put(self, tenant: str, artifact_id: str, body: bytes, expected_sha: str, expected_size: int) -> dict:
        self.secret()
        digest = hashlib.sha256(body).hexdigest()
        if len(body) > MAX_BYTES:
            reject("ARTIFACT_TOO_LARGE", "Source artifact exceeds 1 MiB", 413)
        if digest != expected_sha or len(body) != expected_size:
            reject("ARTIFACT_DIGEST_MISMATCH", "Uploaded bytes do not match declared digest and size")
        target = self.path(tenant, artifact_id)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM objects WHERE tenant=? AND id=?", (tenant, artifact_id)).fetchone()
            if old:
                if old["sha256"] != digest or old["size"] != len(body):
                    reject("ARTIFACT_IMMUTABLE", "An object cannot be replaced")
                self.verify(tenant, artifact_id, old["generation"], digest, len(body))
                return dict(old)
            generation = str(uuid4())
            fd, temporary = tempfile.mkstemp(dir=self.root, prefix="quarantine-")
            try:
                with os.fdopen(fd, "wb") as file:
                    file.write(body); file.flush(); os.fsync(file.fileno())
                os.link(temporary, target)
                db.execute("INSERT INTO objects VALUES(?,?,?,?,?)", (tenant, artifact_id, generation, digest, len(body)))
            finally:
                os.unlink(temporary)
        return {"generation": generation, "sha256": digest, "size": len(body)}

    def verify(self, tenant: str, artifact_id: str, generation: str, digest: str, size: int) -> bytes:
        with self.connection() as db:
            row = db.execute("SELECT * FROM objects WHERE tenant=? AND id=?", (tenant, artifact_id)).fetchone()
        if not row or row["generation"] != generation or row["sha256"] != digest or row["size"] != size:
            reject("ARTIFACT_GENERATION_MISMATCH", "Object generation, digest or size does not match")
        try:
            fd = os.open(self.path(tenant, artifact_id), os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as file:
                body = file.read(MAX_BYTES + 1)
        except OSError:
            reject("ARTIFACT_INTEGRITY_FAILURE", "Stored object is missing or unsafe")
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            reject("ARTIFACT_INTEGRITY_FAILURE", "Stored bytes fail integrity verification")
        return body

    @staticmethod
    def validate_source(body: bytes, media_type: str | None) -> str:
        if media_type not in {None, "text/plain", "text/markdown", "application/json"}:
            reject("ARTIFACT_MEDIA_TYPE_UNSUPPORTED", "Only UTF-8 text, Markdown and JSON sources are supported", 422)
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            reject("ARTIFACT_VALIDATION_FAILED", "Source must be valid UTF-8", 422)
        if "\x00" in text or not text.strip():
            reject("ARTIFACT_VALIDATION_FAILED", "Source must be non-empty text without NUL bytes", 422)
        if media_type == "application/json":
            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate JSON key")
                    result[key] = value
                return result
            def finite_constant(value):
                raise ValueError("Non-finite JSON number")
            try:
                json.loads(text, object_pairs_hook=unique_object, parse_constant=finite_constant)
            except (ValueError, RecursionError):
                reject("ARTIFACT_VALIDATION_FAILED", "JSON source must be valid and unambiguous", 422)
        return text
