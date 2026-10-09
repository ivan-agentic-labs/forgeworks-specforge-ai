#!/usr/bin/env bash
set -euo pipefail
# Never execute against a production server or a network host.
[[ "${G1_DISPOSABLE_DB:-}" == 'yes' ]] || { echo 'G1_DISPOSABLE_DB=yes required' >&2; exit 2; }
[[ "${PGHOST:-}" == '127.0.0.1' ]] || { echo 'only 127.0.0.1 is allowed' >&2; exit 2; }
[[ "${PGDATABASE:-}" == 'forgeworks_g1' ]] || { echo 'only disposable database forgeworks_g1 is allowed' >&2; exit 2; }
command -v psql >/dev/null || { echo 'psql unavailable' >&2; exit 2; }
base="$(cd "$(dirname "$0")/.." && pwd)/docs/verification/sql-candidates"
for f in 00_role_candidate.sql 10_schema_candidate.sql 20_grants_candidate.sql; do
  echo "G1 DDL probe: $f"
  psql -X -v ON_ERROR_STOP=1 -f "$base/$f"
done
psql -X -v ON_ERROR_STOP=1 -c 'SELECT COUNT(*) AS user_tables FROM pg_tables WHERE schemaname = current_schema();'
echo 'PASS: DDL smoke test completed.'

# The candidate schema has tenant policies and a NOLOGIN/NOBYPASSRLS application role,
# so prove the negative case in the same disposable database. SET ROLE keeps the
# migration owner separate from the application role while avoiding a login grant.
psql -X -v ON_ERROR_STOP=1 <<'SQL'
ALTER TABLE requirement_sets FORCE ROW LEVEL SECURITY;

INSERT INTO tenants(id, slug, status) VALUES
  ('11111111-1111-1111-1111-111111111111', 'tenant-a', 'ACTIVE'),
  ('22222222-2222-2222-2222-222222222222', 'tenant-b', 'ACTIVE');
INSERT INTO requirement_sets(tenant_id, id, title, owner_id, current_version, status) VALUES
  ('11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Tenant A set', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaab', 1, 'ACTIVE'),
  ('22222222-2222-2222-2222-222222222222', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Tenant B set', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbc', 1, 'ACTIVE');

SET ROLE fw_specforge_ai_rw;
SELECT set_config('app.tenant_id', '11111111-1111-1111-1111-111111111111', false);
DO $$
DECLARE
  visible_count integer;
  cross_tenant_count integer;
BEGIN
  SELECT count(*) INTO visible_count FROM requirement_sets;
  IF visible_count <> 1 THEN
    RAISE EXCEPTION 'RLS isolation failed: expected one visible row, got %', visible_count;
  END IF;
  SELECT count(*) INTO cross_tenant_count FROM requirement_sets
    WHERE tenant_id = '22222222-2222-2222-2222-222222222222';
  IF cross_tenant_count <> 0 THEN
    RAISE EXCEPTION 'RLS isolation failed: cross-tenant row is visible';
  END IF;
  BEGIN
    INSERT INTO requirement_sets(tenant_id, id, title, owner_id, current_version, status)
      VALUES ('22222222-2222-2222-2222-222222222222', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'cross-tenant write', 'cccccccc-cccc-cccc-cccc-cccccccccccd', 1, 'ACTIVE');
    RAISE EXCEPTION 'RLS isolation failed: cross-tenant write was accepted';
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;
END $$;
RESET ROLE;
SQL
echo 'PASS: non-owner fw_specforge_ai_rw cannot read or write another tenant when app.tenant_id is set.'
