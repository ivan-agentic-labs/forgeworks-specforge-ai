# Explicit endpoint generation and output export — 2026-10-11

Implemented a separate deterministic source-declared endpoint profile and authenticated immutable OpenAPI export. Source method/path/status are preserved; unresolved natural-language declarations, duplicate operations and ambiguous path templates fail explicitly. Path parameter schemas remain unspecified and review-required. HEAD/OPTIONS/TRACE operations participate in traceability counts.

26 added regression cases cover all eight OpenAPI methods, strict syntax, source-to-output flow, replay, digest validation, independent OpenAPI validation, scope and cross-tenant denial, missing/tampered output and absence of partial revision/job writes.

Local complete suite: `python -W error -m pytest tests -q`: 169 passed, 1 skipped (PostgreSQL). Static contracts, independent OpenAPI contract validation and generated TypeScript compilation passed. Exact-commit GitHub Actions is authoritative for PostgreSQL and application CI. Full schema synthesis, natural-language/LLM generation, implementation tests and real stakeholder acceptance remain open.
