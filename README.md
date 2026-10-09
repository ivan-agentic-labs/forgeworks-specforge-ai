# SpecForge AI

**Status: synthetic MVP milestone and static review console implemented and tested locally. Not deployed or production-ready.**

Traceable requirements-to-API specifications, review and acceptance tests.

The first executable slice stores provenance-backed requirements, treats ambiguity as a blocking object, records stakeholder decisions, generates a deterministic OpenAPI revision, exposes traceability, and binds approval to an immutable digest/version. The static review console is served at `/` and calls only the explicit `/v1` API. No LLM provider is called.

## MVP run and test
```bash
python -m pip install -e 'apps/api[test]'
SPECFORGE_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn specforge_ai.main:app --reload
python -W error -m pytest tests/integration
```
The SQLite store and development issuer are test-only. See `docs/evidence/MVP_CHECKPOINT.md`. The browser UI's API base URL is configurable in its connection panel.

## Documents
- Product scope: `docs/product/PRODUCT_SCOPE.md`
- Architecture and file ownership: `docs/architecture/`
- Source contracts: `contracts/openapi.yaml` and `contracts/events.schema.json`
- Candidate SQL: `docs/verification/sql-candidates/` (NOT migration scripts)
- Signoff / blockers: `docs/verification/DESIGN_GATE_STATUS.md` and `docs/governance/MASTER_G1_DECISION.md`

## Local verification
Install dependencies from `scripts/requirements-verification.txt` then run:

```bash
python scripts/verify_bootstrap.py
python scripts/verify_contracts.py
python scripts/validate_openapi_independent.py
```

CI runs on main and verifies the complete test tree, OpenAPI/event contracts, generated TypeScript client, implemented PostgreSQL MVP runtime, tenant RLS/concurrency and disposable logical backup/restore. These are scoped synthetic proofs; full G1-E and production operations remain open.

## Non-goals at this stage
No production deployment, customer data, code-execution agent, public access, financial mutation, license assertion or fake passing tests.

## Governance
The owner approved proceeding with GitHub bootstrap. Technical G1-E controls are still pending until their tests actually pass and evidence is reviewed. See `docs/governance/MASTER_G1_DECISION.md` for pre-approval baseline language; the owner approval is recorded here as a later decision.


## Engineering continuation

See [current changes and residual gaps](docs/evidence/ENGINEERING_CONTINUATION.md). Configure authentication explicitly; development fixture commands now require `AUTH_MODE=development`, `APP_ENV=development`, a locally generated `DEV_AUTH_SECRET` of at least 32 bytes, and issuer/audience configuration. Never reuse test fixture credentials outside tests.

## Current main engineering status

See [current G1/G2 evidence](docs/verification/CURRENT_GATE_EVIDENCE.md), [exact source receipt](docs/evidence/MAIN_VERIFICATION_2026-10-09.json), and [owner main authorization](docs/governance/ENGINEERING_MAIN_AUTHORIZATION_2026-10-09.md). PostgreSQL adapters exist for all five independent projects. Historical evidence retains its source SHA and narrower scope.

The requirement flow now consumes actual integrity-checked UTF-8 source bytes. Local development/test upload and download capabilities are short-lived, tenant-bound, generation-bound and limited to 1 MiB; requirement statements and provenance digests are derived from those bytes. External object storage, malware scanning and retention/deletion evidence remain open.
