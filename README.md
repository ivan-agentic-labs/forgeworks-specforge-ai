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

CI contains a manual PostgreSQL disposable DDL smoke test. The probe also runs a two-tenant RLS negative test by using the `fw_specforge_ai_rw` application role via `SET ROLE`; it never targets a network host other than `127.0.0.1`.

## Non-goals at this stage
No production deployment, customer data, code-execution agent, public access, financial mutation, license assertion or fake passing tests.

## Governance
The owner approved proceeding with GitHub bootstrap. Technical G1-E controls are still pending until their tests actually pass and evidence is reviewed. See `docs/governance/MASTER_G1_DECISION.md` for pre-approval baseline language; the owner approval is recorded here as a later decision.
