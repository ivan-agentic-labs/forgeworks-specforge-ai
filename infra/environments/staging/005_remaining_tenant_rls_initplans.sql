-- Existing nine tenant equality ALL / TO PUBLIC policies, no new grants.
-- Run in migration session with search_path=fw_specforge_ai,pg_catalog.
ALTER POLICY acceptance_cases_tenant ON acceptance_cases USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON ambiguities USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY artifacts_tenant ON artifacts USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON idempotency_records USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY jobs_tenant ON jobs USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY tenant_boundary ON memberships USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY requirement_sets_tenant ON requirement_sets USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY spec_revisions_tenant ON spec_revisions USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
ALTER POLICY stakeholder_decisions_tenant ON stakeholder_decisions USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid) WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
