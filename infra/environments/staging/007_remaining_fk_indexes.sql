-- Additive FK lookup indexes for this product's small staging tables.
-- Apply after bootstrap and prior numbered staging migrations, in one transaction
-- with search_path set to the product schema, pg_catalog. Fail on lock contention.
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '30s';
CREATE INDEX IF NOT EXISTS idx_acceptance_cases_tenant_requirement ON acceptance_cases (tenant_id, requirement_id);
CREATE INDEX IF NOT EXISTS idx_ambiguities_tenant_requirement ON ambiguities (tenant_id, requirement_id);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_revision ON jobs (tenant_id, revision_id);
CREATE INDEX IF NOT EXISTS idx_spec_revisions_tenant_set ON spec_revisions (tenant_id, set_id);
