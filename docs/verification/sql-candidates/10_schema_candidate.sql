-- REVIEW CANDIDATE ONLY. SQLAlchemy PostgreSQL dialect compilation, NO live PostgreSQL.
-- NOT APPROVED AS EXECUTABLE MIGRATION. fw_specforge_ai_rw must be created with NOLOGIN,
-- checked grants and no table ownership or BYPASSRLS. A distinct migration
-- owner deploys schema. API service must authenticate membership, set SET LOCAL
-- app.tenant_id within transaction, and never pass SQL through to users.
-- Global tenants/users need dedicated authorization rules (not generic RLS).
-- No automatic fw_specforge_ai_rw GRANT is provided; least-privilege permissions undecided.
-- Audit events require retention controls and legal review.
-- PostgreSQL version/vendor and migration ordering are not yet approved.

CREATE TABLE tenants (
	id UUID NOT NULL, 
	slug TEXT NOT NULL, 
	status TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
)

;


CREATE TABLE users (
	id UUID NOT NULL, 
	issuer TEXT NOT NULL, 
	subject TEXT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_users_issuer_sub UNIQUE (issuer, subject)
)

;


CREATE TABLE acceptance_cases (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	spec_revision_id UUID NOT NULL, 
	requirement_id UUID NOT NULL, 
	case_key TEXT NOT NULL, 
	assertions_json JSONB NOT NULL, 
	status TEXT NOT NULL, 
	CONSTRAINT pk_acceptance_cases_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_acceptance_cases_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_acceptance_cases_tenant_id_spec_revision_id_case_key UNIQUE (tenant_id, spec_revision_id, case_key)
)

;


CREATE TABLE artifact_references (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	object_key TEXT NOT NULL, 
	sha256 CHAR(64) NOT NULL, 
	media_type TEXT NOT NULL, 
	status TEXT NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_artifact_references PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_artifact_references_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_artifact_key UNIQUE (tenant_id, object_key)
)

;


CREATE TABLE audit_events (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	actor_key TEXT NOT NULL, 
	action TEXT NOT NULL, 
	resource_key TEXT NOT NULL, 
	data_class TEXT NOT NULL, 
	trace_id TEXT, 
	payload JSONB NOT NULL, 
	CONSTRAINT pk_audit_events PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_audit_events_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE idempotency_records (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	actor_key TEXT NOT NULL, 
	command_name TEXT NOT NULL, 
	idempotency_key TEXT NOT NULL, 
	request_sha256 CHAR(64) NOT NULL, 
	response_status INTEGER, 
	response_json JSONB, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_idempotency_records PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_idempotency_records_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_idempotency_scope UNIQUE (tenant_id, actor_key, command_name, idempotency_key)
)

;


CREATE TABLE inbox_receipts (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	consumer_name TEXT NOT NULL, 
	event_key TEXT NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	CONSTRAINT pk_inbox_receipts PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_inbox_receipts_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_inbox_dedupe UNIQUE (tenant_id, consumer_name, event_key)
)

;


CREATE TABLE jobs (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	kind TEXT NOT NULL, 
	status TEXT NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	created_by UUID, 
	CONSTRAINT pk_jobs PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_jobs_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE memberships (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	user_id UUID NOT NULL, 
	role TEXT NOT NULL, 
	status TEXT NOT NULL, 
	CONSTRAINT pk_memberships PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_memberships_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_memberships_user FOREIGN KEY(user_id) REFERENCES users (id), 
	CONSTRAINT uq_memberships_user UNIQUE (tenant_id, user_id)
)

;


CREATE TABLE operations (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	spec_revision_id UUID NOT NULL, 
	operation_key TEXT NOT NULL, 
	http_method TEXT NOT NULL, 
	path_template TEXT NOT NULL, 
	source_decision_id UUID, 
	approval_status TEXT NOT NULL, 
	CONSTRAINT pk_operations_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_operations_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_operations_tenant_id_spec_revision_id_http_method__1d42c50a UNIQUE (tenant_id, spec_revision_id, http_method, path_template)
)

;


CREATE TABLE outbox_events (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	event_type TEXT NOT NULL, 
	event_version INTEGER DEFAULT 1 NOT NULL, 
	payload JSONB NOT NULL, 
	event_key TEXT NOT NULL, 
	delivered_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_outbox_events PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_outbox_events_tenant FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT uq_outbox_key UNIQUE (tenant_id, event_key)
)

;


CREATE TABLE requirement_sets (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	title TEXT NOT NULL, 
	owner_id UUID NOT NULL, 
	current_version INTEGER NOT NULL, 
	status TEXT NOT NULL, 
	CONSTRAINT pk_requirement_sets_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_requirement_sets_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id)
)

;


CREATE TABLE requirements (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	set_id UUID NOT NULL, 
	source_version INTEGER NOT NULL, 
	source_span TEXT NOT NULL, 
	statement TEXT NOT NULL, 
	provenance_hash CHAR(64) NOT NULL, 
	CONSTRAINT pk_requirements_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_requirements_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_requirements_tenant_id_set_id FOREIGN KEY(tenant_id, set_id) REFERENCES requirement_sets (tenant_id, id), 
	CONSTRAINT uq_requirements_tenant_id_set_id_source_version_provenance_hash UNIQUE (tenant_id, set_id, source_version, provenance_hash)
)

;


CREATE TABLE source_documents (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	set_id UUID NOT NULL, 
	source_version INTEGER NOT NULL, 
	sha256 CHAR(64) NOT NULL, 
	artifact_key TEXT NOT NULL, 
	format TEXT NOT NULL, 
	CONSTRAINT pk_source_documents_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_source_documents_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_source_documents_tenant_id_set_id FOREIGN KEY(tenant_id, set_id) REFERENCES requirement_sets (tenant_id, id), 
	CONSTRAINT uq_source_documents_tenant_id_set_id_source_version UNIQUE (tenant_id, set_id, source_version)
)

;


CREATE TABLE spec_revisions (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	set_id UUID NOT NULL, 
	source_version INTEGER NOT NULL, 
	content_sha256 CHAR(64) NOT NULL, 
	validation_state TEXT NOT NULL, 
	artifact_key TEXT NOT NULL, 
	approved_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_spec_revisions_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_spec_revisions_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_spec_revisions_tenant_id_set_id FOREIGN KEY(tenant_id, set_id) REFERENCES requirement_sets (tenant_id, id), 
	CONSTRAINT uq_spec_revisions_tenant_id_set_id_content_sha256 UNIQUE (tenant_id, set_id, content_sha256)
)

;


CREATE TABLE ambiguities (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	requirement_id UUID NOT NULL, 
	severity TEXT NOT NULL, 
	question TEXT NOT NULL, 
	status TEXT NOT NULL, 
	CONSTRAINT pk_ambiguities_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_ambiguities_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_ambiguities_tenant_id_requirement_id FOREIGN KEY(tenant_id, requirement_id) REFERENCES requirements (tenant_id, id)
)

;


CREATE TABLE trace_links (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	revision_id UUID NOT NULL, 
	requirement_id UUID NOT NULL, 
	operation_id UUID NOT NULL, 
	test_case_id UUID, 
	CONSTRAINT pk_trace_links_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_trace_links_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_trace_links_tenant_id_revision_id FOREIGN KEY(tenant_id, revision_id) REFERENCES spec_revisions (tenant_id, id), 
	CONSTRAINT fk_trace_links_tenant_id_requirement_id FOREIGN KEY(tenant_id, requirement_id) REFERENCES requirements (tenant_id, id), 
	CONSTRAINT fk_trace_links_tenant_id_operation_id FOREIGN KEY(tenant_id, operation_id) REFERENCES operations (tenant_id, id), 
	CONSTRAINT fk_trace_links_tenant_id_test_case_id FOREIGN KEY(tenant_id, test_case_id) REFERENCES acceptance_cases (tenant_id, id), 
	CONSTRAINT uq_trace_links_tenant_id_revision_id_requirement_id_o_6ec415d1 UNIQUE (tenant_id, revision_id, requirement_id, operation_id)
)

;


CREATE TABLE stakeholder_decisions (
	tenant_id UUID NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	ambiguity_id UUID NOT NULL, 
	actor_id UUID NOT NULL, 
	decision_hash CHAR(64) NOT NULL, 
	decision_artifact_key TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	CONSTRAINT pk_stakeholder_decisions_tenant_id_id PRIMARY KEY (tenant_id, id), 
	CONSTRAINT fk_stakeholder_decisions_tenant_id FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	CONSTRAINT fk_stakeholder_decisions_tenant_id_ambiguity_id FOREIGN KEY(tenant_id, ambiguity_id) REFERENCES ambiguities (tenant_id, id), 
	CONSTRAINT uq_stakeholder_decisions_tenant_id_ambiguity_id_version UNIQUE (tenant_id, ambiguity_id, version)
)

;

-- INDEXES
CREATE INDEX ix_requirement_sets_tenant_id_owner_id ON requirement_sets (tenant_id, owner_id);
CREATE INDEX ix_ambiguities_tenant_id_status_severity ON ambiguities (tenant_id, status, severity);

-- RLS POLICIES (candidate, role not yet provisioned)
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY p_memberships_tenant ON memberships FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY p_jobs_tenant ON jobs FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events FORCE ROW LEVEL SECURITY;
CREATE POLICY p_outbox_events_tenant ON outbox_events FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE inbox_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY p_inbox_receipts_tenant ON inbox_receipts FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE idempotency_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_records FORCE ROW LEVEL SECURITY;
CREATE POLICY p_idempotency_records_tenant ON idempotency_records FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events FORCE ROW LEVEL SECURITY;
-- Audit is append-only for the application role; owner/retention procedure is separate.
CREATE POLICY p_audit_events_read ON audit_events FOR SELECT TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY p_audit_events_append ON audit_events FOR INSERT TO fw_specforge_ai_rw WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE artifact_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifact_references FORCE ROW LEVEL SECURITY;
CREATE POLICY p_artifact_references_tenant ON artifact_references FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE requirement_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirement_sets FORCE ROW LEVEL SECURITY;
CREATE POLICY p_requirement_sets_tenant ON requirement_sets FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_documents FORCE ROW LEVEL SECURITY;
CREATE POLICY p_source_documents_tenant ON source_documents FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirements FORCE ROW LEVEL SECURITY;
CREATE POLICY p_requirements_tenant ON requirements FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE ambiguities ENABLE ROW LEVEL SECURITY;
ALTER TABLE ambiguities FORCE ROW LEVEL SECURITY;
CREATE POLICY p_ambiguities_tenant ON ambiguities FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE stakeholder_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE stakeholder_decisions FORCE ROW LEVEL SECURITY;
CREATE POLICY p_stakeholder_decisions_tenant ON stakeholder_decisions FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE spec_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE spec_revisions FORCE ROW LEVEL SECURITY;
CREATE POLICY p_spec_revisions_tenant ON spec_revisions FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE trace_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE trace_links FORCE ROW LEVEL SECURITY;
CREATE POLICY p_trace_links_tenant ON trace_links FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations FORCE ROW LEVEL SECURITY;
CREATE POLICY p_operations_tenant ON operations FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
ALTER TABLE acceptance_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE acceptance_cases FORCE ROW LEVEL SECURITY;
CREATE POLICY p_acceptance_cases_tenant ON acceptance_cases FOR ALL TO fw_specforge_ai_rw USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
