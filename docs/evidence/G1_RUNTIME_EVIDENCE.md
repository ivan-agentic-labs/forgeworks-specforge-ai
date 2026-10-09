# G1 runtime evidence — specforge-ai

**Evidence snapshot:** current `main` at `4bbaa2c55f4958509108880967cf207c50390714`  
**Captured:** 2026-10-09  
**Repository:** `ivan-agentic-labs/forgeworks-specforge-ai`

This record is an evidence ledger, not a G1 signoff. It reports only checks that were actually run against the snapshot above. `VERIFIED` means the named bounded check completed in a disposable/local or GitHub Actions environment; `PASS_STATIC_LIMITED` means the check is deterministic/static or uses a synthetic/local harness and is not production/runtime proof. No reviewer approval is inferred.

## Exact local commands and outcomes

All commands below were run from the repository root at the snapshot SHA above.

| Exact command | Local outcome | Evidence boundary |
|---|---|---|
| `python -m pytest -W error` | **PASS — exit 0; 12 passed in 1.71s** | Runs current `tests/e2e`, `tests/integration`, `tests/resilience`, and `tests/unit`; local synthetic/TestClient harness. |
| `python scripts/verify_bootstrap.py` | **PASS — exit 0; 92 files scanned; errors=[]** | Bootstrap structure and heuristic sensitive-content scan only; not a security certification. |
| `python scripts/verify_contracts.py` | **PASS — exit 0; 12 operations; Draft 2020-12 event schema; errors=[]** | Static OpenAPI shape/reference and JSON Schema checks; not independent semantic certification. |
| `python scripts/validate_openapi_independent.py` | **PASS — exit 0; third-party `openapi-spec-validator`** | Independent semantic validation of `contracts/openapi.yaml`; not an application runtime test. |
| `bash -n scripts/probe_disposable_postgres.sh` | **PASS — exit 0** | Shell syntax only; the live disposable PostgreSQL result is recorded below from Actions. |
| `git diff --check` | **PASS — exit 0** | Whitespace/integrity check for the working tree at capture time. |
| Node check | **NOT RUN — no `package.json` exists in the repository** | No Node client/package check is available in current main. |

The local pytest command uses a synthetic HS256 token with `issuer.synthetic.invalid` and a temporary SQLite database. It does **not** prove real IdP/OIDC, production PostgreSQL, external object storage, browser automation, or network egress isolation.

## GitHub Actions evidence

All listed runs checked out exact SHA `4bbaa2c55f4958509108880967cf207c50390714` and completed successfully.

| Area | Workflow/run | Exact SHA | Result and command scope |
|---|---|---|---|
| Application tests | [SpecForge MVP Application CI — run 37877959321](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37877959321) | `4bbaa2c55f4958509108880967cf207c50390714` | **success**; installs API/test dependencies, runs `python -m pytest tests/integration`, then bootstrap/contracts/independent OpenAPI checks and `bash -n scripts/probe_disposable_postgres.sh`. |
| Contract/event/OpenAPI checks | [G1 Contract Verification — run 37877959333](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37877959333) | `4bbaa2c55f4958509108880967cf207c50390714` | **success**; runs `python scripts/verify_bootstrap.py`, `python scripts/verify_contracts.py`, and `python scripts/validate_openapi_independent.py`. |
| Empty disposable PostgreSQL + bounded RLS probe | [G1 Disposable PostgreSQL DDL Proof — run 37879227875](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37879227875) | `4bbaa2c55f4958509108880967cf207c50390714` | **success** on PostgreSQL 17 service; runs `bash scripts/probe_disposable_postgres.sh`. The probe applies `00_role_candidate.sql`, `10_schema_candidate.sql`, and `20_grants_candidate.sql` to an empty disposable DB, then proves one-tenant visibility and rejects a cross-tenant insert as non-owner `fw_specforge_ai_rw` with `app.tenant_id` set. |

The PostgreSQL run is disposable CI evidence only. The probe does not establish the full SELECT/INSERT/UPDATE/DELETE matrix, transaction-context reset, `BYPASSRLS`/privileged-role review, concurrency behavior, production migration safety, or backup/restore.

## Explicit G1 criterion table

| Criterion | Status | Observed evidence on exact SHA | Residual boundary / next evidence |
|---|---|---|---|
| Independent OpenAPI semantic validation | **VERIFIED** | Local `validate_openapi_independent.py` exit 0 and current-SHA contract run 37877959333 success. | Generated client compilation/interoperability and reviewer acceptance remain NOT_RUN. |
| Event schema | **PASS_STATIC_LIMITED** | `verify_contracts.py` exit 0; Draft 2020-12 schema check and static contract checks; current-SHA contract run success. | No broker delivery, compatibility history, or operational versioning proof. |
| Empty disposable migration / DDL | **VERIFIED** | Current-SHA PostgreSQL run 37879227875 success; all three candidate SQL files executed against empty PostgreSQL 17 service. | This is a smoke/probe, not a production migration or data-migration/rollback proof; review-only FK addendum was not applied. |
| Non-owner two-tenant RLS | **VERIFIED (bounded)** | Same PostgreSQL run inserts two tenants, forces RLS on `requirement_sets`, sets `app.tenant_id` as `fw_specforge_ai_rw`, confirms one visible row/zero foreign row, and rejects cross-tenant insert. | Full RLS negative matrix (UPDATE/DELETE/COPY), context reset/pooling, concurrency, and privileged-role/bypass checks are NOT_RUN. |
| Auth / tenant negative tests | **PASS_STATIC_LIMITED** | Current pytest passes synthetic-token missing-scope (`403`) and foreign-tenant (`403`) cases in integration/E2E tests. | Real IdP/OIDC session, CSRF, provisioning, revocation, and production authorization integration are BLOCKED/NOT_RUN. |
| E2E API/UI flow | **PASS_STATIC_LIMITED** | `tests/e2e/test_review_console_flow.py` passes via FastAPI `TestClient`: static console/API flow, ambiguity gate, idempotency, approval, stale-version rejection, and traceability. | No real browser sandbox, cross-browser run, or external-egress isolation. |
| Worker reliability | **PASS_STATIC_LIMITED** | `tests/resilience/test_generation_worker_reliability.py` passes deterministic durable retry/terminal-budget assertions. | No forced process crash, queue/network partition, load, region failure, or production worker run. |
| Artifact / integrity tests | **PASS_STATIC_LIMITED** | Unit/E2E tests pass digest persistence, quarantine and blocked download, deterministic output SHA, idempotent replay, traceability, and stale approval checks. | Uses local SQLite and a placeholder object-store URL; external storage integrity/retention and production artifact provenance are NOT_RUN. |
| Real IdP/OIDC and browser sandbox/egress | **BLOCKED / NOT_RUN** | No current evidence. | Requires real provider integration and independent isolation/egress tests. |
| External storage, legal/domain/ops/cost signoff | **BLOCKED / NOT_RUN** | No current evidence or reviewer artifact. | Requires responsible owner/reviewer decisions and retained logs/approvals. |
| Production backup/restore and resilience | **NOT_RUN** | No current evidence. | Requires restore drill, failure simulation, and operational measurements. |
| Generated client compilation, full test-plan scenarios, and independent reviewer approval | **NOT_RUN** | No current evidence. | Do not infer approval from passing CI or local tests. |

## Gate conclusion

The exact current-main evidence improves the prior baseline: independent OpenAPI, event-schema static checks, disposable DDL, and a bounded non-owner two-tenant RLS probe now have retained local/CI evidence; synthetic API/UI, auth/tenant negative, worker, and artifact/integrity tests also pass within their stated limits. **G1-D remains CONDITIONAL / NOT SIGNED and G1-E remains BLOCKED / OPEN.** In particular, this document does not claim real IdP/OIDC, browser sandbox/egress, external storage, legal/domain/operations/cost signoff, production backup/restore, full RLS coverage, generated-client interoperability, or reviewer approval.
