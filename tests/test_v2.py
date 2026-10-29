"""TEST DATA: v2 assets, real domain formats, statistical contracts and audit history."""
import json,io,zipfile,hashlib,sys,time
import numpy as np
import h5py
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage
from backend.v2 import assets,analysis
from backend.statistics_engine import persist

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    return TestClient(app)

def test_asset_versions_hash_and_comparison(client,tmp_path):
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'one.csv').write_text('x\n1\n')
    asset=client.post('/api/v2/assets',json={'label':'TEST dataset','kind':'dataset','path':str(root)}).json()
    metadata=client.post(f"/api/v2/assets/{asset['id']}/versions").json()
    assert client.post('/api/v2/asset-versions/'+metadata['id']+'/verify').json()['status']=='UNKNOWN'
    first=client.post(f"/api/v2/assets/{asset['id']}/versions?hash_content=true").json()
    assert client.post('/api/v2/asset-versions/'+first['id']+'/verify').json()['status']=='PASS'
    (root/'one.csv').write_text('x\n2\n');(root/'new.csv').write_text('x\n3\n')
    assert client.post('/api/v2/asset-versions/'+first['id']+'/verify').json()['status']=='FAIL'
    second=client.post(f"/api/v2/assets/{asset['id']}/versions?hash_content=true").json()
    diff=client.get('/api/v2/asset-versions/compare',params={'left':first['id'],'right':second['id']}).json()
    assert diff['added']==['new.csv'] and diff['changed']==['one.csv']

@pytest.mark.parametrize('suffix',['npz','h5'])
def test_real_simulation_formats(client,tmp_path,suffix):
    path=tmp_path/('TEST_field.'+suffix);array=np.array([[1.,2.],[3.,np.nan]])
    if suffix=='npz':np.savez(path,temperature=array)
    else:
        with h5py.File(path,'w') as f:f['temperature']=array
    r=client.post('/api/v2/plugins/simulation/parse',json={'path':str(path),'definitions':{'temperature':{'unit':'K'}}})
    assert r.status_code==200,r.text
    result=r.json();field=result['fields']['temperature']
    assert field['mean']==2 and field['nonfinite']==1 and field['shape']==[2,2]
    assert result['definitions']['temperature']['unit']=='K'

def test_pose_and_deep_learning_csv(client,tmp_path):
    path=tmp_path/'TEST_pose.csv';path.write_text('rotation_error,translation_error\n1,0.2\n2,0.3\n')
    for kind in ('pose','deep_learning'):
        result=client.post('/api/v2/plugins/'+kind+'/parse',json={'path':str(path),'definitions':{'rotation_error':{'unit':'degree','method':'TEST protocol'}}}).json()
        assert result['series']['rotation_error']==[1,2] and result['source']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()

def test_audits_pdf_resources_and_sse(client,tmp_path):
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'m.csv').write_text('loss\n1\n2\n')
    s=client.post('/api/import',json={'path':str(root)}).json();id=s['id']
    a=client.post(f'/api/v2/snapshots/{id}/audits',json={'full_hash':True}).json()
    assert any(f['rule']=='source_content' and f['status']=='PASS' for f in a['findings'])
    (root/'m.csv').write_text('loss\n9\n')
    b=client.post(f'/api/v2/snapshots/{id}/audits',json={'full_hash':True}).json()
    assert any(f['rule']=='source_content' and f['status']=='FAIL' for f in b['findings'])
    assert len(client.get(f'/api/v2/snapshots/{id}/audits').json())==2
    assert client.get(f'/api/v2/snapshots/{id}/report.pdf').content.startswith(b'%PDF')
    assert client.get('/api/v2/resources').json()['hard_limits'] is False
    run=client.post('/api/executions',json={'argv':[sys.executable,'-c','pass'],'cwd':str(tmp_path)}).json()
    response=client.get('/api/v2/executions/'+run['id']+'/events?max_events=1')
    assert 'Pending' in response.text and response.headers['content-type'].startswith('text/event-stream')

def test_dependency_cycles_and_seeded_random_batch(client,tmp_path):
    spec={'argv':[sys.executable,'-c','pass'],'cwd':str(tmp_path)}
    one=client.post('/api/executions',json=spec).json();two=client.post('/api/executions',json=spec).json()
    assert client.put('/api/v2/executions/'+one['id']+'/dependencies',json={'dependencies':[two['id']]}).status_code==200
    assert client.put('/api/v2/executions/'+two['id']+'/dependencies',json={'dependencies':[one['id']]}).status_code==422
    req={'spec':spec,'choices':{'seed':[1,2,3]},'count':3,'seed':42}
    first=client.post('/api/v2/execution-batches/random',json=req).json();second=client.post('/api/v2/execution-batches/random',json=req).json()
    assert [r['spec']['params'] for r in first['runs']]==[r['spec']['params'] for r in second['runs']]
    assert all(r['state']=='Pending' for r in first['runs'])

def test_batch_welch_holm_and_correlation(client):
    runs=[]
    for group,values in [('a',[1.,2.,3.]),('b',[3.,5.,6.])]:
        for seed,v in enumerate(values):
            runs.append({'id':group+str(seed),'name':group+str(seed),'params':{'model_version':group,'seed':seed,'dataset':'TEST','dataset_version':'1','split':'test','evaluation_protocol':'test-v1'},'metrics':{'loss':v,'second':v*2},'series':{'loss':[v,v+1,v+2],'second':[v*2,v*2+2,v*2+4]},'metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST mean'}},'sources':[]})
    sid=storage.save('TEST_DATA',{'root':'TEST_DATA','runs':runs,'issues':[],'evidence':[],'git':{'commit':None,'status':None}})
    refs=[{'snapshot_id':sid,'run_id':r['id'],'metric':'loss'} for r in runs]
    result=client.post('/api/v2/analyses/independent',json={'left':refs[:3],'right':refs[3:],'independent_runs':True})
    assert result.status_code==200,result.text
    assert result.json()['result']['mean_difference']==pytest.approx(-8/3)
    assert client.post('/api/v2/analyses/independent',json={'left':refs[:3],'right':refs[3:]}).status_code==422
    pids=[persist({'method':'TEST p-value fixture','result':{'p_two_sided':p}})['id'] for p in (.01,.04,.03)]
    adjusted=client.post('/api/v2/analyses/holm',json={'ids':pids}).json()['result']
    assert [p['p_adjusted'] for p in adjusted]==pytest.approx([.03,.06,.06])
    corr=client.post('/api/v2/analyses/correlation',json={'reference':refs[0],'other_metric':'second'}).json()
    assert corr['result']['rho']==pytest.approx(1) and 'p_two_sided' not in corr['result']
    batch=client.post('/api/v2/analyses/batch',json={'refs':[{k:v for k,v in ref.items() if k!='metric'} for ref in refs],'group_by':['model_version']}).json()
    assert batch['result']['loss']['compatibility']['status']=='PASS'
    assert len(batch['result']['loss']['groups'])==2

def test_reference_exchange_cache_repair_and_offline_verifier(client,tmp_path):
    from backend.packages import bundle
    from backend.v2.verify_package import verify
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'m.csv').write_text('loss\n1\n2\n')
    snapshot=client.post('/api/import',json={'path':str(root)}).json();sid=snapshot['id']
    (storage.DB/'metrics'/f'{sid}.parquet').write_bytes(b'INTENTIONALLY CORRUPT TEST CACHE')
    assert [r['value'] for r in storage.query_metrics(sid,'loss')]==[1,2]
    archive=tmp_path/'TEST-evidence.zip';archive.write_bytes(bundle(sid));assert verify(archive)['status']=='PASS'
    dvc=root/'data.dvc';dvc.write_text('outs:\n  - path: data.csv\n    md5: test-declared-hash\n')
    inspected=client.post('/api/v2/integrations/dvc/inspect',json={'path':str(dvc)}).json()
    assert inspected['outputs'][0]['md5']=='test-declared-hash' and inspected['status']=='UNKNOWN'
    crate=client.get(f'/api/v2/snapshots/{sid}/ro-crate-metadata.json').json();path=root/'ro-crate-metadata.json';path.write_text(json.dumps(crate))
    assert client.post('/api/v2/integrations/ro-crate/inspect',json={'path':str(path)}).status_code==200
    bad=tmp_path/'TEST-tampered.zip'
    with zipfile.ZipFile(archive) as z,zipfile.ZipFile(bad,'w') as out:
        for name in z.namelist():out.writestr(name,b'BAD' if name=='report.md' else z.read(name))
    with pytest.raises(ValueError):verify(bad)

def test_registered_experiment_association_history(client,tmp_path):
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'m.csv').write_text('loss\n1\n')
    project=client.post('/api/tracking/projects',json={'path':str(root)}).json()
    first=client.post('/api/v2/experiments',json={'project_id':project['id'],'label':'TEST first'}).json()
    second=client.post('/api/v2/experiments',json={'project_id':project['id'],'label':'TEST corrected'}).json()
    snapshot=client.post('/api/import',json={'path':str(root)}).json();sid=snapshot['id'];rid=snapshot['runs'][0]['id']
    for eid in (first['id'],second['id']):
        assert client.post('/api/v2/associations',json={'snapshot_id':sid,'run_id':rid,'experiment_id':eid}).status_code==201
    history=client.get(f'/api/v2/snapshots/{sid}/associations').json();assert len(history)==2
    g=client.get(f'/api/v2/snapshots/{sid}/graph').json()
    assert any(n['id']==second['id'] and n['type']=='experiment' for n in g['nodes'])
    assert client.get(f'/api/projects/{sid}').json()['runs']==snapshot['runs']

def test_persisted_welch_normal_degenerate_conditions(client):
    from backend.v2.analysis import independent
    with pytest.raises(ValueError):independent([],[],False)

def test_time_series_pareto_and_pdf_regeneration(client,tmp_path):
    runs=[]
    for i,(loss,speed) in enumerate([(1.,5.),(2.,7.),(3.,4.)]):
        runs.append({'id':'TEST-'+str(i),'name':'TEST '+str(i),'params':{'seed':i,'dataset':'TEST','dataset_version':'1','split':'test','evaluation_protocol':'v1'},'metrics':{'loss':loss,'speed':speed},'series':{'loss':[3.,2.,1.],'speed':[1.,2.,3.]},'metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST'},'speed':{'direction':'maximize','unit':'1','method':'TEST'}},'sources':[]})
    sid=storage.save('TEST_DATA',{'root':'TEST_DATA','runs':runs,'evidence':[],'issues':[],'git':{'commit':None,'status':None}})
    ref={'snapshot_id':sid,'run_id':'TEST-0','metric':'loss'}
    trend=client.post('/api/v2/analyses/time-series',json=ref).json();assert trend['result']['slope_per_step']==pytest.approx(-1)
    refs=[{'snapshot_id':sid,'run_id':r['id']} for r in runs]
    frontier=client.post('/api/v2/analyses/pareto',json={'refs':refs,'metrics':['loss','speed']}).json()
    assert frontier['result']['nondominated_runs']==['TEST-0','TEST-1']
    first=client.get(f'/api/v2/snapshots/{sid}/report.pdf').content
    second=client.get(f'/api/v2/snapshots/{sid}/report.pdf').content
    assert hashlib.sha256(first).hexdigest()==hashlib.sha256(second).hexdigest()
    assert first.startswith(b'%PDF')

def test_plugin_parse_is_persisted_and_nulls_retained(client,tmp_path):
    path=tmp_path/'TEST_training.csv';path.write_text('train_loss,validation_loss\n3,4\nNaN,2\n')
    result=client.post('/api/v2/plugins/deep_learning/parse',json={'path':str(path),'definitions':{'train_loss':{'unit':'1','direction':'minimize'}}}).json()
    assert result['series']['train_loss']==[3,None]
    record=client.get('/api/analyses/'+result['analysis_id']).json()
    assert record['result']['source']['sha256']==result['source']['sha256']
    assert record['result']['raw_preview'][1]['train_loss'] is None

def test_database_handles_close_after_context(client):
    import sqlite3
    connection=storage.connect()
    with connection as c:c.execute('SELECT 1')
    with pytest.raises(sqlite3.ProgrammingError):connection.execute('SELECT 1')

def test_local_origin_and_host_boundaries(client):
    assert client.post('/api/import',json={'path':'TEST invalid'},headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.get('http://untrusted.example/api/projects').status_code==400

def test_physical_bounds_require_matching_units(client):
    run={'id':'TEST-bound','name':'TEST','params':{},'metrics':{'temperature':300},'series':{'temperature':[300,1000,None]},'metric_definitions':{'temperature':{'unit':'K'}},'sources':[]}
    sid=storage.save('TEST',{'root':'TEST','runs':[run],'evidence':[],'issues':[],'git':{'commit':None,'status':None}})
    def check(unit):return client.post(f'/api/v2/snapshots/{sid}/audits',json={'bounds':[{'metric':'temperature','minimum':0,'maximum':500,'unit':unit}]}).json()
    assert next(f for f in check('K')['findings'] if f['rule']=='physical_range')['status']=='FAIL'
    assert next(f for f in check('C')['findings'] if f['rule']=='physical_range')['status']=='UNKNOWN'

def test_tracking_settings_persist_across_engine_restart(client):
    from backend.main import tracking_engine
    from backend.tracking.engine import Engine
    response=client.put('/api/v2/tracking/settings',json={'interval_seconds':2,'verification_interval_seconds':30,'max_read_mib':2,'delay_per_file_seconds':.001})
    assert response.status_code==200
    restored=Engine(tracking_engine().db)
    assert restored.interval==2 and restored.verification_interval==30 and restored.max_read==2*1048576 and restored.scan_delay==.001
