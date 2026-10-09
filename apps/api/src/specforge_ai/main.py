from __future__ import annotations
import os,json
from pathlib import Path
from datetime import datetime,timezone
from uuid import UUID
from typing import Annotated
import jwt
from fastapi import FastAPI,Depends,Header,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from specforge_ai.infrastructure.store import Store,TENANT,USER
ROOT=Path(__file__).resolve().parents[4]
class NewSet(BaseModel):model_config=ConfigDict(extra='forbid');title:str;source_artifact_id:UUID;source_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class Decision(BaseModel):model_config=ConfigDict(extra='forbid');decision_text:str;source_reference:str;expected_version:int
class Generate(BaseModel):model_config=ConfigDict(extra='forbid');source_version:int;output_profile:str
class Approve(BaseModel):model_config=ConfigDict(extra='forbid');spec_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');expected_version:int
def reject(status,code,detail):raise HTTPException(status_code=status,detail={'type':'about:blank','title':'Request rejected','status':status,'code':code,'detail':detail,'request_id':'runtime'})
def auth(authorization:Annotated[str|None,Header()]=None):
 if not authorization or not authorization.startswith('Bearer '):reject(401,'UNAUTHENTICATED','Bearer token is required')
 try:return jwt.decode(authorization[7:],os.getenv('DEV_AUTH_SECRET','forgeworks-development-secret-32-plus'),algorithms=['HS256'],issuer=os.getenv('AUTH_ISSUER','https://issuer.synthetic.invalid'),audience=os.getenv('AUTH_AUDIENCE','forgeworks-api'))
 except jwt.PyJWTError:reject(401,'INVALID_TOKEN','Token signature, issuer, audience, or expiry is invalid')
def scope(required,store):
 def dep(c=Depends(auth)):
  if not c.get('tenant_id') or not c.get('sub') or not store.member(c['tenant_id'],c['sub']):reject(403,'TENANT_CONTEXT_INVALID','Verified membership is required')
  if required not in set(str(c.get('scope','')).split()):reject(403,'INSUFFICIENT_SCOPE',f'Scope {required} is required')
  return c
 return dep
def create_app(db_path=None,seed=False):
 store=Store(db_path or os.getenv('SPECFORGE_DB_PATH',str(ROOT/'.runtime/specforge.db')))
 if seed:store.seed()
 app=FastAPI(title='SpecForge AI MVP',version='0.1.0');app.state.store=store
 @app.exception_handler(HTTPException)
 async def errors(_,e):return JSONResponse(status_code=e.status_code,content=e.detail if isinstance(e.detail,dict) else {'type':'about:blank','title':'Request rejected','status':e.status_code,'code':'REQUEST_REJECTED','detail':str(e.detail),'request_id':'runtime'})
 @app.get('/healthz')
 def health():return {'status':'ok','service':'specforge-ai'}
 @app.post('/v1/requirement-sets',status_code=201)
 def create(body:NewSet,c=Depends(scope('requirements:create',store))):
  r=store.create_set(c['tenant_id'],body.title,body.source_sha256,c['sub']);return {'id':r['id'],'status':r['status'],'created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'title':r['title'],'source_version':r['source_version'],'source_digest':r['source_digest'],'owner_id':r['owner_id']}
 @app.get('/v1/requirement-sets/{sid}/requirements')
 def requirements(sid:UUID,c=Depends(scope('requirements:read',store))):
  if not store.get_set(c['tenant_id'],str(sid)):return reject(404,'RESOURCE_NOT_FOUND','Requirement set is not visible')
  items=[{'id':r['id'],'set_id':r['set_id'],'source_span':r['source_span'],'statement':r['statement'],'requirement_type':r['req_type'],'provenance_digest':r['provenance_digest']} for r in store.reqs(c['tenant_id'],str(sid))];return {'items':items,'next_cursor':None,'has_more':False}
 @app.get('/v1/requirement-sets/{sid}/ambiguities')
 def ambiguities(sid:UUID,c=Depends(scope('requirements:read',store))):
  items=[{'id':a['id'],'requirement_id':a['requirement_id'],'severity':a['severity'],'question':a['question'],'resolution_status':a['status']} for a in store.amb(c['tenant_id'],str(sid))];return {'items':items,'next_cursor':None,'has_more':False}
 @app.post('/v1/ambiguities/{aid}/decisions',status_code=201)
 def decision(aid:UUID,body:Decision,c=Depends(scope('requirements:decide',store))):
  result=store.decide(c['tenant_id'],str(aid),c['sub'],body.decision_text,body.source_reference)
  return {'id':result[0],'status':'RECORDED','created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'ambiguity_id':str(aid),'actor_id':c['sub'],'decision_hash':result[1],'source_reference':body.source_reference}
 @app.post('/v1/requirement-sets/{sid}/spec-revisions',status_code=202)
 def generate(sid:UUID,body:Generate,c=Depends(scope('spec:generate',store))):
  r,status=store.revision(c['tenant_id'],str(sid),body.source_version,body.output_profile)
  if status=='OPEN_AMBIGUITY':return reject(409,'OPEN_AMBIGUITY','Resolve all high-impact ambiguities before generation')
  with store.conn() as db: job_row=db.execute('SELECT * FROM jobs WHERE tenant_id=? AND revision_id=?',(c['tenant_id'],r['id'])).fetchone()
  return {'id':r['id'],'status':r['status'],'created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'requirement_set_id':str(sid),'input_version':r['source_version'],'job_id':job_row['id']}
 @app.get('/v1/spec-revisions/{rid}/traceability')
 def trace(rid:UUID,c=Depends(scope('spec:read',store))):
  r=store.get_revision(c['tenant_id'],str(rid))
  if not r:return reject(404,'RESOURCE_NOT_FOUND','Revision is not visible')
  req=store.reqs(c['tenant_id'],r['set_id']);spec=json.loads(r['spec_json']);linked=len([p for p in spec['paths'].values() for op in p.values() if op.get('x-requirement-id')]);return {'id':str(rid),'status':'VERIFIED' if linked==len(req) else 'INCOMPLETE','created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'revision_id':str(rid),'total_requirements':len(req),'linked_requirements':linked,'unlinked_operation_ids':[] if linked==len(req) else ['health'],'critical_open_ambiguities':len(store.amb(c['tenant_id'],r['set_id']))}
 @app.post('/v1/spec-revisions/{rid}/approve',status_code=201)
 def approve(rid:UUID,body:Approve,c=Depends(scope('spec:approve',store))):
  r,status=store.approve(c['tenant_id'],str(rid),body.spec_sha256,body.expected_version,c['sub'])
  if status=='NOT_FOUND':return reject(404,'RESOURCE_NOT_FOUND','Revision is not visible')
  if status=='STALE':return reject(409,'STALE_VERSION','Revision is stale')
  if status=='DIGEST_MISMATCH':return reject(409,'DIGEST_MISMATCH','Spec digest does not match revision')
  return {'id':str(rid),'status':'APPROVED','created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'revision_id':str(rid),'spec_sha256':r['spec_sha'],'approver_id':c['sub'],'approved_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
 @app.get('/v1/jobs/{jid}')
 def job(jid:UUID,c=Depends(scope('job:read',store))):
  with store.conn() as db:r=db.execute('SELECT * FROM jobs WHERE tenant_id=? AND id=?',(c['tenant_id'],str(jid))).fetchone()
  if not r:return reject(404,'RESOURCE_NOT_FOUND','Job is not visible')
  return {'id':r['id'],'kind':'spec_generation','state':r['state'],'created_at':r['created_at'],'state_version':1,'attempt_count':1,'last_error_code':None}
 return app
app=create_app(seed=os.getenv('SPECFORGE_SEED_FIXTURE','0')=='1')
