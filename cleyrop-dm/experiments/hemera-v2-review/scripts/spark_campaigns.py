import subprocess,uuid,base64,importlib.metadata
from pyspark.sql import SparkSession,functions as F
from pyspark.sql.connect.session import SparkSession as ConnectSession
import duckdb,sqlglot,cloudpickle
from sqlglot.lineage import lineage
from sqlglot.optimizer.qualify import qualify
from common import *
URL='sc://localhost:15003/;token='+LAB_SECRET
s=SparkSession.builder.remote(URL).getOrCreate()
s.conf.set('spark.sql.session.timeZone','UTC')
def i10():
 arrow=s.sql('SELECT k,SUM(v) AS total FROM VALUES (1,2),(1,3),(2,7) AS t(k,v) GROUP BY k ORDER BY k').toArrow()
 assert arrow.to_pylist()==[{'k':1,'total':5},{'k':2,'total':7}]
 captured=7
 f=F.udf(lambda x:x+captured,'long',useArrow=False)
 values=[r[0] for r in s.range(3).select(f('id')).collect()];assert values==[7,8,9]
 try:s.sparkContext
 except Exception as e:context={'type':type(e).__name__,'message':str(e)}
 else:raise AssertionError('SparkContext unexpectedly available')
 return {'server_version':s.version,'client_type':str(type(s)),'arrow':arrow.to_pylist(),'closure_results':values,'sparkContext':context,'python_client':sys.version,'server_python':'3.10.12','transport_auth':'Synthetic static bearer token; not JWT per user'}
def i11():
 env={**os.environ,'SPARK_REMOTE':URL}
 code='from pyspark.sql import SparkSession;s=SparkSession.builder.getOrCreate();print(type(s).__module__);print(s.range(3).count());s.stop()'
 p=subprocess.run([sys.executable,'-c',code],env=env,text=True,capture_output=True,timeout=45);assert p.returncode==0,(p.stdout,p.stderr);assert 'connect' in p.stdout
 try:s.range(1).rdd
 except Exception as e:rdd={'type':type(e).__name__,'message':str(e)}
 else:raise AssertionError('RDD unexpectedly available')
 assert s.range(3).select(F.monotonically_increasing_id()).count()==3
 # Explicit bad-token rejection uses a separate subprocess to bound client retry.
 code="from pyspark.sql.connect.session import SparkSession;s=SparkSession(connection='sc://localhost:15003/;token=wrong');print(s.sql('SELECT 1').collect())"
 bad=subprocess.run([sys.executable,'-c',code],text=True,capture_output=True,timeout=30)
 assert bad.returncode!=0 and any(t in bad.stderr for t in ('UNAUTHENTICATED','Unauthenticated','Invalid token')),(bad.stdout,bad.stderr[-1000:])
 return {'SPARK_REMOTE_subprocess':p.stdout,'rdd':rdd,'bad_bearer_rejected':True,'client_distribution':importlib.metadata.version('pyspark-client'),'client_has_jars':(Path(importlib.metadata.distribution('pyspark-client').locate_file('pyspark'))/'jars').exists(),'scope':'No JWT verifier or refresh. Static shared token acceptance/rejection only.'}
def artifacts():
 name='hemera_artifact_'+uuid.uuid4().hex[:8];a_dir=ROOT/'artifacts'/'a';b_dir=ROOT/'artifacts'/'b';a_dir.mkdir(parents=True,exist_ok=True);b_dir.mkdir(parents=True,exist_ok=True)
 a_file=a_dir/(name+'.py');b_file=b_dir/(name+'.py');a_file.write_text('VALUE=11\n');b_file.write_text('VALUE=22\n')
 a=ConnectSession(connection=URL+';user_id=synthetic-a');b=ConnectSession(connection=URL+';user_id=synthetic-b')
 def load_value(x):
  import importlib
  return importlib.import_module(name).VALUE+x
 udf=F.udf(load_value,'long',useArrow=False)
 a.addArtifacts(str(a_file),pyfile=True);av=a.range(1).select(udf('id')).collect()[0][0];assert av==11
 missing=None
 try:b.range(1).select(udf('id')).collect()
 except Exception as e:missing=type(e).__name__+': '+str(e)[:700]
 assert missing is not None and 'ModuleNotFoundError' in missing,missing
 b.addArtifacts(str(b_file),pyfile=True);bv=b.range(1).select(udf('id')).collect()[0][0];av2=a.range(1).select(udf('id')).collect()[0][0]
 assert bv==22 and av2==11
 a.stop();b.stop()
 return {'session_a':av,'session_b_before_upload':missing,'session_b_after_upload':bv,'session_a_after_b_upload':av2,'scope':'Two synthetic sessions in one local server. user_id values are client supplied; this is not authenticated tenant isolation.'}
QUERIES=[
 ('date_trunc',"SELECT date_trunc('month', TIMESTAMP '2026-02-03 04:05:06') AS v"),
 ('explode','SELECT explode(array(1,2,3)) AS v'),
 ('collect_list','SELECT collect_list(v) AS v FROM VALUES (1),(2),(NULL) AS t(v)'),
 ('unix_timestamp',"SELECT unix_timestamp('2026-01-02 03:04:05','yyyy-MM-dd HH:mm:ss') AS v"),
 ('try_divide','SELECT try_divide(4,0) AS v, try_divide(5,2) AS w'),
 ('qualify','SELECT v, row_number() OVER (ORDER BY v DESC) AS rn FROM VALUES (1),(2),(3) AS t(v) QUALIFY rn=1'),
]
def canonical(values):return json.loads(json.dumps(values,default=str))
def golden():
 out=[]
 for name,source in QUERIES:
  spark_sql=sqlglot.transpile(source,read='spark',write='spark')[0];duck_sql=sqlglot.transpile(source,read='spark',write='duckdb')[0]
  sr=[list(r) for r in s.sql(spark_sql).collect()];dr=[list(r) for r in duckdb.sql(duck_sql).fetchall()]
  equal=canonical(sr)==canonical(dr);out.append({'name':name,'spark_sql':spark_sql,'duckdb_sql':duck_sql,'spark':canonical(sr),'duckdb':canonical(dr),'equal':equal})
 write('golden-details',out)
 assert all(x['equal'] for x in out),out
 return {'queries':out,'scope':'Six deterministic synthetic queries, compared as typed values normalized to JSON; not broad bitwise SQL parity.'}
def edge():
 qs=["SELECT substr('abc',0,2) AS v","SELECT 5/2 AS v, CAST(5 AS BIGINT) DIV CAST(2 AS BIGINT) AS w","SELECT CAST(NULL AS INT) IN (1,NULL) AS v, coalesce(NULL,3) AS w"]
 out=[]
 for q in qs:
  d=sqlglot.transpile(q,read='spark',write='duckdb')[0]
  sr=canonical([list(r) for r in s.sql(q).collect()]);dr=canonical([list(r) for r in duckdb.sql(d).fetchall()]);out.append({'spark_sql':q,'duckdb_sql':d,'spark':sr,'duckdb':dr,'equal':sr==dr})
 return {'cases':out,'all_equal_on_these_cases':all(x['equal'] for x in out),'scope':'Boundary samples, no universal SQL equivalence claim.'}
def i7():
 schema={'raw_orders':{'amount':'DOUBLE','currency':'TEXT'},'fx':{'currency':'TEXT','rate':'DOUBLE'}}
 q='WITH orders AS (SELECT amount,currency FROM raw_orders) SELECT o.amount*f.rate AS amount_eur FROM orders o JOIN fx f ON o.currency=f.currency'
 ast=qualify(sqlglot.parse_one(q),schema=schema)
 tree=lineage('amount_eur',ast,schema=schema)
 leaves=[{'name':n.name,'expression':n.expression.sql()} for n in tree.walk() if not n.downstream]
 assert any('raw_orders' in n['expression'] for n in leaves) and any('fx' in n['expression'] for n in leaves),leaves
 return {'qualified_sql':ast.sql(),'leaves':leaves,'version':sqlglot.__version__}
def i9():
 offset=17;fn=lambda x:x+offset
 encoded=base64.b64encode(cloudpickle.dumps(fn)).decode()
 code='import cloudpickle,base64;f=cloudpickle.loads(base64.b64decode('+repr(encoded)+'));print(f(5))'
 p=subprocess.run([sys.executable,'-c',code],text=True,capture_output=True,timeout=15);assert p.returncode==0 and p.stdout.strip()=='22'
 return {'result':22,'cloudpickle':cloudpickle.__version__,'python':sys.version,'cross_process':True}
def catalog_read():
 # Token reaches Iceberg REST; the Spark gRPC bearer remains separate.
 for k,v in {'':'org.apache.iceberg.spark.SparkCatalog','.type':'rest','.uri':'http://lakekeeper:8181/catalog','.warehouse':'review','.token':token(),'.io-impl':'org.apache.iceberg.aws.s3.S3FileIO','.header.X-Iceberg-Access-Delegation':'remote-signing'}.items():s.conf.set('spark.sql.catalog.review'+k,v)
 t=json.loads((EVIDENCE/'I3.json').read_text())['details']['table']
 full='review.'+t
 result=[r.asDict() for r in s.sql('SELECT * FROM '+full+' ORDER BY id').collect()]
 expected=json.loads((EVIDENCE/'I3.json').read_text())['details']['main'];assert result==expected
 return {'table':full,'spark_rows':result,'pyiceberg_rows':expected,'scope':'Same Iceberg v2 table read through Lakekeeper and remote signing; no schema transition yet.'}
if __name__=='__main__':
 for name,scope,fn in [('I10','New Spark Connect4.1.2 SQL Arrow closure and unsupported API checks',i10),('I11','New pure Python client, SPARK_REMOTE, RDD, real static bearer rejection',i11),('SPARK-ARTIFACTS','Live addArtifacts and two synthetic session separation',artifacts),('I6','New SQLGlot30.12 transpilation and live Spark versus DuckDB golden subset',golden),('I7','New schema-qualified AST column lineage',i7),('I8','New Spark versus DuckDB boundary semantics samples',edge),('I9','New cloudpickle3.1.2 cross-process closure',i9),('MULTI-ENGINE','New same-table PyIceberg and Spark through authenticated Lakekeeper',catalog_read)]:run(name,scope,fn)
 s.stop()
