# SpecForge AI — P0 Product Requirements & Scope

**Target buyer:** Product manager, tech lead, software house.

**Measurable user promise:** Mengubah kebutuhan yang disetujui menjadi kontrak API dan test cases yang dapat dilacak ke sumbernya, tanpa mengarang keputusan bisnis.

## P0 end-to-end workflow
Requirement set → versioned source extraction → taxonomy & ambiguity register → stakeholder decisions → spec revision generation → OAS validation & semantic diff → traceability coverage → reviewer approval → publish version.

## Included in P0
- Requirement teks terstruktur berbahasa Indonesia/Inggris
- Satu service REST berbasis OpenAPI 3.1.x
- Ambiguity workflow dengan keputusan manusia
- Traceability requirement → operation/schema → test case

## Explicitly out of scope
- Otomatis menentukan kebijakan bisnis tanpa stakeholder
- Generate entire running application
- Menerbitkan versi kontrak dengan ambiguitas kritis terbuka
- Klaim semua requirement telah terimplementasi

## Roles & permission model
- `org_owner`: billing, org settings, members, quotas; does not automatically grant bypass to data policy.
- `org_admin`: invites within same tenant, configures allowed integrations, reviews impact.
- `editor`: creates runs/imports/draft analyses, cannot approve their own high-impact external write if separation-of-duty policy enables it.
- `reviewer`: approves signed revision/digest within policy and time window.
- `auditor`: read-only access to redacted audit + evidence.
- `service_worker`: machine identity with narrowly scoped effect grants, never unrestricted user impersonation; the BFF carries verified user access claims server-side.

## Product value and validation
Business hypothesis: targeted buyer experiences frequent repeatable failure that is expensive enough to justify adoption. Evidence needed: 3–5 structured buyer interviews, their current workaround, time/expense per incident, willingness to share consented/synthetic fixtures, and pilot pass criteria. These are **future prerequisites**, not interviews already done.

**North-star and guardrail metrics:** requirement-to-operation provenance coverage, critical ambiguity unresolved at publish = 0, reviewed OpenAPI validation pass rate, incorrect invented requirements on adjudicated set, time-to-reviewed-contract.

## P0 completion criteria
1. One authorized end-to-end job reaches its intended output with reproducible fixture and trace.
2. Duplicate requests / partial external timeout / revocation / cross-tenant access fail safely.
3. Every material output cites a source/digest/rule version and has a reviewer action where needed.
4. Evidence of output correctness must come from deterministic assertion and human review of edge cases; AI alone does not sign off.
5. Security, privacy, budget, and recovery gate conditions defined in governance are respected.

## Critical G1 assumptions pending
- Requirement taxonomy and completeness protocol require buyer signoff
- Semantic validator/toolchain must be selected with fixtures
- Reviewer-defined semantic correctness baseline required

**Scope owner:** Founder/Product. **Security owner:** assigned reviewer. **Domain validator:** qualified buyer/SME. **Status:** PROVISIONAL, awaiting actual signed reviews.
