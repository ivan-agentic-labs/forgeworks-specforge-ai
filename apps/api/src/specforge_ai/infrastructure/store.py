from __future__ import annotations
import sqlite3,threading,uuid,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
TENANT='00000000-0000-0000-0000-000000000001'; USER='00000000-0000-0000-0000-000000000010'
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
class Store:
 def __init__(self,path):self.path=path;self.lock=threading.RLock();Path(path).parent.mkdir(parents=True,exist_ok=True) if path!=':memory:' else None;self.init()
 def conn(self):c=sqlite3.connect(self.path,check_same_thread=False);c.row_factory=sqlite3.Row;return c
 def init(self):
  with self.conn() as c:c.executescript('''CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY,slug TEXT,status TEXT);CREATE TABLE IF NOT EXISTS memberships(tenant_id TEXT,user_id TEXT,role TEXT,status TEXT,PRIMARY KEY(tenant_id,user_id));CREATE TABLE IF NOT EXISTS sets_(tenant_id TEXT,id TEXT,title TEXT,source_version INTEGER,source_digest TEXT,owner_id TEXT,status TEXT,version INTEGER,PRIMARY KEY(tenant_id,id));CREATE TABLE IF NOT EXISTS requirements(tenant_id TEXT,id TEXT,set_id TEXT,statement TEXT,source_span TEXT,req_type TEXT,provenance_digest TEXT,PRIMARY KEY(tenant_id,id));CREATE TABLE IF NOT EXISTS ambiguities(tenant_id TEXT,id TEXT,requirement_id TEXT,severity TEXT,question TEXT,status TEXT,PRIMARY KEY(tenant_id,id));CREATE TABLE IF NOT EXISTS decisions(tenant_id TEXT,id TEXT,ambiguity_id TEXT,actor_id TEXT,decision_hash TEXT,source_reference TEXT,PRIMARY KEY(tenant_id,id));CREATE TABLE IF NOT EXISTS revisions(tenant_id TEXT,id TEXT,set_id TEXT,source_version INTEGER,status TEXT,spec_json TEXT,spec_sha TEXT,version INTEGER,PRIMARY KEY(tenant_id,id));CREATE TABLE IF NOT EXISTS jobs(tenant_id TEXT,id TEXT,revision_id TEXT,state TEXT,created_at TEXT,PRIMARY KEY(tenant_id,id));''')
 def seed(self):
  with self.conn() as c:c.execute('INSERT OR IGNORE INTO tenants VALUES(?,?,?)',(TENANT,'synthetic-demo','ACTIVE'));c.execute('INSERT OR IGNORE INTO memberships VALUES(?,?,?,?)',(TENANT,USER,'editor','ACTIVE'))
 def member(self,t,u):
  with self.conn() as c:return c.execute("SELECT 1 FROM memberships WHERE tenant_id=? AND user_id=? AND status='ACTIVE'",(t,u)).fetchone() is not None
 def create_set(self,t,title,digest,owner):
  sid,rid,aid=str(uuid.uuid4()),str(uuid.uuid4()),str(uuid.uuid4());prov=hashlib.sha256((title+'|source').encode()).hexdigest()
  with self.conn() as c:
   c.execute('INSERT INTO sets_ VALUES(?,?,?,?,?,?,?,?)',(t,sid,title,1,digest,owner,'OPEN',1));c.execute('INSERT INTO requirements VALUES(?,?,?,?,?,?,?)',(t,rid,sid,f'Implement {title}', 'source:1-1','functional',prov));c.execute('INSERT INTO ambiguities VALUES(?,?,?,?,?,?)',(t,aid,rid,'HIGH','What is the success response shape?','OPEN'))
  return self.get_set(t,sid)
 def get_set(self,t,sid):
  with self.conn() as c:return c.execute('SELECT * FROM sets_ WHERE tenant_id=? AND id=?',(t,sid)).fetchone()
 def reqs(self,t,sid):
  with self.conn() as c:return c.execute('SELECT * FROM requirements WHERE tenant_id=? AND set_id=?',(t,sid)).fetchall()
 def amb(self,t,sid):
  with self.conn() as c:return c.execute('SELECT a.* FROM ambiguities a JOIN requirements r ON r.id=a.requirement_id AND r.tenant_id=a.tenant_id WHERE a.tenant_id=? AND r.set_id=?',(t,sid)).fetchall()
 def decide(self,t,aid,actor,text,src):
  did=str(uuid.uuid4());dh=hashlib.sha256(text.encode()).hexdigest()
  with self.conn() as c:c.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?)',(t,did,aid,actor,dh,src));c.execute("UPDATE ambiguities SET status='RESOLVED' WHERE tenant_id=? AND id=?",(t,aid))
  return did,dh
 def revision(self,t,sid,source_version,profile):
  open_amb=[a for a in self.amb(t,sid) if a['status']=='OPEN']
  if open_amb:return None,'OPEN_AMBIGUITY'
  req=self.reqs(t,sid);rid,jid=str(uuid.uuid4()),str(uuid.uuid4());spec={'openapi':'3.1.0','info':{'title':self.get_set(t,sid)['title'],'version':'0.1.0'},'paths':{'/health':{'get':{'operationId':'health','x-requirement-id':req[0]['id'],'responses':{'200':{'description':'OK'}}}}}}
  raw=json.dumps(spec,sort_keys=True,separators=(',',':'));sha=hashlib.sha256(raw.encode()).hexdigest()
  with self.conn() as c:c.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?,?)',(t,rid,sid,source_version,'GENERATED',raw,sha,1));c.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(t,jid,rid,'SUCCEEDED',now()))
  return self.get_revision(t,rid),'OK'
 def get_revision(self,t,rid):
  with self.conn() as c:return c.execute('SELECT * FROM revisions WHERE tenant_id=? AND id=?',(t,rid)).fetchone()
 def approve(self,t,rid,sha,version,actor):
  r=self.get_revision(t,rid)
  if not r:return None,'NOT_FOUND'
  if r['version']!=version:return r,'STALE'
  if r['spec_sha']!=sha:return r,'DIGEST_MISMATCH'
  if r['status']=='APPROVED':return r,'ALREADY'
  with self.conn() as c:c.execute("UPDATE revisions SET status='APPROVED' WHERE tenant_id=? AND id=?",(t,rid))
  return self.get_revision(t,rid),'OK'
