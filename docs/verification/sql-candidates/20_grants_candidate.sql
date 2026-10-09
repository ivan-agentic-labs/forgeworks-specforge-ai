-- DESIGN CANDIDATE FOR DISPOSABLE PROOF ONLY.
-- Privileges apply exclusively to tenant-scoped tables protected by RLS.
-- Keep global `tenants` and `users` restricted to a separately audited provisioning path.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE acceptance_cases TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE artifact_references TO fw_specforge_ai_rw;
-- Audit events: append-only for application role, no direct update/delete.
REVOKE ALL ON TABLE audit_events FROM PUBLIC;
REVOKE UPDATE, DELETE ON TABLE audit_events FROM fw_specforge_ai_rw;
GRANT SELECT, INSERT ON TABLE audit_events TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE idempotency_records TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE inbox_receipts TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE jobs TO fw_specforge_ai_rw;
-- G1-D conditional restriction: membership writes disabled for generic app role.
-- Identity/admin provisioning service requires a separate reviewed role and authz gate.
REVOKE INSERT, UPDATE, DELETE ON TABLE memberships FROM fw_specforge_ai_rw;
GRANT SELECT ON TABLE memberships TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE operations TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE outbox_events TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE requirement_sets TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE requirements TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE source_documents TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE spec_revisions TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE ambiguities TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE trace_links TO fw_specforge_ai_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE stakeholder_decisions TO fw_specforge_ai_rw;

-- Global identity tables must not be readable via PUBLIC (disposable-proof safeguard).
REVOKE ALL ON TABLE users, tenants FROM PUBLIC;
