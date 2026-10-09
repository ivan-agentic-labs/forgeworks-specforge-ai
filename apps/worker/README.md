# Worker boundary (not deployed)

The API's disposable store persists `PENDING`, `RUNNING`, `SUCCEEDED`,
`FAILED_RETRYABLE`, and `FAILED_TERMINAL` job states with optimistic
`state_version`, attempt counts, retry budget, next-attempt timestamps, and
error codes. `Store.run_job` and `Store.record_job_failure` are deterministic
test-harness transitions; they do not invoke a paid provider or external
side-effecting worker. A broker/outbox-backed worker still requires the G2/G4
permission, sandbox, crash-recovery, and PostgreSQL evidence gates.
