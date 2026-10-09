"""PostgreSQL runtime adapter; migrations are applied separately by the migration role."""
from __future__ import annotations

import inspect
import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from specforge_ai.infrastructure.store import Store

TENANT_CONTEXT = ContextVar("specforge_tenant", default=None)
ROLE = "fw_specforge_ai_rw"
ALIASES = {"sets_": "requirement_sets", "decisions": "stakeholder_decisions", "revisions": "spec_revisions"}
ACTIVE_CONNECTION = ContextVar("specforge_connection", default=None)
INSERT_COLUMNS = {"sets_": "tenant_id,id,title,source_version,source_digest,owner_id,status,version", "requirements": "tenant_id,id,set_id,statement,source_span,req_type,provenance_digest", "acceptance_cases": "tenant_id,id,revision_id,requirement_id,case_key,description,status", "artifacts": "tenant_id,id,kind,filename,declared_media_type,sha256,size_bytes,status,object_generation,created_at,expires_at,rejected_reason"}


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def normalize(row):
    if row is None:
        return None
    return Row({key: str(value) if isinstance(value, UUID) else value.isoformat().replace("+00:00", "Z") if isinstance(value, datetime) else json.dumps(value, sort_keys=True, separators=(",", ":")) if isinstance(value, (dict,list)) else value for key, value in row.items()})


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        return normalize(self.cursor.fetchone())

    def fetchall(self):
        return [normalize(row) for row in self.cursor.fetchall()]


class Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=()):
        for table, columns in INSERT_COLUMNS.items():
            statement = re.sub(r"\bINTO " + table + r" VALUES", "INTO " + table + "(" + columns + ") VALUES", statement)
        for source, target in ALIASES.items():
            statement = re.sub(r"\b" + source + r"\b", target, statement)
        statement = statement.replace("ORDER BY rowid", "ORDER BY id")
        if statement.startswith("INSERT OR IGNORE INTO"):
            statement = statement.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1) + " ON CONFLICT DO NOTHING"
        statement = statement.replace("?", "%s")
        try:
            # A savepoint preserves SQLite's recoverable statement-failure semantics.
            with self.connection.transaction():
                cursor = self.connection.execute(statement, parameters)
            return Cursor(cursor)
        except psycopg.IntegrityError as error:
            raise sqlite3.IntegrityError("Database integrity constraint rejected the command") from error


def tenant_method(method):
    @wraps(method)
    def wrapped(self, tenant, *args, **kwargs):
        tenant = str(UUID(str(tenant)))
        token = TENANT_CONTEXT.set(tenant)
        try:
            return method(self, tenant, *args, **kwargs)
        finally:
            TENANT_CONTEXT.reset(token)
    return wrapped


class PostgresStore(Store):
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.lock = threading.RLock()
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as db:
            role = db.execute("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()
            if any(role.values()):
                raise ValueError("Runtime must not use a superuser, BYPASSRLS, CREATEROLE or CREATEDB role")
            if not db.execute("SELECT pg_has_role(current_user, %s, 'MEMBER') AS allowed", (ROLE,)).fetchone()["allowed"]:
                raise ValueError("Runtime login must be a member of the tenant application role")
            if db.execute("SELECT 1 FROM pg_tables WHERE schemaname=current_schema() AND tableowner IN (current_user, %s) AND tablename IN ('tenants','requirement_sets','spec_revisions','jobs','artifacts','memberships','ambiguities','stakeholder_decisions','requirements','acceptance_cases','idempotency_records')", (ROLE,)).fetchone():
                raise ValueError("Runtime must not own product tables")
            attributes = db.execute("SELECT rolsuper, rolbypassrls, rolcanlogin, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=%s", (ROLE,)).fetchone()
            if not attributes or any(attributes.values()):
                raise ValueError("Tenant group role must be NOLOGIN, NOSUPERUSER and NOBYPASSRLS")
            if not db.execute("SELECT 1 FROM information_schema.columns WHERE table_name='requirement_sets' AND column_name='version'").fetchone():
                raise ValueError("Apply migration 002 with the migration role before starting runtime")

    @tenant_method
    def member(self, tenant, user):
        try:
            user = str(UUID(str(user)))
        except ValueError:
            return False  # No provisioned UUID identity mapping; fail closed before SQL.
        with self.conn() as db:
            return db.execute("SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'", (tenant, user)).fetchone() is not None

    @contextmanager
    def conn(self, tenant=None):
        tenant = tenant or TENANT_CONTEXT.get()
        if tenant is None:
            raise ValueError("A transaction requires an explicit tenant context")
        tenant = str(UUID(str(tenant)))
        active = ACTIVE_CONNECTION.get()
        if active:
            if active[0] != id(self) or active[1] != tenant:
                raise ValueError("Nested transaction cannot change store or tenant")
            yield active[2]
            return
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as db:
            db.execute("SET LOCAL ROLE fw_specforge_ai_rw")
            db.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant,))
            # Conservative serialization for this low-volume adapter. No pooling.
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (tenant,))
            connection = Connection(db)
            token = ACTIVE_CONNECTION.set((id(self), tenant, connection))
            try:
                yield connection
            finally:
                ACTIVE_CONNECTION.reset(token)

    def seed(self):
        raise ValueError("PostgreSQL provisioning requires a separate migration/provisioning role")

for name, method in inspect.getmembers(Store, predicate=inspect.isfunction):
    parameters = list(inspect.signature(method).parameters)
    if len(parameters) > 1 and parameters[1] == "tenant_id" and name not in PostgresStore.__dict__:
        setattr(PostgresStore, name, tenant_method(method))
