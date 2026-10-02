from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
clients=[]
for name,aud in [('review-admin','lakekeeper'),('review-outsider','lakekeeper'),('openfga','openfga')]:
 clients.append({'clientId':name,'enabled':True,'publicClient':False,'secret':'hemera-v2-review-local-only','serviceAccountsEnabled':True,'standardFlowEnabled':False,'directAccessGrantsEnabled':False,'protocol':'openid-connect','protocolMappers':[{'name':'audience','protocol':'openid-connect','protocolMapper':'oidc-audience-mapper','config':{'included.client.audience':aud,'access.token.claim':'true','id.token.claim':'false'}}]})
(ROOT/'realm.json').write_text(json.dumps({'realm':'hemera-v2-review','enabled':True,'sslRequired':'none','accessTokenLifespan':1800,'clients':clients},indent=2))
(ROOT/'seaweed-iam.json').write_text(json.dumps({'identities':[{'name':'hemera-v2-review','credentials':[{'accessKey':'hemera-v2-review','secretKey':'hemera-v2-review-local-only'}],'actions':['Admin','Read','List','Tagging','Write']}]},indent=2))
(ROOT/'init.sql').write_text('CREATE DATABASE lakekeeper;\nCREATE DATABASE openfga;\nCREATE DATABASE flowqueue;\n')
