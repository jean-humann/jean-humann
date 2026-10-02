import subprocess
from common import *
code=r'''
import json,importlib.metadata
from pathlib import Path
from pyspark.sql import SparkSession,functions as F
s=SparkSession.builder.remote('sc://localhost:15003/;token=hemera-v2-review-local-only').getOrCreate()
add=9
udf=F.udf(lambda x:x+add,'long',useArrow=False)
try:s.range(1).rdd
except Exception as e:unsupported=type(e).__name__
print(json.dumps({'version':s.version,'sql':[r.asDict() for r in s.sql('SELECT 2 AS id, 3 AS v').collect()],'udf':[r[0] for r in s.range(3).select(udf('id')).collect()],'unsupported_rdd':unsupported,'arrow':s.range(3).toArrow().to_pylist()}))
s.stop()
'''
def check():
 results={}
 for name in ['spark-client-venv','full-client-venv']:
  p=subprocess.run([str(ROOT/name/'bin/python'),'-c',code],capture_output=True,text=True,timeout=60);assert p.returncode==0,p.stderr
  results[name]=json.loads(p.stdout)
 assert results['spark-client-venv']==results['full-client-venv'],results
 return {'results':results,'scope':'Two actual installed distributions, pyspark-client4.1.2 and pyspark[connect]4.1.2, same Python3.10.19, one real Spark server. Worker container packaging not tested.'}
run('INT-10','Pure Python client vs full PySpark Connect functional subset',check)
