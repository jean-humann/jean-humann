import json,requests,base64
from common import *
h=headers()
r=requests.post(CATALOG+'/management/v1/bootstrap',headers=h,json={'accept-terms-of-use':True,'is-operator':True},timeout=30)
assert r.status_code in (200,204,409),(r.status_code,r.text)
warehouse={'warehouse-name':'review','project-id':'00000000-0000-0000-0000-000000000000','storage-profile':{'type':'s3','bucket':'hemera-v2-review','key-prefix':'warehouse','endpoint':'http://storage:8333','region':'local-01','path-style-access':True,'flavor':'minio','sts-enabled':False},'storage-credential':{'type':'s3','credential-type':'access-key','access-key-id':'hemera-v2-review','secret-access-key':LAB_SECRET}}
r=requests.post(CATALOG+'/management/v1/warehouse',headers=h,json=warehouse,timeout=60)
assert r.status_code in (200,201,409),(r.status_code,r.text)
if r.status_code==409:
 r=requests.get(CATALOG+'/management/v1/warehouse',headers=h,timeout=30)
 print('warehouses',r.status_code,r.text)
else:
 result=r.json();(ROOT/'runtime.json').write_text(json.dumps(result,indent=2));print(result)
r=requests.get(FGA+'/stores',headers=headers('openfga'),timeout=15)
assert r.status_code==200,(r.status_code,r.text)
write('fga-stores',r.json())
print('OpenFGA stores',r.json())
