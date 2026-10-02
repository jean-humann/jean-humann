"""Expand-only schema change with two real engines, no Trino coverage."""
import subprocess
from pyspark.sql import SparkSession
from common import *
s=SparkSession.builder.remote('sc://localhost:15003/;token='+LAB_SECRET).getOrCreate()
for k,v in {'':'org.apache.iceberg.spark.SparkCatalog','.type':'rest','.uri':'http://lakekeeper:8181/catalog','.warehouse':'review','.token':token(),'.io-impl':'org.apache.iceberg.aws.s3.S3FileIO','.header.X-Iceberg-Access-Delegation':'remote-signing'}.items():s.conf.set('spark.sql.catalog.review'+k,v)
def campaign():
 table=json.loads((EVIDENCE/'I3.json').read_text())['details']['table'];full='review.'+table
 before=[r.asDict() for r in s.sql('SELECT * FROM '+full+' ORDER BY id').collect()]
 code="import sys;sys.path.insert(0,'/lab/scripts');from catalog_campaigns import *;t=catalog().load_table("+repr(table)+");t.update_schema().add_column('expanded_note',StringType()).commit();print(t.schema().model_dump_json())"
 p=subprocess.run(['docker','compose','-f',str(ROOT/'compose.yaml'),'--profile','client','run','--rm','--no-deps','client','/lab/linux-venv/bin/python','-c',code],text=True,capture_output=True,timeout=60);assert p.returncode==0,p.stderr
 cached=[r.asDict() for r in s.sql('SELECT * FROM '+full+' ORDER BY id').collect()]
 s.sql('REFRESH TABLE '+full).collect()
 refreshed=[r.asDict() for r in s.sql('SELECT * FROM '+full+' ORDER BY id').collect()]
 assert all('expanded_note' not in r for r in before)
 assert all(r.get('expanded_note','missing') is None for r in refreshed)
 assert [{k:v for k,v in r.items() if k!='expanded_note'} for r in refreshed]==before
 return {'table':full,'spark_before':before,'spark_without_refresh':cached,'spark_after_refresh':refreshed,'pyiceberg_new_schema':json.loads(p.stdout),'missing':'Trino, contract/drop changes, concurrent long-running query and migration orchestrator were not tested.'}
run('SCHEMA-TRANSITION','PyIceberg expand-only change with Spark cached reader and REFRESH TABLE',campaign)
s.stop()
