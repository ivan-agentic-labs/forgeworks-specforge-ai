import hashlib
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from openapi_spec_validator import validate
from specforge_ai.main import create_app
from specforge_ai.infrastructure.store import TENANT, USER
from test_specforge_flow import h
headers = h


def upload_source(client, text):
    body = text.encode()
    digest = hashlib.sha256(body).hexdigest()
    intent = client.post('/v1/artifacts/upload-intents', headers=h('artifact:create'), json={'kind':'source','filename':'requirements.txt','size_bytes':len(body),'sha256':digest,'declared_media_type':'text/plain'})
    assert intent.status_code == 201, intent.text
    aid = intent.json()['artifact_id']
    uploaded = client.put(intent.json()['upload_url'], content=body)
    assert uploaded.status_code == 201, uploaded.text
    committed = client.post(f'/v1/artifacts/{aid}/commit', headers=h('artifact:commit'), json={'sha256':digest,'size_bytes':len(body),'object_generation':uploaded.json()['object_generation']})
    assert committed.status_code == 201, committed.text
    return aid, digest


def requirement_set(client, text):
    artifact, digest = upload_source(client, text)
    response = client.post('/v1/requirement-sets', headers=headers('requirements:create'), json={'title':'Declared API','source_artifact_id':artifact,'source_sha256':digest})
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_source_to_explicit_openapi_and_digest_verified_download(tmp_path):
    with TestClient(create_app(str(tmp_path / 'flow.sqlite'), seed=True)) as client:
        sid = requirement_set(client, 'GET /users/{user_id} -> 200 | Retrieve user\nPOST /users -> 201 | Create user\nHEAD /users -> 200 | Inspect users')
        body = {'source_version':1,'output_profile':'openapi31-explicit-v1'}
        auth = {**headers('spec:generate'),'Idempotency-Key':'explicit-generation-0001'}
        generated = client.post(f'/v1/requirement-sets/{sid}/spec-revisions', headers=auth, json=body)
        assert generated.status_code == 202, generated.text
        replay = client.post(f'/v1/requirement-sets/{sid}/spec-revisions', headers=auth, json=body)
        assert replay.json() == generated.json()
        rid = generated.json()['id']
        downloaded = client.get(f'/v1/spec-revisions/{rid}/openapi', headers=headers('spec:read'))
        assert downloaded.status_code == 200, downloaded.text
        assert hashlib.sha256(downloaded.content).hexdigest() == generated.json()['spec_sha256'] == downloaded.headers['X-Spec-SHA256']
        assert downloaded.headers['Cache-Control'] == 'no-store'
        spec = downloaded.json()
        validate(spec)
        assert set(spec['paths']) == {'/users/{user_id}', '/users'}
        assert set(spec['paths']['/users']) == {'post', 'head'}
        assert spec['paths']['/users']['post']['responses'].keys() == {'201'}
        assert spec['x-output-profile'] == 'openapi31-explicit-v1'
        trace = client.get(f'/v1/spec-revisions/{rid}/traceability', headers=headers('spec:read')).json()
        assert trace['status'] == 'VERIFIED'
        assert trace['linked_requirements'] == trace['total_requirements'] == 3
        assert trace['operation_coverage'] == {'linked': 3, 'total': 3, 'ratio': 1.0}
        assert trace['requirement_coverage'] == {'linked': 3, 'total': 3, 'ratio': 1.0}
        assert client.get(f'/v1/spec-revisions/{rid}/openapi', headers=headers('requirements:read')).status_code == 403
        assert client.get(f'/v1/spec-revisions/{uuid4()}/openapi', headers=headers('spec:read')).status_code == 404
        other = str(uuid4())
        with client.app.state.store.conn() as db:
            db.execute('INSERT INTO memberships VALUES(?,?,?,?)', (other, USER, 'editor', 'ACTIVE'))
        assert client.get(f'/v1/spec-revisions/{rid}/openapi', headers=h('spec:read', other)).status_code == 404
        with client.app.state.store.conn() as db:
            db.execute('UPDATE revisions SET spec_json=? WHERE id=? AND tenant_id=?', ('{}', rid, TENANT))
        assert client.get(f'/v1/spec-revisions/{rid}/openapi', headers=headers('spec:read')).status_code == 409


@pytest.mark.parametrize('source,profile,code', [
    ('Retrieve users','openapi31-explicit-v1','EXPLICIT_ENDPOINT_DECLARATION_REQUIRED'),
    ('GET /users -> 200 | one\nGET /users -> 201 | two','openapi31-explicit-v1','EXPLICIT_ENDPOINT_DUPLICATE'),
    ('GET /users/{id} -> 200 | one\nPOST /users/{name} -> 201 | two','openapi31-explicit-v1','EXPLICIT_ENDPOINT_TEMPLATE_COLLISION'),
    ('GET /users -> 200 | retrieve','unsupported-profile','OUTPUT_PROFILE_UNSUPPORTED'),
])
def test_invalid_explicit_input_has_no_partial_revision(tmp_path, source, profile, code):
    with TestClient(create_app(str(tmp_path / 'reject.sqlite'), seed=True)) as client:
        sid = requirement_set(client, source)
        result = client.post(f'/v1/requirement-sets/{sid}/spec-revisions', headers=headers('spec:generate'), json={'source_version':1,'output_profile':profile})
        assert result.status_code == 422, result.text
        assert result.json()['code'] == code
        with client.app.state.store.conn() as db:
            assert db.execute('SELECT count(*) FROM revisions').fetchone()[0] == 0
            assert db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 0
