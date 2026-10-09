# G2 bootstrap status — 9 October 2026

Owner: `ivan-agentic-labs`. Five independent private repositories are authorized.
G1 owner design approval permits bootstrap; historical conditional review text remains baseline evidence. **G1-D remains CONDITIONAL / NOT SIGNED and G1-E remains OPEN/BLOCKED** until all required runtime evidence and reviewer decisions are accepted.

On current `main` SHA `4bbaa2c55f4958509108880967cf207c50390714`, the independent OpenAPI validator, static contract/event checks, application CI, and a disposable PostgreSQL DDL plus bounded non-owner two-tenant RLS probe passed. Local product pytest also passes the current synthetic API/UI, auth/tenant-negative, worker-reliability, and artifact/integrity tests. These are partial, bounded evidence; details and exact run links are in `docs/evidence/G1_RUNTIME_EVIDENCE.md`.

Generated-client compilation, full PostgreSQL RLS CRUD/context-reset/bypass/concurrency coverage, real IdP/OIDC, browser sandbox/egress, external storage, legal/domain/operations/cost signoff, production backup/restore, and independent reviewer approval remain **NOT_RUN or BLOCKED**. No production deployment or customer data is authorized.

APIShield is the first implementation priority AFTER remote bootstrap and CI verification.

The PostgreSQL workflow uses an intentionally public, disposable localhost-only test password. This is not a production credential. Never reuse it outside the isolated test service.
