import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'evidence'
not_run={
 'INT-2':'JWT interceptor, token refresh and authenticated tenant isolation not deployed. Static bearer and synthetic-session artifacts were probed separately.',
 'INT-4':'No Kafka/NATS sink, fault injection, durable delivery or duplicate/loss reconciliation test.',
 'INT-6':'No requested_subject token exchange or long-job re-exchange. Keycloak only issues synthetic service credentials in this bench.',
 'INT-7':'No Kubernetes cluster or operator was accessed. Local Spark restart is not this gate.',
 'INT-8':'Only PyIceberg and Spark expand-column/read-cache behavior probed. No Trino or complete migration matrix.',
 'INT-9':'SQLMesh compiler-only acceptance not rerun in this bench.',
 'INT-11':'Doc02 INT-11 defines SQLMesh/dbt region writes under WAP, including CTAS/replace. Not executed.',
 'INT-12':'Doc02 INT-12 defines monitoring of dbt Core/Fusion and adapter readiness. No runtime acceptance test executed.',
 'INT-13':'Doc02 INT-13 defines dbt-spark Iceberg materializations through Lakekeeper. Not executed; target adapters must be without JVM.',
 'INT-14':'No Trino OPA bridge, OAuth2 end-user identity, row/column permissions test.',
}
for case,reason in not_run.items():
 (E/(case+'.json')).write_text(json.dumps({'campaign':case,'executed':False,'status':'not_executed','reason':reason},indent=2)+'\n')
rows=[]
for case in [*[f'I{i}' for i in range(1,13)],*[f'INT-{i}' for i in range(1,15)],'AUTH','WAP-VETO','OPENFGA-TTL','SPARK-ARTIFACTS','MULTI-ENGINE','SCHEMA-TRANSITION','STAGING-ISOLATION']:
 p=E/(case+'.json')
 if p.exists():
  value=json.loads(p.read_text());rows.append({k:value[k] for k in ['campaign','executed','status','scope','reason'] if k in value})
(E/'results.json').write_text(json.dumps({'kind':'new_synthetic_local_campaigns_2026-10-02','historical_campaigns_replayed_verbatim':False,'final_platform_jvm_policy':'zero JVM; Spark and Keycloak are temporary parity dependencies only','production_atomicity_fencing_failover_proven':False,'cases':rows,'interpretations':{'I6':'Original six-query execution compared timestamp serialization without full UTC normalization; not evidence of a date_trunc engine defect. Strict INT-1 normalizes UTC and date_trunc passes.','I8':'Probe passed by detecting behavior. Data parity FAILED for substr at zero: ab versus a.','INT-3':'Two threads, PostgreSQL advisory transaction lock, ancestry check and catalog CAS. No zombie writer or failover fencing claim.','INT-10':'SQL, UDF and Arrow outputs match. Exact error API parity fails: pure-client RDD uses PySparkAttributeError, full client PySparkNotImplementedError. No worker image acceptance.','INT-5':'Native model rejects undefined condition. Standalone OpenFGA conditional check is not Lakekeeper TTL integration.'}},indent=2)+'\n')
print(json.dumps({status:sum(x['status']==status for x in rows) for status in ['passed','failed','not_executed']}))
