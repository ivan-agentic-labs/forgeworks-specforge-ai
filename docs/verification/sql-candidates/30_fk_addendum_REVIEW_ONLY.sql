-- DESIGN-ONLY SQL. NOT VALIDATED BY A LIVE POSTGRESQL INSTANCE.
-- Review business semantics, existing data, and ON DELETE decision before adoption.
-- Apply after 10_schema_candidate.sql, on an isolated disposable database only.

ALTER TABLE acceptance_cases
  ADD CONSTRAINT fk_g1_acceptance_cases_spec_revision_id
  FOREIGN KEY (tenant_id, spec_revision_id)
  REFERENCES spec_revisions (tenant_id, id)
  ON DELETE RESTRICT;

ALTER TABLE acceptance_cases
  ADD CONSTRAINT fk_g1_acceptance_cases_requirement_id
  FOREIGN KEY (tenant_id, requirement_id)
  REFERENCES requirements (tenant_id, id)
  ON DELETE RESTRICT;

ALTER TABLE operations
  ADD CONSTRAINT fk_g1_operations_spec_revision_id
  FOREIGN KEY (tenant_id, spec_revision_id)
  REFERENCES spec_revisions (tenant_id, id)
  ON DELETE RESTRICT;

ALTER TABLE operations
  ADD CONSTRAINT fk_g1_operations_source_decision_id
  FOREIGN KEY (tenant_id, source_decision_id)
  REFERENCES stakeholder_decisions (tenant_id, id)
  ON DELETE RESTRICT;
