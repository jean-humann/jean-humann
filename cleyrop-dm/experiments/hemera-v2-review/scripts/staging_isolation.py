from catalog_campaigns import *
def scan_signed(reader,snapshot):
 import pyarrow.parquet as pq
 from io import BytesIO
 result=[]
 for task in reader.scan(snapshot_id=snapshot).plan_files():
  location=task.file.file_path
  uri='http://storage:8333/'+location.removeprefix('s3://')
  response=requests.post(CATALOG+'/catalog/'+reader.config['s3.signer.endpoint'],headers=headers('review-outsider'),json={'method':'GET','region':'local-01','uri':uri,'headers':{}},timeout=15)
  response.raise_for_status();signature=response.json()
  response=requests.get(signature['uri'],headers={k:','.join(v) for k,v in signature['headers'].items()},timeout=15)
  response.raise_for_status();result.extend(pq.read_table(BytesIO(response.content)).to_pylist())
 return sorted(result,key=lambda x:x['id'])
def probe():
 c,t,ident=table('staging_privacy');base=t.current_snapshot().snapshot_id
 t.manage_snapshots().create_branch(base,'wap_unpublished').commit();t.append(data(-99,'AUDIT_VETO_PAYLOAD'),branch='wap_unpublished');staged=t.refs()['wap_unpublished'].snapshot_id
 table_id=WAREHOUSE+'/'+t.config['s3.signer.endpoint'].split('/tabular-id/')[1].split('/')[0]
 fh=headers('openfga');store=next(x['id'] for x in requests.get(FGA+'/stores',headers=fh).json()['stores'] if x['name']=='lakekeeper')
 model=requests.get(FGA+f'/stores/{store}/authorization-models',headers=fh).json()['authorization_models'][0]['id']
 payload=token('review-outsider').split('.')[1];subject=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))['sub']
 tup={'user':'user:oidc~'+subject,'relation':'select','object':'lakekeeper_table:'+table_id}
 r=requests.post(FGA+f'/stores/{store}/write',headers=fh,json={'authorization_model_id':model,'writes':{'tuple_keys':[tup]}},timeout=15);r.raise_for_status()
 try:
  reader=catalog('review-outsider').load_table(ident)
  published=rows(reader);unpublished=scan_signed(reader,staged)
  t.manage_snapshots().remove_branch('wap_unpublished').commit()
  reader.refresh();after_veto=scan_signed(reader,staged)
  details={'table':ident,'reader_grant':'select on this table only','published_main':published,'unpublished_staging':unpublished,'read_snapshot_id_after_veto':after_veto,'staging_snapshot_id':staged,'ordinary_reader_saw_unpublished_payload':any(x['id']==-99 for x in unpublished),'scope':'Real OIDC reader, native OpenFGA select, Lakekeeper metadata and S3 remote signing; no storage credentials in client. Main remains unchanged but staging is readable within the same table.'}
  write('STAGING-ISOLATION',{'campaign':'STAGING-ISOLATION','executed':True,'status':'failed' if details['ordinary_reader_saw_unpublished_payload'] else 'passed','timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'P0 unpublished rows must be invisible to ordinary dataset readers','details':details})
  print('STAGING-ISOLATION', 'failed' if details['ordinary_reader_saw_unpublished_payload'] else 'passed')
 finally:
  requests.post(FGA+f'/stores/{store}/write',headers=fh,json={'authorization_model_id':model,'deletes':{'tuple_keys':[tup]}},timeout=15).raise_for_status()
probe()
