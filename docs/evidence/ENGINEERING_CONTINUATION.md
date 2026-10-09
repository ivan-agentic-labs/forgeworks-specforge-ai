# Engineering continuation — 2026-10-09

## Scope and source

Five independent private repositories remain the project boundary. The original G2 bootstrap ZIP was read and compared with the architecture/handoff documents. Owner authorization permits implementation and GitHub pushes; this record does not assert independent security or domain signoff.

## Implemented changes

- Explicit development authentication; no implicit shared signing-secret fallback.
- Required JWT expiry, issuer, audience, subject and tenant claims; fixed algorithm selection.
- Configurable OIDC RS256/JWKS verification with bounded fetch timeout and key-cache lifetime. Offline tests cover key selection/rotation and algorithm-confusion rejection; no real identity-provider session has been tested.
- All application workflows execute the complete `tests` tree with warnings treated as errors.
- A locked generated TypeScript client and compilation check under `packages/sdk`.

Bearer verification and full-suite CI have been hardened; generated TypeScript contracts compile. Requirements still originate from synthetic fixtures; actual source-document extraction and external object storage are not implemented.

## Verification and limitations

Structure/sensitive-pattern scans, static contracts, independent OpenAPI validation and generated TypeScript compilation were executed locally. These checks are bounded evidence, not a certification that every possible secret or privacy issue is absent. Test credentials are explicitly synthetic; test signing private keys are generated at runtime.

The test log and GitHub Actions run linked by the delivery report are authoritative for the exact tested SHA. APIShield's local browser run is blocked because the browser download returned an invalid archive; the test remains mandatory in CI. Local PostgreSQL is unavailable. The dedicated disposable PostgreSQL Actions service passed for the exact source commit recorded below; this does not prove production database operations.

## Remaining gaps

- Real IdP onboarding, BFF/OIDC browser session, CSRF, revocation and provisioning.
- External S3-compatible storage, scanning/retention/deletion and backup/restore.
- Remote sandbox/egress/SSRF/breakout evidence; execution remains disabled.
- GitHub App installation/webhook/draft-PR effects and AI-provider quality/cost proof.
- Full PostgreSQL runtime adapters for AccessFix, AgentTest and DataReconcile. SpecForge now has an adapter requiring its own dedicated CI proof; production load/recovery remains open.
- Real source extraction/scanning/agent execution beyond the synthetic fixture scope.
- Legal/domain/operations/accessibility/cost and independent reviewer acceptance.

G1-E remains OPEN/BLOCKED. No production deployment, customer data, paid provider calls or product auto-merge is introduced.

## GitHub verification receipt

Source commit: `6c946476a7c9039f85428ded89e6d935f1837d94`. These results cover that exact implementation; later commits require their own workflow results.

Application test result: 24 passed.

- [G1 Contract Verification](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37883274844): **success**.
- [SpecForge MVP Application CI](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai/actions/runs/37883274803): **success**.

## PostgreSQL continuation

Added a real SpecForge runtime adapter and migration 002, tenant-local transactions with nested transaction reuse, a non-owner tenant role, forced RLS, conservative advisory serialization, atomic API idempotency, and a dedicated disposable PostgreSQL workflow. See ADR 0002 and the exact new workflow result before treating the adapter as verified. Source extraction and artifacts remain fixture/quarantine scope.
