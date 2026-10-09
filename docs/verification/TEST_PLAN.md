# SpecForge AI — Verifiable test and evaluation plan

| Test ID | Scenario | Fixture / setup | Expected acceptance result | Execution |
|---|---|---|---|---|
| SF-T01 | Unreferenced endpoint output | generator adversarial fixture | publication blocked | NOT RUN |
| SF-T02 | Ambiguous refund cutoff rule | vague requirement fixture | NEEDS_DECISION until human input | NOT RUN |
| SF-T03 | Required nullable field incompatible | OAS diff fixture | breaking change surfaced | NOT RUN |
| SF-T04 | Update source after approval | different SHA | approval no longer applies | NOT RUN |
| SF-T05 | Requirement asks secret in sample | sensitive fixture | redact/block secret publication | NOT RUN |
| SF-T06 | Cross-tenant spec lookup | foreign ID | denied without leak | NOT RUN |

## Coverage and execution gates
- Unit: every pure domain invariant, deterministic cross-validation, state guard, authorization policy and financial arithmetic where relevant.
- Contract: OpenAPI semantic validation, JSON Schema, request/response/error examples, client generation, event backwards compatibility.
- Integration: PostgreSQL tenant/RLS/FKs/transactions, storage capability, OIDC+BFF flow, inbox/outbox/queue, provider-scoped permissions.
- E2E: five canonical success/failure paths including human approval and result retrieval; use separate tenants and consented/synthetic data.
- Agent evaluation: frozen labeled corpus with human adjudication, baseline comparison, model/version pinning, typed outputs, prompt injection and tool abuse fixtures.
- Security: SAST/SCA/secret/DAST and cross-tenant negative tests, SSRF sandbox escape, revocation, external effect uncertainty.
- Reliability: 2x planned load (tentative), forced worker crash, network partitions, point-in-time DB restore, region failure simulation.

## Metrics to establish on actual runs
- requirement-to-operation provenance coverage
- critical ambiguity unresolved at publish = 0
- reviewed OpenAPI validation pass rate
- incorrect invented requirements on adjudicated set
- time-to-reviewed-contract

**No arbitrary success numbers:** Define threshold from buyer risk tolerance and pilot corpus before G1. Store observed accuracy and sample size, confidence/coverage when meaningful, source hash, run logs, costs, p95, failure distribution. A test case being designed is not a passed test.

## Evidence format
`{test_id, requirement_id, revision_sha, input_fixture_sha, dataset_version, environment, exact_command, expected, observed, pass_fail, reviewer, trace_id, issues}`.
