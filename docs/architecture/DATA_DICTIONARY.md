# SpecForge AI — Data model, relational constraints and transaction design

## Canonical relational aggregates (v4.1: authoritative)

Previous v4.0 terminology is mapped to **one** physical table per aggregate. Never generate two tables for one alias.

| Previous functional term | Canonical table | Mapping |
|---|---|---|
| `requirement_sets` | `requirement_sets` | Unchanged |
| `source_documents` | `source_documents` | Unchanged |
| `requirements` | `requirements` | Unchanged |
| `ambiguities` | `ambiguities` | Unchanged |
| `stakeholder_decisions` | `stakeholder_decisions` | Unchanged |
| `spec_revisions` | `spec_revisions` | Unchanged |
| `operations` | `operations` | Unchanged |
| `trace_links` | `trace_links` | Unchanged |
| `acceptance_cases` | `acceptance_cases` | Unchanged |

All canonical tables must have a physical column contract below; shared per-product platform tables are covered in governance.

## RLS and role design (not executed migration)
- Separate migration/owner role from API/worker read-write roles; application roles never hold BYPASSRLS/superuser or table owner privileges.
- Enable RLS and FORCE where suitable, separate `USING` and `WITH CHECK`; set `app.tenant_id` with `SET LOCAL` inside transactional request after auth membership resolution.
- Transaction-pool reused sessions must not inherit tenant variables. Test PgBouncer/pooled mode after selected provider is known.
- Compound FK + membership/policy validation is required despite RLS; no cross-tenant object keys or storage ACL inheritance.
- Synthetic two-tenant fixtures cover SELECT/INSERT/UPDATE/DELETE, foreign keys, joined views, workers and pooled connections.

## SQL transaction boundaries
1. Job accepted: domain validation + write `jobs` + `outbox` + `idempotency_records` in a **single commit**; return 202 only after commit succeeds.
2. Worker lease: visibility timeout/fencing token; dedupe message ID in inbox; at-least-once delivery with idempotent handlers.
3. Approval: compare `version` and content SHA, actor role+tenant, policy, expiry and external permission; conflicting writers return 409.
4. External effect: commit unique effect reservation → invoke outside DB transaction → store external ID/outcome; timeout -> `UNKNOWN_REMOTE` -> provider-specific lookup/reconciliation; never retry blindly.
5. Artifact: quarantine content until checksum, MIME, virus/format checks and final tenant-owner authorization; download intent scoped and revocation bounded by provider semantics.

## Domain-specific invariants and source column dictionary
Source snapshots and decision provenance immutable by revision; LLM output not accepted as a business decision; reviewer digest pinned; no direct publication without approval.

# SpecForge AI — proposed physical model, not executed DDL

## Shared physical schema model (applied independently per product)

All tenant-owned tables: `tenant_id UUID NOT NULL`, `id UUID NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `PRIMARY KEY (tenant_id,id)`.
A child FK must use `(tenant_id,parent_id) REFERENCES parent(tenant_id,id)`; foreign UUID alone is insufficient. Database roles: migration owner != API/worker; API/worker roles have no SUPERUSER/BYPASSRLS privileges. Proposed RLS uses `tenant_id = nullif(current_setting('app.tenant_id',true),'')::uuid` with `USING` and `WITH CHECK`; tenant context set `SET LOCAL` **inside a transaction** using server-verified membership, never client supplied. Connection pool reuse without transaction isolation is prohibited.

Other independent core tables for every product: `tenants`, `users`, `memberships`, `jobs`, `outbox_events`, `inbox_receipts`, `idempotency_records`, `audit_events`, `artifact_references` (tenant-scoped). Their schema and cleanup/retention must be supplied by the shared-platform contract before migration code.

Immutable audit records require explicit retention/legal basis. Event idempotency does not imply exactly-once external effects; use reconciliation and unique natural business keys. Soft deletion alone is not a privacy deletion implementation.


## Domain tables

### `requirement_sets`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `title` | `text NOT NULL` |
| `owner_id` | `uuid NOT NULL` |
| `current_version` | `int NOT NULL` |
| `status` | `text NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `INDEX (tenant_id, owner_id)`.
**Domain constraints:** source version only changes by new revision.

### `source_documents`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `set_id` | `uuid NOT NULL` |
| `source_version` | `int NOT NULL` |
| `sha256` | `char(64) NOT NULL` |
| `artifact_key` | `text NOT NULL` |
| `format` | `text NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, set_id, source_version)`.
**Scoped FK:** `(tenant_id,set_id) -> requirement_sets(tenant_id,id)`.
**Domain constraints:** immutable file digest.

### `requirements`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `set_id` | `uuid NOT NULL` |
| `source_version` | `int NOT NULL` |
| `source_span` | `text NOT NULL` |
| `statement` | `text NOT NULL` |
| `provenance_hash` | `char(64) NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, set_id, source_version, provenance_hash)`.
**Scoped FK:** `(tenant_id,set_id) -> requirement_sets(tenant_id,id)`.
**Domain constraints:** no source-less approved requirement.

### `ambiguities`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `requirement_id` | `uuid NOT NULL` |
| `severity` | `text NOT NULL` |
| `question` | `text NOT NULL` |
| `status` | `text NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `INDEX (tenant_id, status, severity)`.
**Scoped FK:** `(tenant_id,requirement_id) -> requirements(tenant_id,id)`.
**Domain constraints:** unresolved critical blocks approval.

### `stakeholder_decisions`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `ambiguity_id` | `uuid NOT NULL` |
| `actor_id` | `uuid NOT NULL` |
| `decision_hash` | `char(64) NOT NULL` |
| `decision_artifact_key` | `text NOT NULL` |
| `version` | `int NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, ambiguity_id, version)`.
**Scoped FK:** `(tenant_id,ambiguity_id) -> ambiguities(tenant_id,id)`.
**Domain constraints:** only authorized stakeholder can decide.

### `spec_revisions`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `set_id` | `uuid NOT NULL` |
| `source_version` | `int NOT NULL` |
| `content_sha256` | `char(64) NOT NULL` |
| `validation_state` | `text NOT NULL` |
| `artifact_key` | `text NOT NULL` |
| `approved_at` | `timestamptz` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, set_id, content_sha256)`.
**Scoped FK:** `(tenant_id,set_id) -> requirement_sets(tenant_id,id)`.
**Domain constraints:** approved artifact immutable.

### `trace_links`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `revision_id` | `uuid NOT NULL` |
| `requirement_id` | `uuid NOT NULL` |
| `operation_id` | `uuid NOT NULL` |
| `test_case_id` | `uuid` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, revision_id, requirement_id, operation_id)`.
**Scoped FK:** `(tenant_id,revision_id) -> spec_revisions(tenant_id,id)`; `(tenant_id,requirement_id) -> requirements(tenant_id,id)`; `(tenant_id,operation_id) -> operations(tenant_id,id)`; `(tenant_id,test_case_id) -> acceptance_cases(tenant_id,id)` when test_case_id not null. Require revision consistency with composite alternate unique key `(tenant_id,spec_revision_id,id)` on operations and equivalent test-case revision key; prohibit links across revisions.
**Domain constraints:** every approved operation linked to source or signed design decision.

## Transaction boundaries

- Creating a job: validate actor+tenant+resource; insert job and outbox in same PostgreSQL commit, then return HTTP 202. Broker delivery happens after transaction commit.
- External mutation: reserve unique business effect key and approval snapshot inside DB transaction; call external API outside transaction; reconcile remote effect ID after uncertain timeout.
- Final approval: optimistic `version`/If-Match plus exact content digest; reject stale updates.
- Tenant isolation test: same IDs searched under different tenant contexts must not disclose existence or associated storage objects.

## Schema proof not yet collected

Column design is not a generated migration and has not been executed against PostgreSQL. FK/index names, enum strategy, JSONB evidence fields, full SQL migration, query plans, retention and concurrency isolation must be validated during implementation.


> **DDL status:** conceptual physical design; no migration executed or database schema proved. Exact FK constraint names, indexes, query plans, row locks and RLS enforcement require G2/G4 evidence. The appended v3.2 dictionary is historic source input, not an executed implementation.


## v4.1 — Added physical model definitions and closure notes

These are **design-only table contracts**, not executed migrations. Explicit FK/index names, datatype behavior, RLS, and transaction isolation remain subject to PostgreSQL tests.

### `operations`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `spec_revision_id` | `UUID NOT NULL` |
| `operation_key` | `TEXT NOT NULL` |
| `http_method` | `TEXT NOT NULL` |
| `path_template` | `TEXT NOT NULL` |
| `source_decision_id` | `UUID` |
| `approval_status` | `TEXT NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id,spec_revision_id,http_method,path_template)`.
**Scoped FK:** `(tenant_id,spec_revision_id) -> spec_revisions`; optional `(tenant_id,source_decision_id) -> stakeholder_decisions`.
**Domain constraints:** Unique OAS operation per method/path and exact approved provenance; generated content cannot create stakeholder decision records.

### `acceptance_cases`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `spec_revision_id` | `UUID NOT NULL` |
| `requirement_id` | `UUID NOT NULL` |
| `case_key` | `TEXT NOT NULL` |
| `assertions_json` | `JSONB NOT NULL` |
| `status` | `TEXT NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id,spec_revision_id,case_key)`.
**Scoped FK:** `(tenant_id,spec_revision_id) -> spec_revisions`; `(tenant_id,requirement_id) -> requirements`.
**Domain constraints:** Every critical acceptance case must trace to a requirement and approved revision; empty assertion set is invalid.


### Domain-specific mapping decisions

- API OpenAPI output is a generated artifact; relational `operations` preserves traceability to explicit requirement and decision versions.
