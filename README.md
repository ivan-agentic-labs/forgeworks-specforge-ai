# SpecForge AI

> **Turn documented requirements into reviewable API specifications.**

Part of **ForgeWorks**, a collection of five complementary API services for software engineering and operations.

## What the product does

SpecForge AI helps teams move from written requirements to an auditable API contract. It preserves source provenance, exposes ambiguous requirements for stakeholder decisions, and generates reviewable OpenAPI revisions from explicit inputs.

**Who uses it:** Product analysts, system analysts, product managers, and engineering leads.

## Capabilities and outputs

| Capability | Input / action | Output |
| --- | --- | --- |
| Requirement ingestion | Bounded local UTF-8 source documents | Recorded source content, integrity checks, and provenance |
| Ambiguity handling | Requirement statements needing interpretation | Reviewable ambiguity items and stakeholder decisions |
| Contract generation | Approved explicit requirements and source-declared HTTP operations | Deterministic OpenAPI revision |
| Traceability and approval | Source versions, decisions, and proposed contract | Digest/version-bound review and approval records |

## Example workflow

1. Ingest a supported requirements source.
2. Review provenance and resolve ambiguities with a stakeholder decision.
3. Generate a contract revision from the decided requirements.
4. Inspect traceability and use version-bound approvals for downstream implementation.

**What a team gets:** explicit inputs, a repeatable processing path, and inspectable outputs for review. A local review console exposes provenance, ambiguities, traceability, and approval information.

## Technical design

- **API:** Python service with versioned REST/OpenAPI contracts and structured error handling.
- **Data:** PostgreSQL domain adapter and tenant-scoped data access controls.
- **Auth:** explicit development authentication for local use; never reuse local keys or sample identities on hosted infrastructure.
- **Verification:** automated code tests, contract checks, and scoped evidence documents. Their meaning is limited to the scenarios they exercised.

## Run locally

Install Python and the runtime/test dependencies from the repository root:

```bash
python -m pip install --require-hashes -r requirements-runtime.lock
python -m pip install -e 'apps/api[test]' -r scripts/requirements-verification.txt
export APP_ENV=development AUTH_MODE=development
export AUTH_ISSUER=https://issuer.synthetic.invalid AUTH_AUDIENCE=forgeworks-api
export DEV_AUTH_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ARTIFACT_SIGNING_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python scripts/development_token.py
SPECFORGE_SEED_FIXTURE=1 PYTHONPATH=apps/api/src uvicorn specforge_ai.main:app --reload
```

The generated token is short-lived and is only for local development with synthetic data. To run the test suite, use `python -W error -m pytest tests` with the same explicit development environment.

## API and technical references

- [Product scope](docs/product/PRODUCT_SCOPE.md)
- [Architecture](docs/architecture/)
- [OpenAPI contract](contracts/openapi.yaml) and [event schemas](contracts/events.schema.json)
- [Verification evidence](docs/verification/CURRENT_GATE_EVIDENCE.md)
- [Release verification runbook](ops/runbooks/RUNTIME_RELEASE_VERIFICATION.md)
- [One-app / five-services design](docs/platform/ONE_APP_FIVE_SERVICES.md)

## ForgeWorks service family

- [APIShield Agent](https://github.com/ivan-agentic-labs/forgeworks-apishield-agent) · API contract-change analysis
- [AccessFix AI](https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai) · accessibility review
- [SpecForge AI](https://github.com/ivan-agentic-labs/forgeworks-specforge-ai) · requirements-to-API contracts
- [AgentTest Lab](https://github.com/ivan-agentic-labs/forgeworks-agenttest-lab) · AI agent evaluation
- [DataReconcile AI](https://github.com/ivan-agentic-labs/forgeworks-datareconcile-ai) · reconciliation and exceptions

The services have separate repositories and explicit interfaces. A single customer-facing ForgeWorks portal is an architectural direction, not a claim of independently verified live integration.

## Usage boundary

This workflow does not invent missing stakeholder decisions. Source handling is bounded and local; enterprise document retention, external integrations, and hosted customer acceptance are separate from the source-level contract workflow. Consult the linked evidence register and runbook before claiming customer-level or production acceptance.
