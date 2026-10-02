import threading,concurrent.futures,uuid
import psycopg
from common import *
DSN='postgresql://postgres:'+LAB_SECRET+'@127.0.0.1:15432/flowqueue'
def campaign():
 schema='review_'+uuid.uuid4().hex[:8];events=[];lock=threading.Lock()
 def conn():
  c=psycopg.connect(DSN);c.execute('SET search_path TO '+schema);c.commit();return c
 with psycopg.connect(DSN) as c:
  c.execute('CREATE SCHEMA '+schema)
  c.execute('SET search_path TO '+schema)
  c.execute("CREATE TABLE flow_job(id int primary key,name text,state text default 'QUEUED',depends_on int[] default '{}',lease_until timestamptz,owner text,attempt int default 0,started_at timestamptz,finished_at timestamptz)")
  c.execute("INSERT INTO flow_job(id,name,depends_on) VALUES(1,'source_b','{}'),(2,'source_a','{}'),(3,'independent','{}'),(4,'transform','{1,2}'),(5,'output','{4}')")
 claim="""WITH next_job AS (
 SELECT j.id FROM flow_job j WHERE
 (j.state='QUEUED' OR (j.state='RUNNING' AND j.lease_until<clock_timestamp()))
 AND NOT EXISTS(SELECT 1 FROM flow_job d WHERE d.id=ANY(j.depends_on) AND d.state<>'SUCCEEDED')
 ORDER BY j.id FOR UPDATE SKIP LOCKED LIMIT 1)
 UPDATE flow_job j SET state='RUNNING',owner=%s,attempt=attempt+1,
 lease_until=clock_timestamp()+interval '1.2 seconds',started_at=clock_timestamp()
 FROM next_job n WHERE j.id=n.id RETURNING j.id,j.name,j.attempt,j.started_at"""
 with conn() as c:dead=c.execute(claim,('dead-worker',)).fetchone()
 assert dead[0]==1
 events.append({'kind':'lease_then_abandon','worker':'dead-worker','id':1,'attempt':dead[2]})
 deadline=time.monotonic()+20
 def worker(name):
  while time.monotonic()<deadline:
   with conn() as c:
    job=c.execute(claim,(name,)).fetchone()
   if not job:
    with conn() as c:
     if c.execute("SELECT count(*) FROM flow_job WHERE state<>'SUCCEEDED'").fetchone()[0]==0:return
    time.sleep(.05);continue
   with lock:events.append({'kind':'lease','worker':name,'id':job[0],'attempt':job[2],'started_at':job[3]})
   time.sleep(.08)
   with conn() as c:
    n=c.execute("UPDATE flow_job SET state='SUCCEEDED',finished_at=clock_timestamp() WHERE id=%s AND owner=%s AND attempt=%s AND lease_until>clock_timestamp()",(job[0],name,job[2])).rowcount
   assert n==1
  raise AssertionError('queue did not finish before deadline')
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(worker,['w1','w2','w3']))
 with conn() as c:
  jobs=c.execute('SELECT id,name,state,attempt,started_at,finished_at FROM flow_job ORDER BY id').fetchall()
  stale=c.execute("UPDATE flow_job SET state='FAILED' WHERE id=%s AND owner=%s AND attempt=%s",(1,'dead-worker',dead[2])).rowcount
 assert stale==0 and all(x[2]=='SUCCEEDED' for x in jobs)
 assert jobs[0][3]==2
 assert jobs[3][4]>=max(jobs[0][5],jobs[1][5]) and jobs[4][4]>=jobs[3][5]
 claims=[(x['id'],x['attempt']) for x in events if x['kind']=='lease'];assert len(claims)==len(set(claims))
 return {'schema':schema,'events':events,'jobs':[dict(zip(['id','name','state','attempt','started_at','finished_at'],j)) for j in jobs],'stale_worker_completion_rows':stale,'scope':'Synthetic queue SQL with real PG16.15, three worker threads, committed lease abandonment, lease recovery and fencing of completion. No claim of exactly-once side effects.'}
run('I12','New real PostgreSQL SKIP LOCKED / dependencies / lease / stale completion test',campaign)
