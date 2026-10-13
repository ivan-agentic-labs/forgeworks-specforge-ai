# SpecForge AI — Complete Project Specification

**Document type:** Canonical product, architecture, implementation, verification, and operations specification  
**Version:** 2.2.0-detailed-full  
**Date:** 2026-10-13  
**Status:** FINAL  
**Product family:** ForgeWorks AI  

> SpecForge AI turns approved requirement sets into versioned, traceable OpenAPI contracts and acceptance tests. It does not invent business rules. Critical ambiguities block publication.

This document is self-contained and intentionally detailed.

---

## 1. Executive Product Definition

SpecForge AI helps product managers and engineering leads convert structured requirements into reviewable API contracts. The system extracts requirements from source documents, surfaces ambiguities, requires human decisions on critical points, generates an OpenAPI revision, validates it deterministically, calculates traceability, and only allows publication when all gates pass.

The core promise is traceability and safety: every published operation can be traced to a confirmed requirement or an explicit decision, and no critical ambiguity remains open at publish time.

---

## 2. Goals and Non-Goals

**Goals**
- Produce valid OpenAPI 3.1 revisions from confirmed requirements only.
- Make ambiguities visible and require resolution for critical items.
- Maintain requirement → operation/schema → test case traceability.
- Block publication when coverage or validation fails.
- Keep full evidence of decisions and approvals.

**Non-Goals**
- Does not decide business policy.
- Does not generate a running application.
- Does not publish contracts with open critical ambiguities.
- Does not claim that all requirements have been implemented in code.

---

## 3. Target Users

- Product managers who need to turn written requirements into API contracts.
- Tech leads who review and approve specifications.
- Engineering teams who consume the published OpenAPI.

---

## 4. Detailed End-to-End Workflow

1. User imports a RequirementSet (documents + optional glossary).
2. System stores originals immutably and computes digests.
3. Extraction produces Requirement records, each with a source span. Missing spans create Ambiguities.
4. Ambiguity Register is built and classified by severity.
5. Critical ambiguities are routed to stakeholders. They remain open until a Decision is recorded.
6. Medium/low ambiguities may be waived with reason and optional expiry.
7. Generator produces an OpenAPI revision using only confirmed requirements and closed decisions.
8. Deterministic validator checks syntax and semantic rules (no invented paths, no orphan schemas, security declared, glossary compliance).
9. Traceability engine calculates coverage.
10. Test cases are derived and linked.
11. Reviewer sees semantic diff, coverage, open ambiguities, and glossary warnings.
12. Approval is bound to the exact SpecRevision digest.
13. Publish gate enforces all conditions server-side.
14. Evidence bundle is stored and can be exported.

Any change to requirements, decisions, or generated content creates a new digest and invalidates prior approval. RequirementSet version updates mark dependent revisions as stale; regeneration is explicit and full.

---

## 5. Domain Model (Expanded)

**RequirementSet**  
Immutable version of imported documents. Fields: id, version, source_digests, glossary_version, created_at.

**Requirement**  
Extracted item. Fields: id, requirement_set_id, source_span, statement, type, status (draft/confirmed/rejected), confidence, extracted_by.

**Ambiguity**  
Open question. Fields: id, requirement_ids, severity (critical/high/medium/low), category, question, options, status (open/resolved/waived), decision_id.

**Decision**  
Human resolution. Fields: id, ambiguity_id, chosen_option, rationale, actor_id, decided_at, digest.

**SpecRevision**  
Generated contract. Fields: id, requirement_set_version, openapi_content, digest, parent_digest, validation_results, coverage, status.

**Approval**  
Binds to digest. Fields: id, spec_revision_id, actor_id, digest, decided_at, expires_at.

**TraceLink**  
requirement_id → operation / schema / test_case_id.

---

## 6. Ambiguity and Decision Rules (Detailed)

Critical categories (missing endpoint, auth model, data ownership, breaking change) always block publish.  
Waiver is allowed only for medium and low. Waiver record includes reason, actor, and optional expiry. Expired waivers reopen the ambiguity.  
Changing a Decision invalidates dependent SpecRevisions.

Stakeholder routing: DecisionRequest is created, visible in UI, and can notify via configured channel. Reminder at day 3 and day 6. Timeout does not auto-resolve; publish remains blocked.

---

## 7. Generation and Validation (Detailed)

The model may propose structure. The deterministic validator rejects:
- Paths or operations without a requirement link or explicit decision.
- Orphan schemas.
- Missing security schemes when operations require auth.
- Glossary violations.

Semantic diff is code-generated and includes added/removed/modified paths, schema changes, security changes, and a breaking-change flag.

Canonical digest uses sorted keys, compact JSON, preserved array order, and null inclusion.

---

## 8. Traceability and Publish Gate

Coverage formula:
- operations_with_link / total_operations
- requirements_with_operation_or_deferral / total_confirmed_requirements

Default threshold 95%. Critical requirements require 100%.

Publish allowed only if:
- critical_ambiguities_open == 0
- both coverage numbers ≥ threshold
- validation passed
- valid approval matching current digest
- approval not expired

---

## 9. Evidence, Retention, and Errors

Evidence bundle contains source digests, ambiguity register + decisions/waivers, SpecRevision digest, validation results, coverage, approval, and published artifact hash. Retained minimum 2 years.

Error classes include semantic.validation_failed, glossary.conflict, coverage.below_threshold, validator.tool_error (retryable), stale.revision.

---

## 10. Testing Catalogue (Expanded)

TEST-SF-001 through TEST-SF-022 as previously defined, plus:
- Canonical digest stability
- Glossary conflict creates Ambiguity
- Stale revision cannot be published
- Server-side publish gate enforcement

---

## 11. Implementation Notes

- All digests use canonical JSON.
- OpenAPI generation runs in a bounded worker.
- Glossary checker is deterministic.
- Publish and approval write to append-only audit log.
- UI must display diff, coverage, open ambiguities, and digest before enabling approval.

---

## 12. Closing

This specification locks SpecForge AI P0. No critical ambiguity may remain open at publication. All contracts are traceable. The model proposes; deterministic validation and human approval enforce correctness.

*End of SpecForge AI Complete Detailed Specification*


## 13. Extended Domain Rules and Invariants

DB-INV-SF-001: Every Requirement must reference a valid RequirementSet version.  
DB-INV-SF-002: A SpecRevision digest must change if any confirmed requirement, decision, or generated content changes.  
DB-INV-SF-003: An Approval is invalid if its digest does not match the current SpecRevision digest.  
DB-INV-SF-004: Critical Ambiguity with status open blocks any publish attempt at the database or service layer.  
DB-INV-SF-005: Waived Ambiguity must record actor, reason, and timestamp.  
DB-INV-SF-006: Glossary version is immutable per RequirementSet version.

## 14. State Machines

**SpecRevision states:** draft → validated → approval_pending → approved → published / rejected / stale.  
Forbidden: approved → published if critical ambiguities > 0 or coverage below threshold.  
Forbidden: stale → published.

**Ambiguity states:** open → resolved / waived.  
Critical cannot transition to waived.

## 15. Semantic Validation Rules (Exhaustive)

- Every path item must contain at least one operation linked to a requirement or decision.  
- Every $ref must resolve inside the document.  
- Security schemes referenced by operations must be defined.  
- OperationId must be unique.  
- Glossary preferred names must be used for new path segments unless an approved synonym exists.  
- No operation may be added that lacks a TraceLink.

## 16. Example Full OpenAPI Fragment with Traceability

```yaml
paths:
  /orders:
    post:
      operationId: createOrder
      x-trace-requirements: ["req_12", "req_15"]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OrderCreate'
```

Corresponding TraceLink records must exist for req_12 and req_15.

## 17. Stakeholder and DecisionRequest Detail

DecisionRequest contains ambiguity_id, assigned stakeholders, created_at, reminders_sent, and status.  
If the assigned stakeholder has no activity for 30 days, org_admin is added automatically.  
Resolution creates a Decision record and closes the Ambiguity.

## 18. Regeneration and Staleness Detail

When a new RequirementSet version is imported:  
- All SpecRevisions bound to the previous version are marked stale.  
- Stale revisions remain readable for audit.  
- User must call the regenerate endpoint.  
- Regeneration produces a new SpecRevision with a new digest and parent_digest pointing to the previous one.  
- Previous approval is not carried forward.

## 19. Error Catalogue (Expanded)

| Code | HTTP | Retryable | User action |
|------|------|-----------|-------------|
| semantic.validation_failed | 422 | No | Fix requirements or decisions |
| glossary.conflict | 422 | No | Resolve glossary Ambiguity |
| coverage.below_threshold | 422 | No | Add links or defer with reason |
| stale.revision | 409 | No | Regenerate |
| approval.digest_mismatch | 409 | No | Re-approve |
| validator.tool_error | 503 | Yes | Retry later |

## 20. Implementation Records Style (Sample)

### IR-SF-001 — Requirement import and hashing
Required behavior: Store original bytes, compute SHA-256, reject duplicate identical imports within the same workspace unless forced.  
Negative: cross-tenant access, missing file, hash collision handling.

### IR-SF-002 — Ambiguity creation from low-confidence extraction
Required behavior: Any extraction with confidence=low or missing source_span creates an Ambiguity automatically.

(Additional IR records follow the same pattern for generation, validation, approval, publish, and evidence export.)

## 21. Operational Questions Answered

- Timeout for generation worker: 10 minutes.  
- Retry for validator.tool_error: 3 times with backoff.  
- Retention: 2 years minimum for SpecRevision and Approval.  
- Who can approve: reviewer role or designated stakeholder.  
- Alert: publish_gate_failure rate > 5% over 1 hour.

## 22. Appendix — Review Protocol

Reviewer checks: product boundary, one full trace from RequirementSet to published artifact, negative cases (cross-tenant, stale approval, invented path), and evidence completeness.

*End of extended SpecForge sections*
