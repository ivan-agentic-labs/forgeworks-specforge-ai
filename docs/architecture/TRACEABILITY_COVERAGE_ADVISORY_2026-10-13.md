# Traceability coverage change advisory — 2026-10-13

## Scope

This change adds explicit linkage numerators, denominators, and ratios to the read-only traceability response:

| Metric | Numerator | Denominator |
|---|---|---|
| Operation coverage | Operations carrying a valid stored requirement link | All OpenAPI operations |
| Requirement coverage | Distinct stored requirements represented by an operation | All stored requirements |

A zero denominator reports a ratio of `0.0`; an empty operation, requirement, or acceptance-case set cannot produce `VERIFIED`.

No approval policy was relaxed. Approval continues to require a valid semantic OpenAPI report, complete linkage for every stored requirement, operation, and acceptance case, and no open high/critical ambiguity. This full-linkage rule is stricter than a 95% overall threshold for the current supported flow.

## Policy and release boundary

The owner specification describes 95% overall coverage and 100% critical-requirement coverage, including requirements that are linked or explicitly deferred. The current RequirementSet schema does not model requirement criticality, a confirmed/deferred disposition, or a publish operation. This change therefore reports linkage evidence only; it does **not** claim the owner threshold policy is fully implemented, does not introduce a deferral path, and does not establish publication, customer acceptance, or production readiness. Any future threshold relaxation or criticality/disposition model needs an explicit domain decision and its own contract, state-transition, and migration review.

## Local verification

| Check | Result |
|---|---|
| Focused traceability and explicit-source flow | 8 passed |
| Full pytest suite with warnings treated as errors | 358 passed, 1 skipped; the disposable PostgreSQL runtime test was skipped because no disposable PostgreSQL service was configured |
| Bootstrap structure and heuristic sensitive-content scan | 184 files scanned, no findings; the scan is heuristic and cannot guarantee the absence of all secrets or personal data |
| Static contract check | 14 operations, no errors |
| Independent OpenAPI validator | PASS; this is not an application runtime test |
| Browser session tests | 11 passed |
| Generated TypeScript SDK strict check | PASS; npm reported 0 vulnerabilities |
| Disposable PostgreSQL shell syntax and `git diff --check` | PASS |

These are local synthetic checks, not independent domain/security signoff or G1-E/production acceptance. GitHub Actions results, if triggered by a PR, are tracked separately against the exact PR commit.
