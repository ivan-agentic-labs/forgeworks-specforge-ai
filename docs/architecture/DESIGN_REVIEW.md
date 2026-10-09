# SpecForge AI — Product Design Review (canonical summary)
**Status:** `DESIGN REVIEW CANDIDATE`. G1 domain signoff `BLOCKED`. This note **does not claim tested functionality**.

## Purpose and scope
**ICP:** Product/engineering teams translating requirements into stable HTTP contracts and test plans.

**P0 workflow:** Collect requirements → extract identities/constraints → enumerate ambiguity → obtain stakeholder decision → generate typed OpenAPI → validate → derive acceptance tests → approve revision.

**Explicit exclusions:** No hallucinated business rules, no automatic release of ambiguous spec, no replacement for product-owner signoff.

**Subsystems:** Requirement set/ambiguity/decision; glossary; provenance links; LLM structured output; OAS/diff/test-case engine.

## API inventory (as currently specified)
| Method/path | `operationId` | Scope |
|---|---|---|
| `POST /v1/requirement-sets` | `post_v1_requirement_sets` | `requirements:create` |
| `GET /v1/requirement-sets/{id}/requirements` | `get_v1_requirement_sets_id_requirements` | `requirements:read` |
| `GET /v1/requirement-sets/{id}/ambiguities` | `get_v1_requirement_sets_id_ambiguities` | `requirements:read` |
| `POST /v1/ambiguities/{id}/decisions` | `post_v1_ambiguities_id_decisions` | `requirements:decide` |
| `POST /v1/requirement-sets/{id}/spec-revisions` | `post_v1_requirement_sets_id_spec_revisions` | `spec:generate` |
| `GET /v1/spec-revisions/{id}/traceability` | `get_v1_spec_revisions_id_traceability` | `spec:read` |
| `POST /v1/spec-revisions/{id}/approve` | `post_v1_spec_revisions_id_approve` | `spec:approve` |
| `POST /v1/artifacts/upload-intents` | `post__v1_artifacts_upload_intents` | `artifact:create` |
| `POST /v1/artifacts/{artifact_id}/commit` | `post__v1_artifacts_artifact_id_commit` | `artifact:commit` |
| `GET /v1/artifacts/{artifact_id}` | `get__v1_artifacts_artifact_id` | `artifact:read` |
| `POST /v1/artifacts/{artifact_id}/download-intents` | `post__v1_artifacts_artifact_id_download_intents` | `artifact:download` |
| `GET /v1/jobs/{job_id}` | `get__v1_jobs_job_id` | `job:read` |

`openapi.yaml` is the source. These routes are not running. Remaining contract hardening: independent validator and SDK; verify existing cursor pagination semantics in runtime; security tests and example/runtime parity.

## Database inventory and handling
From candidate SQL (18 tables): `tenants`, `users`, `acceptance_cases`, `artifact_references`, `audit_events`, `idempotency_records`, `inbox_receipts`, `jobs`, `memberships`, `operations`, `outbox_events`, `requirement_sets`, `requirements`, `source_documents`, `spec_revisions`, `ambiguities`, `trace_links`, `stakeholder_decisions`.

- Keep physical table names from `docs/verification/sql-candidates/10_schema_candidate.sql` as **candidate canonical**; historical aliases may not be implemented simultaneously.
- Apply `tenant_id` composite relations, invariant constraints and optimistic version where review/approval is relevant.
- Validate DDL in disposable PostgreSQL with owned migration role, nonowner runtime login role, multiple tenants; DDL presently unexecuted.

## Product-specific invariants and required negative proofs
| ID | Invariant | Negative case required | Evidence |
|---|---|---|---|
| `SF-INV-01` | Every generated operation traces to a confirmed requirement/decision ID | Operation with no provenance blocks approval | Runtime test + reviewer signoff |
| `SF-INV-02` | Ambiguities are first-class unresolved objects | High-impact unresolved ambiguity blocks spec publication | Runtime test + reviewer signoff |
| `SF-INV-03` | Revision immutable after approval | Modification after approval requires new revision | Runtime test + reviewer signoff |
| `SF-INV-04` | OpenAPI syntax+semantics must pass independent checker | Deliberately invalid schema or breaking upgrade rejected | Runtime test + reviewer signoff |

## Modules/files planned for ownership (domain and adapters)
- `apps/api/src/specforge_ai/domain/entities.py`
- `apps/api/src/specforge_ai/infrastructure/persistence/models.py`
- `apps/api/src/specforge_ai/infrastructure/persistence/repositories.py`
- `apps/api/src/specforge_ai/infrastructure/llm/provider_adapter.py`
- `apps/api/src/specforge_ai/domain/requirements_policy.py`
- `apps/api/src/specforge_ai/domain/ambiguity_policy.py`
- `apps/api/src/specforge_ai/domain/provenance_policy.py`
- `apps/api/src/specforge_ai/domain/semantic_versioning.py`
- `apps/api/src/specforge_ai/application/commands/import_requirements.py`
- `apps/api/src/specforge_ai/application/commands/resolve_ambiguity.py`
- `apps/api/src/specforge_ai/application/commands/generate_spec_revision.py`
- `apps/api/src/specforge_ai/application/commands/approve_revision.py`
- `apps/api/src/specforge_ai/infrastructure/openapi/semantic_validator.py`
- `apps/api/src/specforge_ai/infrastructure/openapi/diff_adapter.py`
- `apps/api/src/specforge_ai/infrastructure/github/spec_publisher.py`
- `apps/api/src/specforge_ai/application/commands/commit_artifact.py`
- `apps/api/src/specforge_ai/infrastructure/storage/object_store.py`
- `apps/api/src/specforge_ai/infrastructure/security/tenant_context.py`
- `apps/api/src/specforge_ai/infrastructure/persistence/outbox.py`

## Failure semantics
Unknown requirement returns clarification request, not invented constraint. If downstream AI/provider fails, persist recoverable explicit job state and do not fabricate a successful output. Remote writes require `approval_snapshot` and idempotent effect ledger.

## Evidence and customer acceptance
**Required positive proof:** Stakeholder approved traceability from requirement to spec operation to test and successful independent lint.

**Main threats:** Manufactured requirements, leaking sensitive docs, backward-compatibility errors, bogus test cases.

**Data/IP/approval:** Processor/controller roles and vendor processing terms must be signed off before real data..

## P0 gates and signoff
- Founder/product owner: validates use-case acceptance from qualified user/buyer; **OPEN**.
- API reviewer: external OAS validation, SDK build, authorization negative tests; **NOT RUN**.
- DB/security reviewer: two-tenant SQL execution, constraints, RLS, IAM and sandbox where required; **NOT RUN**.
- Domain specialist: accessibility, finance, graders, provenance, GitHub contract per product; **OPEN**.
- Ops owner: cost/vendor, data policy, restore and incident evidence; **OPEN**.

**Outcome:** Documentation improved and canonical routes/tables inventoried; no independent product-domain approval or G1 PASS granted.
