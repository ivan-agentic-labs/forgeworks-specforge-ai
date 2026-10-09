from datetime import datetime,timedelta,timezone
import hashlib
import jwt
from fastapi.testclient import TestClient
from specforge_ai.main import create_app
from specforge_ai.infrastructure.store import TENANT,USER
S='forgeworks-development-secret-32-plus';ISS='https://issuer.synthetic.invalid';AUD='forgeworks-api'
def h(scope,tenant=TENANT):
 t=jwt.encode({'sub':USER,'tenant_id':tenant,'scope':scope,'iss':ISS,'aud':AUD,'exp':datetime.now(timezone.utc)+timedelta(minutes=5)},S,algorithm='HS256');return {'Authorization':'Bearer '+t}
def source(c):
 body=b'Create the pet endpoint\nTBD: What response shape is required?';digest=hashlib.sha256(body).hexdigest()
 intent=c.post('/v1/artifacts/upload-intents',headers=h('artifact:create'),json={'kind':'source','filename':'requirements.txt','size_bytes':len(body),'sha256':digest,'declared_media_type':'text/plain'});assert intent.status_code==201,intent.text
 uploaded=c.put(intent.json()['upload_url'],content=body);assert uploaded.status_code==201,uploaded.text
 committed=c.post(f"/v1/artifacts/{intent.json()['artifact_id']}/commit",headers=h('artifact:commit'),json={'sha256':digest,'size_bytes':len(body),'object_generation':uploaded.json()['object_generation']});assert committed.status_code==201,committed.text
 return intent.json()['artifact_id'],digest
def test_requirement_to_approved_spec(tmp_path):
 app=create_app(str(tmp_path/'db.sqlite'),seed=True)
 with TestClient(app) as c:
  artifact_id,digest=source(c)
  r=c.post('/v1/requirement-sets',headers=h('requirements:create'),json={'title':'Pet API','source_artifact_id':artifact_id,'source_sha256':digest});assert r.status_code==201,r.text;sid=r.json()['id']
  amb=c.get(f'/v1/requirement-sets/{sid}/ambiguities',headers=h('requirements:read')).json()['items'][0]
  blocked=c.post(f'/v1/requirement-sets/{sid}/spec-revisions',headers=h('spec:generate'),json={'source_version':1,'output_profile':'openapi31'});assert blocked.status_code==409
  d=c.post(f"/v1/ambiguities/{amb['id']}/decisions",headers=h('requirements:decide'),json={'decision_text':'Return HTTP 200 with JSON object','source_reference':'product-owner:synthetic-1','expected_version':1});assert d.status_code==201
  g=c.post(f'/v1/requirement-sets/{sid}/spec-revisions',headers=h('spec:generate'),json={'source_version':1,'output_profile':'openapi31'});assert g.status_code==202;rid=g.json()['id']
  tr=c.get(f'/v1/spec-revisions/{rid}/traceability',headers=h('spec:read')).json();assert tr['status']=='VERIFIED' and tr['linked_requirements']==2
  with app.state.store.conn() as db: sha=db.execute('SELECT spec_sha FROM revisions WHERE id=?',(rid,)).fetchone()['spec_sha']
  a=c.post(f'/v1/spec-revisions/{rid}/approve',headers=h('spec:approve'),json={'spec_sha256':sha,'expected_version':1});assert a.status_code==201

def test_scope_and_tenant_fail_closed(tmp_path):
 app=create_app(str(tmp_path/'db.sqlite'),seed=True)
 with TestClient(app) as c:
  r=c.post('/v1/requirement-sets',headers=h('spec:generate'),json={'title':'x','source_artifact_id':'33333333-3333-3333-3333-333333333333','source_sha256':'a'*64});assert r.status_code==403
  r=c.post('/v1/requirement-sets',headers=h('requirements:create','00000000-0000-0000-0000-000000000099'),json={'title':'x','source_artifact_id':'33333333-3333-3333-3333-333333333333','source_sha256':'a'*64});assert r.status_code==403

