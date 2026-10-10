-- Query-constant tenant context; preserve same tenant_id equality and NULL denial.
-- Staging migration role search_path must be fw_specforge_ai,pg_catalog.
ALTER POLICY requirements_tenant ON requirements
  USING (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid)
  WITH CHECK (tenant_id = NULLIF((SELECT current_setting('app.tenant_id', true)), '')::uuid);
