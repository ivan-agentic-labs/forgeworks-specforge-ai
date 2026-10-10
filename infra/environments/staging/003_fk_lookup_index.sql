-- Additive index for requirements by requirement set. Apply with the migration role and
-- search_path set to fw_specforge_ai, pg_catalog (never the runtime role).
CREATE INDEX IF NOT EXISTS idx_requirements_tenant_set ON requirements (tenant_id, set_id);
