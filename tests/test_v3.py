"""TEST DATA ONLY: real programs, bounded scientific files, restart and evidence tests."""
import json,sys,time,threading
from pathlib import Path
import numpy as np
import h5py
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage
from backend.orchestrator import Orchestrator
from backend.v3 import workflows,documents,reproduction,data_studio,suites
from backend.v2 import assets

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    return TestClient(app)

def wait(engine,id,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        r=engine.get(id)
        if r['state'] in ('Succeeded','Failed','Interrupted','Cancelled'):return r
        time.sleep(.05)
    raise AssertionError(engine.get(id))

def spec(tmp_path,script=None):
    script=script or "import os,pathlib; p=pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR']); (p/'metrics.csv').write_text('loss\\n3\\n1\\n')"
    return {'argv':[sys.executable,'-c',script],'cwd':str(tmp_path),'params':{'seed':7,'dataset':'TEST','dataset_version':'1','split':'test','evaluation_protocol':'TEST-v1','metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST mean'}}},'timeout_seconds':15}

def test_scenario_a_real_reproduction(client,tmp_path):
    engine=Orchestrator(tmp_path/'executor');engine.start()
    try:
        entry=tmp_path/'TEST_DATA_train.py';entry.write_text((Path(__file__).parents[1]/'examples'/'TEST_DATA_train.py').read_text())
        cfg=spec(tmp_path);cfg['argv']=[sys.executable,str(entry)]
        original=engine.create(cfg);engine.enqueue(original['id']);done=wait(engine,original['id']);assert done['state']=='Succeeded',done
        record=reproduction.create(engine,done['id'],[],{'loss':{'atol':0.,'rtol':0.}})
        assert record['environment']['runner']['python'] and record['environment']['target_environment_status']=='UNKNOWN'
        with pytest.raises(ValueError,match='confirmation'):reproduction.launch(engine,record['id'],False)
        replay=reproduction.launch(engine,record['id'],True);assert wait(engine,replay['execution'])['state']=='Succeeded'
        with pytest.raises(ValueError,match='already'):reproduction.launch(engine,record['id'],True)
        report=reproduction.evaluate(engine,record['id']);assert report['scorecard']['result_consistency']['status']=='PASS'
        assert report['scorecard']['environment_completeness']['status']=='UNKNOWN' and report['scientific_correctness']=='UNKNOWN'
        assert report['comparisons'][0]['original']==report['comparisons'][0]['replayed']
        series=storage.get(done['snapshot_id'])['runs'][0]['series']['loss'];assert len(series)==40 and series[-1]<series[0]
        assert (Path(done['output_dir'])/'checkpoint.npz').is_file()
    finally:engine.stop()

def test_reproduction_source_changes_and_crash_reservation(client,tmp_path,monkeypatch):
    entry=tmp_path/'TEST_train.py';entry.write_text("import os,pathlib; (pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR'])/'metrics.csv').write_text('loss\\n1\\n')")
    engine=Orchestrator(tmp_path/'executor');engine.start()
    try:
        cfg=spec(tmp_path);cfg['argv']=[sys.executable,str(entry)];original=engine.create(cfg);engine.enqueue(original['id']);assert wait(engine,original['id'])['state']=='Succeeded'
        manifest=reproduction.create(engine,original['id'],[],{'loss':{'atol':0,'rtol':0}})
        entry.write_text(entry.read_text()+'\n# TEST changed source')
        with pytest.raises(ValueError,match='source changed'):reproduction.launch(engine,manifest['id'],True)
        enqueue=engine.enqueue
        def fault(id):raise RuntimeError('TEST crash before enqueue')
        monkeypatch.setattr(engine,'enqueue',fault)
        with pytest.raises(RuntimeError):reproduction.launch(engine,manifest['id'],True,True)
        prepared=documents.get('reproduction',manifest['id']);assert prepared['status']=='Prepared'
        monkeypatch.setattr(engine,'enqueue',enqueue)
        replay=reproduction.launch(engine,manifest['id'],True,True);assert replay['execution']==prepared['execution']
        assert wait(engine,replay['execution'])['state']=='Succeeded'
        assert len(engine.listing())==2
    finally:engine.stop()

def test_bounded_data_studio_and_traversal(client,tmp_path):
    root=tmp_path/'TEST_DATA';root.mkdir()
    with h5py.File(root/'field.h5','w') as f:
        a=f.create_dataset('temperature',shape=(100000,1000),chunks=(100,100),dtype='f8',fillvalue=4);a[:2,:3]=np.arange(6).reshape(2,3)
    aid=assets.register('TEST large sparse HDF5','dataset',root)['id']
    assert data_studio.inspect(aid,'field.h5')['fields'][0]['shape']==[100000,1000]
    result=data_studio.array_slice(aid,'field.h5','temperature',[[0,2,1],[0,3,1]])
    assert result['mean']==2.5 and result['values']==[[0,1,2],[3,4,5]]
    with pytest.raises(ValueError,match='100000'):data_studio.array_slice(aid,'field.h5','temperature',[[0,1000,1],[0,1000,1]])
    assert client.get(f'/api/v3/assets/{aid}/inspect',params={'path':'../outside.h5'}).status_code==422
    np.savez(root/'object.npz',unsafe=np.array([{'TEST':1}],dtype=object))
    with pytest.raises(ValueError,match='object'):data_studio.array_slice(aid,'object.npz','unsafe',[[0,1,1]])
    (root/'table.csv').write_text('a,b\n1,2\n3,4\n5,6\n')
    assert data_studio.table(aid,'table.csv',1,1)['rows']==[{'a':3,'b':4}]
    from PIL import Image
    Image.new('RGB',(100,80),'white').save(root/'image.png')
    assert client.get(f'/api/v3/assets/{aid}/image',params={'path':'image.png'}).content.startswith(b'\xff\xd8')
    assert len(data_studio.files(aid))==4

def test_scenario_c_equation_driven_simulation(client,tmp_path):
    script="import os,pathlib; p=pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR']); (p/'metrics.csv').write_text('time,energy,power,h,error\\n0,10,2,1,1\\n1,12,2,0.5,0.25\\n2,14,2,0.25,0.0625\\n')"
    engine=Orchestrator(tmp_path/'executor');engine.start()
    try:
        cfg=spec(tmp_path,script);cfg['params']['metric_definitions'].update({k:{'unit':u,'method':'TEST','direction':'minimize'} for k,u in [('h','m'),('error','K'),('time','s'),('energy','J'),('power','W')]})
        run=engine.create(cfg);engine.enqueue(run['id']);done=wait(engine,run['id']);assert done['state']=='Succeeded'
        s=storage.get(done['snapshot_id']);r=s['runs'][0]
        args={'snapshot_id':done['snapshot_id'],'run_id':r['id'],'energy_metric':'energy','power_metric':'power','time_metric':'time','unit_energy':'J','unit_power':'W','unit_time':'s','atol':1e-10,'rtol':0.}
        result=client.post('/api/v3/suites/energy-balance',json=args);assert result.status_code==200,result.text
        assert result.json()['result']['status']=='PASS' and result.json()['result']['max_absolute_residual_J']==0
        trend=suites.simulation_trend(done['snapshot_id'],r['id'],'h','error','convergence');assert trend['result']['observed_order']==pytest.approx(2)
        sensitivity=suites.simulation_trend(done['snapshot_id'],r['id'],'time','energy','sensitivity');assert sensitivity['result']['secant_slopes']==[2,2]
        args['atol']=-1;assert client.post('/api/v3/suites/energy-balance',json=args).status_code==422
    finally:engine.stop()

def test_pose_sign_invariance_and_protocol(client,tmp_path):
    root=tmp_path/'TEST_POSE';root.mkdir()
    columns=['qx','qy','qz','qw','px','py','pz','pw','tx','ty','tz','ux','uy','uz']
    (root/'pose.csv').write_text(','.join(columns)+'\n0,0,0,1,0,0,0,-1,0,0,0,3,4,0\n0,0,0,1,0,0,0.7071067811865475,0.7071067811865476,0,0,0,0,0,0\n')
    s=client.post('/api/import',json={'path':str(root)}).json()
    args={'snapshot_id':s['id'],'run_id':s['runs'][0]['id'],'columns':{'truth_quaternion':columns[:4],'prediction_quaternion':columns[4:8],'truth_translation':columns[8:11],'prediction_translation':columns[11:]},'quaternion_order':'xyzw','convention':'active','frame':'TEST inertial','translation_unit':'m'}
    result=client.post('/api/v3/suites/pose',json=args);assert result.status_code==200,result.text
    assert result.json()['result']['rotation_error_degrees']==pytest.approx([0,90])
    assert result.json()['result']['translation_error']==[5,0]
    args['failure_rotation_degrees']=45;assert client.post('/api/v3/suites/pose',json=args).json()['result']['failure_indices']==[1]
    del args['frame'];assert client.post('/api/v3/suites/pose',json=args).status_code==422

def test_scenario_d_workflow_real_command_audit_figure_report(client,tmp_path):
    engine=Orchestrator(tmp_path/'executor');engine.start();wf=workflows.WorkflowEngine(engine)
    definition={'name':'TEST executable scientific workflow','nodes':[
        {'id':'train','kind':'command','config':spec(tmp_path)},
        {'id':'statistics','kind':'describe','depends_on':['train'],'config':{'snapshot_id':{'$ref':'train.snapshot_id'},'run_id':{'$ref':'train.runs.0.run_id'},'metric':'loss'}},
        {'id':'audit','kind':'audit','depends_on':['train'],'config':{'snapshot_id':{'$ref':'train.snapshot_id'}}},
        {'id':'figure','kind':'figure','depends_on':['train'],'config':{'snapshot_id':{'$ref':'train.snapshot_id'},'metric':'loss','format':'svg'}},
        {'id':'report','kind':'report','depends_on':['train','audit','figure','statistics'],'config':{'snapshot_id':{'$ref':'train.snapshot_id'}}}]}
    try:
        saved=workflows.save(definition)
        with pytest.raises(ValueError,match='confirmation'):wf.start(saved['id'],1,False)
        started=wf.start(saved['id'],1,True);done=wait(wf,started['id']);assert done['state']=='Succeeded',done
        assert Path(done['nodes']['figure']['output']['path']).read_bytes().lstrip().startswith(b'<?xml')
        assert Path(done['nodes']['report']['output']['path']).read_bytes().startswith(b'%PDF')
        assert done['nodes']['train']['attempts']==1
        changed=workflows.save({**definition,'name':'TEST revision 2'},saved['id'],1)
        assert changed['revision']==2 and wf.get(done['id'])['revision']==1
    finally:wf.stop();engine.stop()

def test_workflow_retries_conditions_cycle_recovery(client,tmp_path):
    with pytest.raises(ValueError,match='cycle'):workflows.save({'name':'TEST cycle','nodes':[{'id':'a','kind':'import','config':{},'depends_on':['b']},{'id':'b','kind':'import','config':{},'depends_on':['a']}]})
    engine=Orchestrator(tmp_path/'executor');engine.start();wf=workflows.WorkflowEngine(engine)
    fail=spec(tmp_path,'raise RuntimeError("TEST intentional failure")')
    try:
        saved=workflows.save({'name':'TEST failure','nodes':[{'id':'bad','kind':'command','config':fail,'retries':1},{'id':'dependent','kind':'import','config':{},'depends_on':['bad']}]})
        done=wait(wf,wf.start(saved['id'],1,True)['id']);assert done['state']=='Failed'
        assert done['nodes']['bad']['attempts']==2 and len(done['nodes']['bad']['execution_ids'])==2 and done['nodes']['dependent']['state']=='Blocked'
        with storage.connect() as c:c.execute("UPDATE workflow_runs SET state='Running' WHERE id=?",(done['id'],))
        wf.recover();assert wf.get(done['id'])['state']=='Interrupted'
    finally:wf.stop();engine.stop()

def test_knowledge_query_diagnostics_revision_contracts(client,tmp_path):
    root=tmp_path/'TEST_logs';root.mkdir();(root/'m.csv').write_text('loss\n'+''.join(str(v)+'\n' for v in range(1,16)))
    (root/'config.json').write_text(json.dumps({'metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST mean'}}}))
    s=client.post('/api/import',json={'path':str(root)}).json();sid=s['id']
    result=client.post('/api/v3/intelligence/diagnose',json={'snapshot_id':sid}).json()
    assert any(r['rule']=='loss_divergence' and r['status']=='WARN' for r in result['result'])
    assert client.post('/api/v3/intelligence/query',json={'snapshot_id':sid,'text':'哪些实验没有记录随机种子'}).json()['rows'][0]['missing']
    assert client.post('/api/v3/intelligence/query',json={'snapshot_id':sid,'text':'最低 loss'}).status_code==422
    payload={'kind':'claim','title':'TEST hypothesis','body':'TEST result','supporting':[{'kind':'snapshot','id':str(sid)}]}
    one=client.post('/api/v3/knowledge',json=payload).json();assert one['validation_status']=='unverified'
    two=client.put('/api/v3/knowledge/'+one['id']+'?revision=1',json={**payload,'body':'TEST revised'});assert two.status_code==200,two.text
    assert client.put('/api/v3/knowledge/'+one['id']+'?revision=1',json=payload).status_code==422
    assert len(client.get('/api/v3/knowledge/'+one['id']+'/history').json())==2
    assert client.get('/api/v3/knowledge?q=revised').json()[0]['id']==one['id']
    assert client.post('/api/v3/knowledge',json={**payload,'supporting':[{'kind':'snapshot','id':'9999'}]}).status_code==404
    graph=client.get(f'/api/v3/snapshots/{sid}/graph');assert graph.status_code==200,graph.text
    assert any(e['to']==one['id'] for e in graph.json()['edges'])

def test_scenario_b_real_multimodel_formats_and_reports(client,tmp_path):
    root=tmp_path/'TEST_multimodel';root.mkdir()
    for model,values in [('a',[1.,2.,3.]),('b',[3.,5.,6.])]:
        for seed,value in enumerate(values):
            directory=root/(model+str(seed));directory.mkdir()
            (directory/'metrics.csv').write_text('loss\n'+str(value+1)+'\n'+str(value)+'\n')
            config=spec(tmp_path)['params'];config.update(model_version=model,seed=seed)
            (directory/'config.json').write_text(json.dumps(config))
    s=client.post('/api/import',json={'path':str(root)}).json();sid=s['id'];assert len(s['runs'])==6
    refs=[{'snapshot_id':sid,'run_id':r['id'],'metric':'loss'} for r in s['runs']]
    test=client.post('/api/v2/analyses/independent',json={'left':refs[:3],'right':refs[3:],'independent_runs':True});assert test.status_code==200,test.text
    assert test.json()['result']['mean_difference']==pytest.approx(-8/3)
    batch=client.post('/api/v2/analyses/batch',json={'refs':[{k:v for k,v in r.items() if k!='metric'} for r in refs],'group_by':['model_version']}).json()
    assert len(batch['result']['loss']['groups'])==2
    assert client.get(f'/api/projects/{sid}/figure?metric=loss&format=svg').content.lstrip().startswith(b'<?xml')
    assert client.get(f'/api/v2/snapshots/{sid}/report.pdf').content.startswith(b'%PDF')
    query=client.post('/api/v3/intelligence/query',json={'snapshot_id':sid,'text':'最低 loss'}).json();assert query['rows'][0]['value']==1
    summary=client.post('/api/v3/intelligence/summary',json={'snapshot_id':sid,'run_ids':[r['id'] for r in s['runs']]}).json()
    assert summary['result']['configuration_differences']['model_version'] and summary['result']['metrics']['loss']['compatibility']['status']=='PASS'
    distribution=client.post('/api/v3/reproductions/distribution',json={'left':refs[:3],'right':refs[3:],'independent_runs':True}).json()
    assert distribution['status']=='UNKNOWN' and 'equivalence' in distribution['warning']

def test_real_cpp_execution(client,tmp_path):
    import shutil,subprocess,os
    compiler=shutil.which('g++')
    if not compiler:pytest.skip('g++ unavailable; C++ runtime not verified in this environment')
    source=Path(__file__).parents[1]/'examples'/'TEST_DATA_simulation.cpp';binary=tmp_path/('TEST_sim.exe' if os.name=='nt' else 'TEST_sim')
    flags=['-static','-static-libgcc','-static-libstdc++'] if os.name=='nt' else []
    built=subprocess.run([compiler,'-std=c++11',*flags,str(source),'-o',str(binary)],capture_output=True,text=True,timeout=40)
    assert built.returncode==0,built.stderr
    engine=Orchestrator(tmp_path/'executor');engine.start()
    try:
        cfg=spec(tmp_path);cfg['argv']=[str(binary)]
        run=engine.create(cfg);engine.enqueue(run['id']);done=wait(engine,run['id']);assert done['state']=='Succeeded',done
        s=storage.get(done['snapshot_id']);r=s['runs'][0]
        report=suites.balance(done['snapshot_id'],r['id'],'energy','power','time','J','W','s',1e-10,0)
        assert report['result']['status']=='PASS'
    finally:engine.stop()

def test_notebook_no_execution_external_hdf5_and_api_workflow(client,tmp_path):
    nb=tmp_path/'TEST.ipynb';nb.write_text(json.dumps({'nbformat':4,'cells':[{'cell_type':'code','execution_count':1,'source':['raise RuntimeError("NEVER EXECUTE")'],'outputs':[{'output_type':'execute_result','data':{'application/json':{'value':3},'text/html':'<script>throw 1</script>'}}]}]}))
    aid=assets.register('TEST notebook','dataset',nb)['id']
    result=client.post(f'/api/v3/assets/{aid}/notebook',params={'path':''});assert result.status_code==200,result.text
    assert 'text/html' not in result.json()['result'][0]['outputs'][0]['data'] and result.json()['status']=='UNKNOWN'
    with h5py.File(tmp_path/'outside.h5','w') as f:f['secret']=[1,2]
    with h5py.File(tmp_path/'links.h5','w') as f:f['linked']=h5py.ExternalLink('outside.h5','secret')
    aid=assets.register('TEST hdf5 link','dataset',tmp_path/'links.h5')['id']
    with pytest.raises(ValueError,match='hard links'):data_studio.array_slice(aid,'','linked',[[0,1,1]])
    body={'name':'TEST API workflow','nodes':[{'id':'import','kind':'import','config':{'path':str(tmp_path)}}]}
    response=client.post('/api/v3/workflows',json=body);assert response.status_code==200,response.text
    id=response.json()['id'];assert client.post('/api/v3/workflows/'+id+'/start',json={}).status_code==422

def test_workflow_branch_and_owned_parallel_cancellation(client,tmp_path):
    root=tmp_path/'TEST';root.mkdir();(root/'m.csv').write_text('loss\n1\n')
    engine=Orchestrator(tmp_path/'executor');engine.start();wf=workflows.WorkflowEngine(engine)
    try:
        definition=workflows.save({'name':'TEST false condition','nodes':[{'id':'import','kind':'import','config':{'path':str(root)}},{'id':'report','kind':'report','depends_on':['import'],'condition':{'node':'import','path':'snapshot_id','op':'eq','value':-1},'config':{'snapshot_id':{'$ref':'import.snapshot_id'}}}]})
        done=wait(wf,wf.start(definition['id'],1,True)['id']);assert done['state']=='Succeeded' and done['nodes']['report']['state']=='Skipped'
        slow=spec(tmp_path,'import time; time.sleep(20)');definition=workflows.save({'name':'TEST concurrent cancellation','nodes':[{'id':id,'kind':'command','config':slow} for id in ('a','b')]})
        unrelated=engine.create(slow)
        run=wf.start(definition['id'],1,True);deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            record=wf.get(run['id'])
            if all(n['state']=='Running' for n in record['nodes'].values()):break
            time.sleep(.05)
        assert all(n['state']=='Running' for n in record['nodes'].values())
        assert len({n['execution_ids'][0] for n in record['nodes'].values()})==2
        wf.cancel(run['id']);assert wf.get(run['id'])['state']=='Cancelled'
        assert all(engine.get(n['execution_ids'][0])['state']=='Cancelled' for n in record['nodes'].values())
        assert engine.get(unrelated['id'])['state']=='Pending'
    finally:wf.stop();engine.stop()

def test_additive_migration_and_bad_reference_terminates(client,tmp_path):
    import sqlite3
    storage.DB.mkdir();db=storage.DB/'audit.sqlite'
    legacy={'root':'TEST legacy','runs':[{'name':'.','params':{},'metrics':{},'series':{},'sources':[]}],'evidence':[],'issues':[],'git':{}}
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE snapshots(id INTEGER PRIMARY KEY,created TEXT,root TEXT,payload TEXT)');c.execute('INSERT INTO snapshots VALUES (1,?,?,?)',('TEST date','TEST legacy',json.dumps(legacy)))
    document=documents.save('knowledge',{'kind':'note','title':'TEST migrated'});assert document['revision']==1
    with storage.connect() as c:
        assert json.loads(c.execute('SELECT payload FROM snapshots WHERE id=1').fetchone()[0])==legacy
        assert c.execute('SELECT 1 FROM schema_migrations WHERE version=3').fetchone()
    root=tmp_path/'TEST';root.mkdir();(root/'m.csv').write_text('loss\n1\n')
    engine=Orchestrator(tmp_path/'executor');wf=workflows.WorkflowEngine(engine)
    try:
        d=workflows.save({'name':'TEST bad reference','nodes':[{'id':'source','kind':'import','config':{'path':str(root)}},{'id':'broken','kind':'report','depends_on':['source'],'config':{'snapshot_id':{'$ref':'source.nonexistent'}}}]})
        done=wait(wf,wf.start(d['id'],1,True)['id'],timeout=5)
        assert done['state']=='Failed' and done['nodes']['broken']['attempts']==1
    finally:wf.stop();engine.stop()
