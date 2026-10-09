-- Staging only: fresh private schema in the connected Supabase project.
-- Apply exactly once through the migration/provisioning role. Never at app startup.
CREATE SCHEMA fw_specforge_ai;
REVOKE ALL ON SCHEMA fw_specforge_ai FROM PUBLIC, anon, authenticated;
SET LOCAL search_path TO fw_specforge_ai, pg_catalog;
ALTER DEFAULT PRIVILEGES IN SCHEMA fw_specforge_ai REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA fw_specforge_ai REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated;
-- Source: 001_specforge_mvp.sql
-- SpecForge MVP disposable migration; review-only FK addendum is excluded.
-- Candidate only: platform tables, rollback, PostgreSQL evidence, and a
-- production object-store/scanner adapter are not claimed by this file.
CREATE TABLE IF NOT EXISTS tenants(id uuid PRIMARY KEY,slug text UNIQUE NOT NULL,status text NOT NULL);
CREATE TABLE IF NOT EXISTS requirement_sets(tenant_id uuid NOT NULL,id uuid NOT NULL,title text NOT NULL,source_version integer NOT NULL,source_digest char(64) NOT NULL,owner_id text NOT NULL,status text NOT NULL,PRIMARY KEY(tenant_id,id),FOREIGN KEY(tenant_id) REFERENCES tenants(id));
CREATE TABLE IF NOT EXISTS requirements(tenant_id uuid NOT NULL,id uuid NOT NULL,set_id uuid NOT NULL,statement text NOT NULL,provenance_digest char(64) NOT NULL,PRIMARY KEY(tenant_id,id),FOREIGN KEY(tenant_id,set_id) REFERENCES requirement_sets(tenant_id,id));
CREATE TABLE IF NOT EXISTS ambiguities(tenant_id uuid NOT NULL,id uuid NOT NULL,requirement_id uuid NOT NULL,severity text NOT NULL,question text NOT NULL,status text NOT NULL,PRIMARY KEY(tenant_id,id),FOREIGN KEY(tenant_id,requirement_id) REFERENCES requirements(tenant_id,id));
CREATE TABLE IF NOT EXISTS spec_revisions(tenant_id uuid NOT NULL,id uuid NOT NULL,set_id uuid NOT NULL,source_version integer NOT NULL,status text NOT NULL,spec_json jsonb NOT NULL,spec_sha char(64) NOT NULL,version integer NOT NULL DEFAULT 1,PRIMARY KEY(tenant_id,id),FOREIGN KEY(tenant_id,set_id) REFERENCES requirement_sets(tenant_id,id));
CREATE TABLE IF NOT EXISTS stakeholder_decisions(tenant_id uuid NOT NULL,id uuid NOT NULL,ambiguity_id uuid NOT NULL,actor_id uuid NOT NULL,decision_hash char(64) NOT NULL,source_reference text NOT NULL,decision_text text NOT NULL,version integer NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(tenant_id,id),UNIQUE(tenant_id,ambiguity_id,version),FOREIGN KEY(tenant_id,ambiguity_id) REFERENCES ambiguities(tenant_id,id));
CREATE TABLE IF NOT EXISTS acceptance_cases(tenant_id uuid NOT NULL,id uuid NOT NULL,revision_id uuid NOT NULL,requirement_id uuid NOT NULL,case_key text NOT NULL,description text NOT NULL,status text NOT NULL,PRIMARY KEY(tenant_id,id),UNIQUE(tenant_id,revision_id,requirement_id),FOREIGN KEY(tenant_id,revision_id) REFERENCES spec_revisions(tenant_id,id),FOREIGN KEY(tenant_id,requirement_id) REFERENCES requirements(tenant_id,id));
CREATE TABLE IF NOT EXISTS artifacts(tenant_id uuid NOT NULL,id uuid NOT NULL,kind text NOT NULL,filename text NOT NULL,declared_media_type text,sha256 char(64) NOT NULL,size_bytes bigint NOT NULL,status text NOT NULL,object_generation text,created_at timestamptz NOT NULL DEFAULT now(),expires_at timestamptz,rejected_reason text,PRIMARY KEY(tenant_id,id));
CREATE TABLE IF NOT EXISTS jobs(tenant_id uuid NOT NULL,id uuid NOT NULL,revision_id uuid NOT NULL,state text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),state_version integer NOT NULL DEFAULT 1,attempt_count integer NOT NULL DEFAULT 0,max_attempts integer NOT NULL DEFAULT 3,next_attempt_at timestamptz,last_error_code text,last_error_message text,updated_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(tenant_id,id),FOREIGN KEY(tenant_id,revision_id) REFERENCES spec_revisions(tenant_id,id));
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS source_decision_digest char(64) NOT NULL DEFAULT repeat('0',64);
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS validator_report_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS validator_report_sha char(64) NOT NULL DEFAULT repeat('0',64);
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS traceability_report_json jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS traceability_report_sha char(64) NOT NULL DEFAULT repeat('0',64);
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS stale_reason text;
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS approved_at timestamptz;
ALTER TABLE spec_revisions ADD COLUMN IF NOT EXISTS approver_id uuid;
ALTER TABLE requirement_sets ENABLE ROW LEVEL SECURITY;ALTER TABLE requirements ENABLE ROW LEVEL SECURITY;ALTER TABLE spec_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholder_decisions ENABLE ROW LEVEL SECURITY;ALTER TABLE acceptance_cases ENABLE ROW LEVEL SECURITY;ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY requirement_sets_tenant ON requirement_sets USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY requirements_tenant ON requirements USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY spec_revisions_tenant ON spec_revisions USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY stakeholder_decisions_tenant ON stakeholder_decisions USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY acceptance_cases_tenant ON acceptance_cases USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY artifacts_tenant ON artifacts USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);
CREATE POLICY jobs_tenant ON jobs USING(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid) WITH CHECK(tenant_id=nullif(current_setting('app.tenant_id',true),'')::uuid);

-- Source: 002_specforge_runtime.sql
-- Reviewed engineering extension of the disposable MVP schema, not the design SQL candidates.
ALTER TABLE requirement_sets ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE requirements ADD COLUMN source_span text NOT NULL DEFAULT '';
ALTER TABLE requirements ADD COLUMN req_type text NOT NULL DEFAULT 'functional';
ALTER TABLE ambiguities ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE spec_revisions ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
CREATE TABLE memberships(tenant_id uuid NOT NULL REFERENCES tenants(id),user_id uuid NOT NULL,role text NOT NULL,status text NOT NULL,PRIMARY KEY(tenant_id,user_id));
CREATE TABLE idempotency_records(tenant_id uuid NOT NULL REFERENCES tenants(id),key text NOT NULL,request_hash char(64) NOT NULL,response_json jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(tenant_id,key));
CREATE ROLE fw_specforge_ai_rw NOLOGIN NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA fw_specforge_ai TO fw_specforge_ai_rw;
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

-- Auth-managed tables remain untouched. Return only a boolean for the JWT-bound user.
CREATE FUNCTION fw_specforge_ai.session_active(session_id uuid, user_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
 SELECT auth.uid() = $2 AND EXISTS (
   SELECT 1 FROM auth.sessions s JOIN auth.users u ON u.id=s.user_id
   WHERE s.id=$1 AND s.user_id=$2
     AND (s.not_after IS NULL OR s.not_after > now())
     AND u.deleted_at IS NULL AND (u.banned_until IS NULL OR u.banned_until <= now())
 );
$$;
REVOKE ALL ON FUNCTION fw_specforge_ai.session_active(uuid, uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION fw_specforge_ai.session_active(uuid, uuid) TO fw_specforge_ai_rw;
GRANT USAGE ON SCHEMA fw_specforge_ai TO fw_specforge_ai_rw;
-- Restrict all product tables, including unexposed tenants, as defense in depth.
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='fw_specforge_ai' LOOP
   EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY','fw_specforge_ai',t.tablename);
   EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY','fw_specforge_ai',t.tablename);
   EXECUTE format('REVOKE ALL ON %I.%I FROM PUBLIC, anon, authenticated','fw_specforge_ai',t.tablename);
 END LOOP;
END $$;
RESET search_path;
