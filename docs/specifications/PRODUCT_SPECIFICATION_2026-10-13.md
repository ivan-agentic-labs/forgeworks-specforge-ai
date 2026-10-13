# SpecForge AI — revised owner product specification (2026-10-13)

**Source basis:** `SpecForge_AI_Full_Detailed_v2.2.md`, `SpecForge_AI_Expanded_Parent_v3.0.md`, `SpecForge_AI_Ultra_Detailed_Extension.md` and the matching `IR/` catalogue in the owner's uploaded `ForgeWorks_5_Projects_Long_Narrative_plus_IR.zip`.

**Document state:** owner design requirements; not independent evidence of implemented or hosted functionality. This replaces the old bootstrap-era design-review and handoff prose, while preserving actual code/contracts/migrations/tests and dated audit evidence.

## Product scope
Traceable approved requirements into versioned OpenAPI and acceptance tests. It remains a separate backend service connected through the planned shared ForgeWorks front end; not a separate production domain.

## Owner P0 workflow / controls
1. Import immutable RequirementSet documents with SHA-256 and source spans; missing or low-confidence source spans create Ambiguities.
2. Classify critical/high/medium/low ambiguity. Critical ambiguity cannot be waived or silently resolved; stakeholder Decision is required.
3. Generate new OpenAPI 3.1 SpecRevision from confirmed requirements and decisions only. AI suggestions are not unreviewed business rules.
4. Deterministically validate `$ref`, operationId uniqueness, trace links, security schemes, orphan schemas and glossary compliance.
5. Compute traceability (linked operations/total; requirements linked or explicitly deferred/confirmed requirements). Require threshold and 100% coverage for critical requirements.
6. Review semantic diff, ambiguity register and coverage. Bind approval to current revision digest; new RequirementSet invalidates dependent revisions.
7. Publish only with zero critical ambiguities, valid approval, minimum coverage and validation; export provenance/evidence and acceptance tests.

## Limits and non-goals
Owner-designed publish threshold 95% overall and 100% critical; bounded generation worker 10 minutes; three validator retries on retryable tool error; retention design two years. Verify policy version, denominator edge cases and deployment scope before acceptance.

## Implementation records and proof
The uploaded catalogue contains **480 IR IDs but 12 distinct topic patterns**, each repeated 40 times. ID count is not completion count. The distinctive topics are:

- 01. requirement import
- 02. ambiguity detection
- 03. decision recording
- 04. OpenAPI generation
- 05. semantic validation
- 06. traceability calculation
- 07. glossary check
- 08. approval binding
- 09. publish gate
- 10. evidence export
- 11. stale detection
- 12. regeneration

For each topic, bind the implemented source file, requirement ID, positive/negative test, fixture digest, result, commit SHA, environment, reviewer and known limits. A generic repeated checklist is not a passed test.

## Production acceptance
The latest repository source and actual hosted runtime take precedence over an older blueprint's claim of implementation. Explicitly verify real identity and authorization, RLS/tenant isolation, bounded provider permissions, reconciliation, audit, backup/restore and domain-review acceptance before marking RELEASED. Current gate remains open until source-SHA-bound evidence is accepted.

See [shared-app boundary](../platform/ONE_APP_FIVE_SERVICES.md), [current gate evidence](../verification/CURRENT_GATE_EVIDENCE.md) and [hosted runbook](../../ops/runbooks/RUNTIME_RELEASE_VERIFICATION.md).

## Complete uploaded source

Read [the complete owner documents and IR catalogue](source/README.md). These files are preserved byte-for-byte; this page is a summary. The source index records each file size and Git blob SHA.
