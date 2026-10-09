# SpecForge API disposable hardening slice

The FastAPI app now exercises the MVP workflow with a SQLite disposable store:

- optimistic ambiguity/revision approval versions with full stale invalidation;
- independent, pure OpenAPI semantic validation and canonical report digests;
- requirement-to-operation and acceptance-case traceability;
- artifact digest/object-generation records that remain quarantined without a configured scanner;
- durable job state, attempt counters, backoff timestamps, and terminal retry budgets.

Generated documents explicitly carry `x-deterministic-output: true` and
`x-generator: specforge-ai.deterministic.v1`. No paid provider or external
model is called. The PostgreSQL migration and storage/scanner integration remain
candidate/non-production evidence items; this is not a production-ready claim.
