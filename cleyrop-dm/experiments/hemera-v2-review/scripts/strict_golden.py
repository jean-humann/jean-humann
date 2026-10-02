import time
from common import *
os.environ['TZ']='UTC';time.tzset()
import sqlglot,duckdb
from pyspark.sql import SparkSession
s=SparkSession.builder.remote('sc://localhost:15003/;token='+LAB_SECRET).getOrCreate();s.conf.set('spark.sql.session.timeZone','UTC');duckdb.sql("SET TimeZone='UTC'")
queries=["SELECT date_trunc('month',TIMESTAMP '2026-02-03 04:05:06') AS v","SELECT unix_timestamp('2026-01-02 03:04:05','yyyy-MM-dd HH:mm:ss') AS v","SELECT substr('abc',0,2) AS v"]
results=[]
for q in queries:
 dq=sqlglot.transpile(q,read='spark',write='duckdb')[0];sq=sqlglot.transpile(q,read='spark',write='spark')[0]
 sa=s.sql(sq).toArrow();da=duckdb.sql(dq).arrow().read_all()
 results.append({'spark_sql':sq,'duckdb_sql':dq,'spark_schema':str(sa.schema),'duckdb_schema':str(da.schema),'spark_rows':sa.to_pylist(),'duckdb_rows':da.to_pylist(),'arrow_equal':sa.equals(da)})
write('INT-1',{'campaign':'INT-1','executed':True,'status':'passed' if all(x['arrow_equal'] for x in results) else 'failed','timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Strict Arrow schema/value comparison, explicit UTC client/server and DuckDB, three boundary queries','details':results})
print('INT-1', ['equal' if x['arrow_equal'] else 'different' for x in results]);s.stop()
