-- Reviewed engineering extension of the disposable MVP schema, not the design SQL candidates.
ALTER TABLE requirement_sets ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE requirements ADD COLUMN source_span text NOT NULL DEFAULT '';
ALTER TABLE requirements ADD COLUMN req_type text NOT NULL DEFAULT 'functional';
ALTER TABLE ambiguities ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE spec_revisions ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
CREATE TABLE memberships(tenant_id uuid NOT NULL REFERENCES tenants(id),user_id uuid NOT NULL,role text NOT NULL,status text NOT NULL,PRIMARY KEY(tenant_id,user_id));
CREATE TABLE idempotency_records(tenant_id uuid NOT NULL REFERENCES tenants(id),key text NOT NULL,request_hash char(64) NOT NULL,response_json jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(tenant_id,key));
CREATE ROLE fw_specforge_ai_rw NOLOGIN NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO fw_specforge_ai_rw;
DO $$
DECLARE tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['requirement_sets','requirements','ambiguities','spec_revisions','stakeholder_decisions','acceptance_cases','artifacts','jobs','memberships','idempotency_records']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tbl);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tbl);
    IF tbl IN ('ambiguities','memberships','idempotency_records') THEN
      EXECUTE format('CREATE POLICY tenant_boundary ON %I USING (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid) WITH CHECK (tenant_id=nullif(current_setting(''app.tenant_id'',true),'''')::uuid)',tbl);
    END IF;
    EXECUTE format('GRANT SELECT ON %I TO fw_specforge_ai_rw',tbl);
    IF tbl <> 'memberships' THEN
      EXECUTE format('GRANT INSERT,UPDATE,DELETE ON %I TO fw_specforge_ai_rw',tbl);
    END IF;
  END LOOP;
END $$;
