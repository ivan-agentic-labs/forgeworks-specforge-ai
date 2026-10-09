# SpecForge PostgreSQL runtime adapter

The runtime adapter uses the canonical MVP table names and separately applied migrations 001/002. Runtime logins must be non-owner members of the NOLOGIN/NOSUPERUSER/NOBYPASSRLS tenant role. Each outer transaction sets the role and tenant locally, closes its connection afterward, and takes a tenant advisory lock. Nested commands reuse that same transaction and cannot change tenant/store. This conservative serialization favors correctness for low-volume use; throughput and pooling are not accepted yet.

The idempotency response and its generated revision are committed in one database transaction. Composite tenant foreign keys and forced RLS remain database boundaries. Membership provisioning and migrations require a separate privileged role; the application cannot seed identities. SQLite is restricted to development/test.

The disposable CI proof covers source set, competing expected-version decisions, revision generation, job completion, traceability, approval, exact idempotency replay, actual API requests, quarantine, and negative SELECT/UPDATE/DELETE/INSERT tenant access. It does not establish real source extraction, storage scanning, IdP sessions, production operations, recovery or load acceptance. No design-candidate SQL file is applied.
