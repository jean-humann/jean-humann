"""Synthetic live tests: real Lakekeeper, OpenFGA, S3 remote signing, PostgreSQL.
This is a review bench, not a Flows implementation or a replay of the old campaigns.
"""
import base64,concurrent.futures,threading,uuid
import pyarrow as pa
import psycopg
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField,LongType,StringType
from pyiceberg.exceptions import CommitFailedException
from common import *
RUN=uuid.uuid4().hex[:8]
SCHEMA=Schema(NestedField(1,'id',LongType(),required=False),NestedField(2,'value',StringType(),required=False))
WAREHOUSE=json.loads((ROOT/'runtime.json').read_text())['warehouse-id']
DSN='postgresql://postgres:'+LAB_SECRET+'@'+('db:5432' if os.environ.get('HEMERA_INTERNAL') else '127.0.0.1:15432')+'/flowqueue'
def catalog(client='review-admin'):
 return load_catalog('review',type='rest',uri=CATALOG+'/catalog',warehouse='review',token=token(client),**{'header.X-Iceberg-Access-Delegation':'remote-signing'})
def table(name,seed=True):
 c=catalog();ident='review.'+name+'_'+RUN
 c.create_namespace_if_not_exists('review')
 t=c.create_table(ident,schema=SCHEMA)
 if seed:t.append(data(0))
 return c,t,ident
def data(i,value=None):return pa.table({'id':[i],'value':[value or str(i)]})
def rows(t,branch=None):
 t.refresh();args={'snapshot_id':t.refs()[branch].snapshot_id} if branch else {}
 return sorted(t.scan(**args).to_arrow().to_pylist(),key=lambda x:x['id'])
def is_ancestor(t,ancestor,child):
 while child is not None:
  if child==ancestor:return True
  child=t.snapshot_by_id(child).parent_snapshot_id
 return False
def publish(t,branch):
 t.refresh();main=t.current_snapshot().snapshot_id;target=t.refs()[branch].snapshot_id
 if not is_ancestor(t,main,target):raise ValueError('stale WAP ancestry; rerun from current published snapshot')
 t.manage_snapshots().set_current_snapshot(target).commit()
 return target
def i1():
 c,t,ident=table('i1',False);a=c.load_table(ident);b=c.load_table(ident)
 a.append(data(1));error=None
 try:b.append(data(2))
 except CommitFailedException as e:error=str(e)
 before=rows(c.load_table(ident))
 if error:b.refresh();b.append(data(2))
 after=rows(b);assert [r['id'] for r in after]==[1,2]
 # Disable the new automatic retry explicitly to exercise the caller recovery path.
 c,t2,ident2=table('i1_no_retry',False)
 with t2.transaction() as tx:tx.set_properties(**{'commit.retry.num-retries':'0'})
 a=c.load_table(ident2);b=c.load_table(ident2);a.append(data(1));rejected=None
 try:b.append(data(2))
 except CommitFailedException as e:rejected=str(e)
 assert rejected is not None,'retry=0 must expose optimistic conflict'
 b.refresh();b.append(data(2));assert len(rows(b))==2
 return {'table':ident,'default_retries_stale_commit_error':error,'after_stale_append':before,'final_rows':after,'historical_claim_no_automatic_retry':False if error is None else True,'explicit_retry_disabled_table':ident2,'conflict_with_retry_0':rejected,'recovery':'refresh then reapply','storage':'S3V4RestSigner; client holds no storage secret'}
def i2():
 c,t,ident=table('i2');base=t.current_snapshot().snapshot_id
 for br,num in [('wap_a',1),('wap_b',2)]:
  t.refresh();t.manage_snapshots().create_branch(base,br).commit();t.append(data(num),branch=br)
 gate=threading.Barrier(2)
 def commit(br):
  local=catalog().load_table(ident);tx=local.manage_snapshots().set_current_snapshot(ref_name=br)
  gate.wait(timeout=15)
  try:tx.commit();return {'branch':br,'outcome':'published'}
  except CommitFailedException as e:return {'branch':br,'outcome':'conflict','error':str(e)}
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(commit,['wap_a','wap_b']))
 assert sorted(x['outcome'] for x in out)==['conflict','published'],out
 winner=next(x['branch'] for x in out if x['outcome']=='published');loser=next(x['branch'] for x in out if x['outcome']=='conflict')
 published_rows=rows(t);t.refresh();current=t.current_snapshot().snapshot_id;loser_head=t.refs()[loser].snapshot_id
 assert not is_ancestor(t,current,loser_head)
 try:publish(t,loser)
 except ValueError as e:guard_error=str(e)
 else:raise AssertionError('ancestry guard accepted divergent branch')
 # Deliberately demonstrate unsafe fresh-handle publish on this throw-away table.
 t.refresh();t.manage_snapshots().set_current_snapshot(loser_head).commit();unsafe_rows=rows(t)
 assert unsafe_rows!=published_rows
 return {'table':ident,'concurrent_cas_results':out,'published_rows':published_rows,'ancestry_guard':guard_error,'unsafe_fresh_handle_repoint_rows':unsafe_rows,'observed_lost_update':True,'warning':'The unsafe operation is intentional only on this throw-away synthetic table.'}
def i3():
 c,t,ident=table('i3');base=t.current_snapshot().snapshot_id
 t.manage_snapshots().create_branch(base,'env_dev').commit();t.append(data(1))
 main=rows(t);dev=rows(t,'env_dev');assert len(main)==2 and len(dev)==1
 return {'table':ident,'main':main,'env_dev':dev,'dev_snapshot_id':base}
def i4():
 c,t,ident=table('i4');t.manage_snapshots().create_branch(t.current_snapshot().snapshot_id,'wap').commit()
 props={'origin.cursor':'synthetic-lsn:42','origin.state':'{"offset":42}','origin.provenance':'hemera-v2-review/synthetic-source','origin.run_id':RUN}
 result=t.upsert(data(0,'updated'),join_cols=['id'],branch='wap',snapshot_properties=props)
 staged=t.snapshot_by_id(t.refs()['wap'].snapshot_id);before=rows(t)
 sid=publish(t,'wap');after=rows(t);summary=t.current_snapshot().summary.model_dump()
 assert all(summary[k]==v for k,v in props.items());assert before[0]['value']=='0' and after[0]['value']=='updated'
 return {'table':ident,'upsert_result':str(result),'published_snapshot':sid,'summary':summary,'before':before,'after':after,'state_recovered_from_published_snapshot':{k:summary[k] for k in props}}
def i5():
 c,t,ident=table('i5');t.manage_snapshots().create_branch(t.current_snapshot().snapshot_id,'env_short',max_ref_age_ms=60000).commit();t.refresh()
 ref=t.refs()['env_short'].model_dump(by_alias=True);assert ref['max-ref-age-ms']==60000
 return {'table':ident,'ref':ref,'not_tested':'Expiration scheduling or physical deletion of old files'}
def veto():
 c,t,ident=table('veto');base=t.current_snapshot().snapshot_id
 t.manage_snapshots().create_branch(base,'wap_bad').commit();t.append(data(-1),branch='wap_bad');audit=all(x['id']>=0 for x in rows(t,'wap_bad'));assert not audit
 t.manage_snapshots().remove_branch('wap_bad').commit();published=rows(t)
 assert t.current_snapshot().snapshot_id==base and published==[{'id':0,'value':'0'}]
 return {'table':ident,'blocking_audit_passed':audit,'published_snapshot_unchanged':base,'published_rows':published,'staging_ref_removed':'wap_bad' not in t.refs()}
def int3():
 c,t,ident=table('int3');gate=threading.Barrier(2);events=[];lock=threading.Lock()
 def worker(num):
  gate.wait(timeout=10)
  with psycopg.connect(DSN) as pg:
   pg.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(ident,))
   start=time.monotonic();local=catalog().load_table(ident);base=local.current_snapshot().snapshot_id;br='wap_'+str(num)
   local.manage_snapshots().create_branch(base,br).commit();local.append(data(num),branch=br,snapshot_properties={'origin.cursor':str(num),'origin.run_id':RUN+'_'+str(num)})
   staged=rows(local,br);assert all(x['id']>=0 for x in staged)
   sid=publish(local,br);local.manage_snapshots().remove_branch(br).commit()
   with lock:events.append({'worker':num,'started':start,'finished':time.monotonic(),'base':base,'published':sid})
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(worker,[1,2]))
 final=rows(t);events.sort(key=lambda x:x['started']);assert events[0]['finished']<=events[1]['started'];assert [x['id'] for x in final]==[0,1,2]
 return {'table':ident,'orchestrator':'Synthetic review wrapper using PostgreSQL advisory transaction lock; not production Flows','events':events,'final_rows':final,'ancestry_and_catalog_CAS':True,'limitations':'One local process, two threads and two database sessions; no distributed failover stress'}
def authn_authz():
 c,t,ident=table('auth');table_id=WAREHOUSE+'/'+t.config['s3.signer.endpoint'].split('/tabular-id/')[1].split('/')[0];path=f'/catalog/v1/{WAREHOUSE}/namespaces/review/tables/{ident.split(".")[1]}'
 good=requests.get(CATALOG+path,headers=headers(),timeout=15)
 anon=requests.get(CATALOG+path,timeout=15)
 outsider=requests.get(CATALOG+path,headers=headers('review-outsider'),timeout=15)
 assert good.status_code==200 and anon.status_code==401 and outsider.status_code in (403,404)
 fh=headers('openfga');stores=requests.get(FGA+'/stores',headers=fh,timeout=15).json();store=next(x['id'] for x in stores['stores'] if x['name']=='lakekeeper')
 models=requests.get(FGA+f'/stores/{store}/authorization-models',headers=fh,timeout=15).json();model=models['authorization_models'][0]
 def user(client):
  payload=token(client).split('.')[1];return 'user:oidc~'+json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))['sub']
 checks={}
 for client in ['review-admin','review-outsider']:
  q={'authorization_model_id':model['id'],'tuple_key':{'user':user(client),'relation':'can_read_data','object':'lakekeeper_table:'+table_id},'consistency':'HIGHER_CONSISTENCY'}
  r=requests.post(FGA+f'/stores/{store}/check',headers=fh,json=q,timeout=15);assert r.status_code==200,(r.status_code,r.text);checks[client]=r.json()
 assert checks['review-admin']['allowed'] and not checks['review-outsider']['allowed'],checks
 # Prove that a genuine OpenFGA grant affects the Lakekeeper REST decision.
 tuple_key={'user':user('review-outsider'),'relation':'select','object':'lakekeeper_table:'+table_id}
 r=requests.post(FGA+f'/stores/{store}/write',headers=fh,json={'authorization_model_id':model['id'],'writes':{'tuple_keys':[tuple_key]}},timeout=15);assert r.status_code==200,(r.status_code,r.text)
 # Catalog authorizer has a cache. Record measured convergence and limit wait.
 start=time.monotonic();after_grant=None
 for _ in range(60):
  after_grant=requests.get(CATALOG+path,headers=headers('review-outsider'),timeout=15)
  if after_grant.status_code==200:break
  time.sleep(1)
 assert after_grant.status_code==200,(after_grant.status_code,after_grant.text)
 grant_delay=time.monotonic()-start
 r=requests.post(FGA+f'/stores/{store}/write',headers=fh,json={'authorization_model_id':model['id'],'deletes':{'tuple_keys':[tuple_key]}},timeout=15);assert r.status_code==200
 start=time.monotonic();after_revoke=None
 for _ in range(60):
  after_revoke=requests.get(CATALOG+path,headers=headers('review-outsider'),timeout=15)
  if after_revoke.status_code in (403,404):break
  time.sleep(1)
 assert after_revoke.status_code in (403,404)
 write('lakekeeper-openfga-model',model)
 return {'table':ident,'table_uuid':table_id,'http_statuses':{'admin':good.status_code,'anonymous':anon.status_code,'outsider':outsider.status_code,'outsider_after_grant':after_grant.status_code,'outsider_after_revoke':after_revoke.status_code},'direct_openfga_checks':checks,'grant_visibility_seconds':grant_delay,'revoke_visibility_seconds':time.monotonic()-start,'native_model_id':model['id'],'native_model_conditions':list(model.get('conditions',{}))}
def ttl():
 fh=headers('openfga');r=requests.post(FGA+'/stores',headers=fh,json={'name':'hemera-v2-review-ttl-'+RUN},timeout=15);r.raise_for_status();store=r.json()['id']
 model={'schema_version':'1.1','type_definitions':[{'type':'user'},{'type':'document','relations':{'viewer':{'this':{}}},'metadata':{'relations':{'viewer':{'directly_related_user_types':[{'type':'user','condition':'unexpired'}]}}}}],'conditions':{'unexpired':{'name':'unexpired','expression':'current_time < expires_at','parameters':{'current_time':{'type_name':'TYPE_NAME_TIMESTAMP'},'expires_at':{'type_name':'TYPE_NAME_TIMESTAMP'}}}}}
 r=requests.post(FGA+f'/stores/{store}/authorization-models',headers=fh,json=model,timeout=15);r.raise_for_status();mid=r.json()['authorization_model_id']
 tup={'user':'user:synthetic','relation':'viewer','object':'document:synthetic','condition':{'name':'unexpired','context':{'expires_at':'2026-10-02T12:00:00Z'}}}
 r=requests.post(FGA+f'/stores/{store}/write',headers=fh,json={'authorization_model_id':mid,'writes':{'tuple_keys':[tup]}},timeout=15);r.raise_for_status()
 checks=[]
 for value in ['2026-10-02T11:59:59Z','2026-10-02T12:00:00Z','2026-10-02T12:00:01Z']:
  q={'authorization_model_id':mid,'tuple_key':{k:v for k,v in tup.items() if k!='condition'},'context':{'current_time':value}}
  r=requests.post(FGA+f'/stores/{store}/check',headers=fh,json=q,timeout=15);r.raise_for_status();checks.append({'current_time':value,**r.json()})
 assert [x['allowed'] for x in checks]==[True,False,False]
 return {'isolated_store':store,'checks':checks,'scope':'Real OpenFGA CEL condition with explicit supplied timestamps. Not Lakekeeper TTL integration or wall-clock expiry. Native Lakekeeper model has no conditions; no reconciler purge was tested.'}
if __name__=='__main__':
 for name,scope,fn in [('AUTH','Real OIDC + Lakekeeper + OpenFGA decisions, grant and revoke',authn_authz),('I1','New live stale append test on PyIceberg 0.12.0 / Lakekeeper 0.12.0',i1),('I2','New live CAS race, divergence guard, unsafe repoint counterexample',i2),('I3','New live branch isolation',i3),('I4','New live branch upsert and published origin summary',i4),('I5','New live ref retention metadata',i5),('WAP-VETO','New live blocking audit before publication',veto),('INT-3','New local serialization wrapper, Lakekeeper commits, PostgreSQL locking',int3),('OPENFGA-TTL','Real standalone OpenFGA condition, not INT-5 acceptance',ttl)]:run(name,scope,fn)
