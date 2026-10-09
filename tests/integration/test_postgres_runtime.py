"""Actual PostgreSQL proof; requires an explicit fresh disposable localhost DB."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from specforge_ai.infrastructure.postgres_store import PostgresStore, ROLE
from specforge_ai.infrastructure.store import TENANT,USER


def test_postgres_revision_decision_approval_and_tenant_boundaries(monkeypatch):
    owner=os.getenv('SPECFORGE_DISPOSABLE_OWNER_DSN')
    if not owner:
        pytest.skip('Disposable PostgreSQL unavailable; NOT a runtime pass')
    info=conninfo_to_dict(owner)
    if os.getenv('G1_DISPOSABLE_DB')!='yes' or info.get('host') not in {'localhost','127.0.0.1'} or info.get('dbname')!='forgeworks_runtime':
        pytest.fail('Refusing non-disposable PostgreSQL configuration')
    root=Path(__file__).resolve().parents[2];other=str(uuid4())
    with psycopg.connect(owner) as db:
        if db.execute("SELECT to_regclass('requirement_sets')").fetchone()[0]:
            pytest.fail('Proof requires a fresh empty database')
        for name in ['001_specforge_mvp.sql','002_specforge_runtime.sql']:
            db.execute((root/'migrations/versions'/name).read_text())
        db.execute("CREATE ROLE fw_runtime_test LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'synthetic-local-runtime-test-only'")
        db.execute('GRANT fw_specforge_ai_rw TO fw_runtime_test')
        db.execute('INSERT INTO tenants VALUES(%s,%s,%s)',(TENANT,'synthetic-demo','ACTIVE'))
        db.execute('INSERT INTO tenants VALUES(%s,%s,%s)',(other,'synthetic-other','ACTIVE'))
        db.execute('INSERT INTO memberships VALUES(%s,%s,%s,%s)',(TENANT,USER,'editor','ACTIVE'))
    info.update(user='fw_runtime_test',password='synthetic-local-runtime-test-only')
    runtime=make_conninfo(**info)
    with pytest.raises(ValueError,match='superuser'):
        PostgresStore(owner)
    store=PostgresStore(runtime)
    assert not store.member(TENANT, "unmapped-oidc-subject")
    # Runtime login and its group cannot own tenant/provisioning tables either.
    for table, new_owner in [('memberships','fw_runtime_test'),('tenants',ROLE)]:
        with psycopg.connect(owner) as db:
            db.execute(psycopg.sql.SQL('ALTER TABLE {} OWNER TO {}').format(psycopg.sql.Identifier(table),psycopg.sql.Identifier(new_owner)))
        try:
            with pytest.raises(ValueError,match='own product tables'):
                PostgresStore(runtime)
        finally:
            with psycopg.connect(owner) as db:
                db.execute(psycopg.sql.SQL('ALTER TABLE {} OWNER TO postgres').format(psycopg.sql.Identifier(table)))
                db.execute(psycopg.sql.SQL('REVOKE ALL ON {} FROM {}').format(psycopg.sql.Identifier(table),psycopg.sql.Identifier(new_owner)))

    assert store.member(TENANT,USER)
    assert not store.member(other,USER)
    row=store.create_set(TENANT,'Synthetic orders','a'*64,USER)
    assert store.get_set(other,row['id']) is None
    with pytest.raises(ValueError,match='tenant context'):
        with store.conn():pass
    with psycopg.connect(runtime) as db:
        db.execute('SET LOCAL ROLE fw_specforge_ai_rw')
        assert db.execute('SELECT count(*) FROM requirement_sets').fetchone()[0]==0
    with store.conn(TENANT) as db:
        assert db.execute('UPDATE requirement_sets SET title=? WHERE tenant_id=?',('forbidden',other)).rowcount==0
        assert db.execute('DELETE FROM requirement_sets WHERE tenant_id=?',(other,)).rowcount==0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('INSERT INTO requirement_sets(tenant_id,id,title,source_version,source_digest,owner_id,status) VALUES(?,?,?,?,?,?,?)',(other,str(uuid4()),'forbidden',1,'b'*64,USER,'OPEN'))
    ambiguity=store.amb(TENANT,row['id'])[0]
    # Two independent adapters and concurrent commands must accept one expected version.
    peers=[PostgresStore(runtime),PostgresStore(runtime)]
    def decide(index):
        return peers[index].decide(TENANT,ambiguity['id'],USER,'Return JSON','synthetic://review/1',1)[1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(decide,range(2)))
    assert sorted(results)==['OK','STALE']
    revision,status=store.revision(TENANT,row['id'],1,'openapi31')
    assert status=='OK' and revision['status']=='GENERATED'
    assert store.job_for_revision(TENANT,revision['id'])['state']=='SUCCEEDED'
    assert store.trace(TENANT,revision['id'])['status']=='VERIFIED'
    with ThreadPoolExecutor(max_workers=2) as pool:
        approvals=list(pool.map(lambda index:peers[index].approve(TENANT,revision['id'],revision['spec_sha'],1,USER),range(2)))
    assert sorted(result[1] for result in approvals)==['OK','STALE']
    approved=next(result[0] for result in approvals if result[1]=='OK')
    assert approved['status']=='APPROVED' and approved['version']==2
    assert store.get_revision(other,revision['id']) is None
    store.idempotency_store(TENANT,'synthetic-key','c'*64,{'id':revision['id']})
    replay,status=store.idempotency_lookup(TENANT,'synthetic-key','c'*64)
    assert status=='REPLAY' and replay['id']==revision['id']
    artifact=store.create_artifact_intent(TENANT,'source','source.txt',10,'d'*64,'text/plain')
    quarantined,status=store.commit_artifact(TENANT,artifact['id'],'d'*64,10,'1')
    assert status=='OK' and quarantined['status']=='QUARANTINED'
    assert store.download_intent(TENANT,artifact['id'])[1]=='NOT_AVAILABLE'
    # Exercise the actual FastAPI adapter and its atomic idempotency envelope.
    from fastapi.testclient import TestClient
    from specforge_ai.main import create_app
    from test_specforge_flow import h
    monkeypatch.setenv('SPECFORGE_DATABASE_URL',runtime)
    with TestClient(create_app()) as client:
        headers={**h('spec:generate'),'Idempotency-Key':'postgres-api-replay-001'}
        body={'source_version':1,'output_profile':'openapi31'}
        generated=client.post(f"/v1/requirement-sets/{row['id']}/spec-revisions",headers=headers,json=body)
        assert generated.status_code==202,generated.text
        replay=client.post(f"/v1/requirement-sets/{row['id']}/spec-revisions",headers=headers,json=body)
        assert replay.status_code==202 and replay.json()==generated.json()
        rejected=client.post(f"/v1/requirement-sets/{row['id']}/spec-revisions",headers=headers,json={**body,'source_version':2})
        assert rejected.status_code==409,rejected.text
