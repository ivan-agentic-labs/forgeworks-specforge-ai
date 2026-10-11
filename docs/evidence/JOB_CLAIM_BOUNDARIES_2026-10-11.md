# Job claim boundaries — 2026-10-11

Baseline: 14ef654fac1d43308dde688518959a1939716f93.

The deterministic synchronous runner attempted a conditional PENDING/FAILED_RETRYABLE claim, but ignored its affected-row count and continued processing a RUNNING job. It also started another attempt after its persisted max_attempts was exhausted. Neither behavior is evidence of a production queue incident; this is the current fixture runner.

Only eligible states proceed. Existing RUNNING and terminal jobs return unchanged. Due work at its attempt limit becomes FAILED_TERMINAL with MAX_ATTEMPTS_EXCEEDED without increasing attempts or touching the revision. SQLite claim/processing now holds one write transaction across independent adapters; PostgreSQL retains its tenant-scoped transaction/advisory lock. Processing requires a successful conditional claim.

Initial nine-case regression suite: four failed, five passed. Failures reproduce RUNNING mutation and attempts incrementing beyond budget. Final ten-case suite additionally checks independent SQLite adapters consume only one attempt; terminal jobs and scheduled backoff stay unchanged. Dedicated native PostgreSQL proof adds unchanged RUNNING state, exhausted pending/retryable jobs, and concurrent successful processing that consumes one attempt against a valid generated revision.

Local validation: 236 Python tests pass, one native PostgreSQL proof skipped; 11 JavaScript tests pass. Bootstrap scan, static contracts, independent OpenAPI validation and whitespace checks pass. Three hosted workflows must pass before merge, including native PostgreSQL runtime/restore and generated SDK compilation.

Limits: synchronous deterministic fixture generation only. RUNNING crash recovery, lease/heartbeat ownership, late failure-report fencing and a distributed worker queue remain separate work. This change does not enable a real external generation provider or establish production readiness. No live migration or deployment is performed.
