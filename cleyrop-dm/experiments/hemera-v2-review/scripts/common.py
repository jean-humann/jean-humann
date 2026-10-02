import json,time,traceback,datetime,sys
from pathlib import Path
import requests,os
ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence'
CATALOG='http://lakekeeper:8181' if os.environ.get('HEMERA_INTERNAL') else 'http://127.0.0.1:18181'
FGA='http://openfga:8080' if os.environ.get('HEMERA_INTERNAL') else 'http://127.0.0.1:18081'
ISSUER=('http://keycloak:8080' if os.environ.get('HEMERA_INTERNAL') else 'http://127.0.0.1:18080')+'/realms/hemera-v2-review'
LAB_SECRET='hemera-v2-review-local-only'
def token(client='review-admin'):
 r=requests.post(ISSUER+'/protocol/openid-connect/token',data={'grant_type':'client_credentials','client_id':client,'client_secret':LAB_SECRET},timeout=15)
 r.raise_for_status()
 return r.json()['access_token']
def headers(client='review-admin'):
 return {'Authorization':'Bearer '+token(client),'Content-Type':'application/json'}
def write(name,value):
 (EVIDENCE/(name+'.json')).write_text(json.dumps(value,indent=2,default=str)+'\n')
def run(case,scope,fn):
 start=time.monotonic()
 out={'campaign':case,'executed':True,'scope':scope,'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:out['details']=fn();out['status']='passed'
 except Exception as e:out.update(status='failed',exception=type(e).__name__,message=str(e),traceback=traceback.format_exc())
 out['seconds']=round(time.monotonic()-start,3)
 write(case,out)
 print(case,out['status'],out.get('message',''),flush=True)
 return out
