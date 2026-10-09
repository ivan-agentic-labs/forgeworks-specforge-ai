# G1 evidence index

**Evidence snapshot:** current `main` SHA `4bbaa2c55f4958509108880967cf207c50390714`. The detailed ledger is [`docs/evidence/G1_RUNTIME_EVIDENCE.md`](../evidence/G1_RUNTIME_EVIDENCE.md). Statuses are bounded evidence outcomes, not G1-D/G1-E approval.

| Evidence item | Status | Current evidence |
|---|---|---|
| Third-party independent OpenAPI validation | **VERIFIED** | Local exit 0 and [G1 Contract Verification run 37877959333](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37877959333), exact SHA above. |
| Event JSON Schema and static contract checks | **PASS_STATIC_LIMITED** | `python scripts/verify_contracts.py` exit 0; same current-SHA contract run. |
| PostgreSQL DDL from empty disposable instance | **VERIFIED** | [G1 Disposable PostgreSQL DDL Proof run 37879227875](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37879227875), exact SHA above. |
| Non-owner two-tenant RLS probe | **VERIFIED (bounded)** | Same PostgreSQL run proves one-tenant visibility and rejects cross-tenant INSERT for `fw_specforge_ai_rw`; not a full CRUD/context-reset/bypass matrix. |
| Auth/tenant negative tests | **PASS_STATIC_LIMITED** | Current pytest synthetic-token missing-scope and foreign-tenant `403` cases pass. |
| E2E API/UI test flow | **PASS_STATIC_LIMITED** | Current TestClient-based static console/API flow passes; no real browser run. |
| Worker reliability tests | **PASS_STATIC_LIMITED** | Current deterministic retry/terminal-budget tests pass. |
| Artifact/integrity tests | **PASS_STATIC_LIMITED** | Current digest/quarantine/idempotency/traceability/stale-approval tests pass in local SQLite harness. |
| Generated client compilation/interoperability | **NOT_RUN** | No generated client or compile run is present. |
| Full RLS CRUD, transaction reset, role-bypass, and concurrency checks | **NOT_RUN** | The disposable probe is intentionally bounded. |
| Real IdP/OIDC session, CSRF, provisioning, and revocation | **BLOCKED / NOT_RUN** | Synthetic HS256 tokens only; no provider evidence. |
| Browser sandbox/egress, unsafe tools, external storage | **BLOCKED / NOT_RUN** | No independent runtime or storage-provider evidence. |
| Owner/independent reviewer signoff and retained approval logs | **NOT_RUN** | Do not infer approval from CI or local tests. |
| Legal/domain/operations/cost signoff and production backup/restore | **BLOCKED / NOT_RUN** | Residual G1 blockers remain. |

The current [application CI run 37877959321](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37877959321) also succeeded at the exact SHA and ran integration pytest, bootstrap/contracts/independent OpenAPI checks, and shell syntax validation. See the runtime ledger for exact commands and boundaries.
