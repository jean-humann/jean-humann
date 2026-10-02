from common import *
f=headers('openfga');auth=json.loads((EVIDENCE/'AUTH.json').read_text())['details'];store=next(s['id'] for s in requests.get(FGA+'/stores',headers=f).json()['stores'] if s['name']=='lakekeeper')
tup={'user':'user:oidc~synthetic-ungranted','relation':'select','object':'lakekeeper_table:'+auth['table_uuid'],'condition':{'name':'unexpired','context':{'expires_at':'2026-10-02T12:00:00Z'}}}
r=requests.post(FGA+f'/stores/{store}/write',headers=f,json={'authorization_model_id':auth['native_model_id'],'writes':{'tuple_keys':[tup]}},timeout=15)
assert r.status_code==400,(r.status_code,r.text)
write('INT-5',{'campaign':'INT-5','executed':True,'status':'failed','scope':'Native Lakekeeper 0.12.0 OpenFGA model accepts no conditional grants. Standalone TTL was tested in another store only.','native_condition_write_http':r.status_code,'native_condition_write_error':r.json(),'native_model_conditions':auth['native_model_conditions'],'purge_reconciler':'not executed: no reconciler implementation in this bench','timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
print('INT-5 failed native conditional grant not supported by loaded model')
