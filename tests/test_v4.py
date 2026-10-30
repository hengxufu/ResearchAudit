"""TEST DATA: real local formats and commands; no external project code execution."""
import hashlib,json,sys,time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import storage
from backend.main import app
from backend.orchestrator import Orchestrator
from backend.v4 import projects,optimization,statistics,environments

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'state');return TestClient(app)

def dataset(root,models=('a',)):
    root.mkdir()
    for model in models:
        for seed,x in enumerate((0.,.5,1.)):
            p=root/(model+str(seed));p.mkdir();value=(x-.3)**2+(1 if model=='b' else 0)
            params={'x':x,'seed':seed,'model':model,'dataset':'TEST','dataset_version':'v1','split':'test','evaluation_protocol':'mse-v1','metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST squared error'}}}
            (p/'config.json').write_text(json.dumps(params));(p/'metrics.csv').write_text(f'loss\n{value+1}\n{value}\n')
    return root

def imported(client,root):
    response=client.post('/api/import',json={'path':str(root)});assert response.status_code==200,response.text
    s=response.json();return s,[{'snapshot_id':s['id'],'run_id':r['id']} for r in s['runs']]

def test_a_project_takeover_readonly_corrections_and_idempotent_backfill(client,tmp_path):
    root=dataset(tmp_path/'TEST_PROJECT');(root/'train.py').write_text('import torch\nraise RuntimeError("DO NOT RUN")\n');(root/'CMakeLists.txt').write_text('project(TEST)');(root/'weights.pt').write_bytes(b'TEST NOT A REAL MODEL')
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    response=client.post('/api/v4/projects/inspect',json={'path':str(root)});assert response.status_code==200,response.text
    d=response.json();assert {'Python','PyTorch','CMake'}<=set(d['structures']);assert all(c['status']=='PENDING_CONFIRMATION' for c in d['candidates'])
    assert next(f for f in d['files'] if f['path']=='weights.pt').get('sha256') is None
    correction=client.post(f"/api/v4/projects/{d['id']}/associations",json={'directory':'a0','experiment_label':'TEST reviewed','reason':'TEST explicit user curation','revision':1});assert correction.status_code==200
    ids=[]
    for _ in range(2):
        r=client.post(f"/api/v4/projects/{d['id']}/backfill",json={'directories':['a0','a1','a2']});assert r.status_code==200,r.text;ids.append([s['snapshot_id'] for s in r.json()['results']])
    assert ids[0]==ids[1]
    assert client.post(f"/api/v4/projects/{d['id']}/watch").status_code==200
    assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    limited=projects.inspect(root,max_files=1);assert limited['truncated']

def test_b_stratified_repeated_bootstrap_and_multipanel(client,tmp_path):
    s,refs=imported(client,dataset(tmp_path/'TEST_MULTI',('a','b')))
    body={'refs':refs,'metric':'loss','group_by':['model'],'independent':True,'resamples':200,'seed':7}
    grouped=client.post('/api/v4/statistics/bootstrap',json=body);assert grouped.status_code==200,grouped.text
    assert [g['n'] for g in grouped.json()['result']]==[3,3]
    paired=client.post('/api/v4/statistics/bootstrap',json={**body,'paired':True});assert paired.status_code==200,paired.text
    assert paired.json()['result']['mean_difference_second_minus_first']==pytest.approx(1)
    assert paired.json()['result']['ci95']==pytest.approx([1,1])
    assert client.post('/api/v4/statistics/bootstrap',json={**body,'independent':False}).status_code==422
    metricrefs=[{**r,'metric':'loss'} for r in refs[:2]]
    recipe=client.post('/api/v4/figures',json={'title':'TEST figure','panels':[{'label':'Raw','refs':metricrefs},{'label':'Display transform','refs':metricrefs,'smooth':2}]}).json()
    for fmt,signature in [('svg',b'<?xml'),('pdf',b'%PDF'),('png',b'\x89PNG')]:
        r=client.get(f"/api/v4/figures/{recipe['id']}/{fmt}");assert r.status_code==200,r.text[:200];assert r.content.startswith(signature) and r.headers['x-content-sha256']==hashlib.sha256(r.content).hexdigest()
    summary=client.post('/api/v4/copilot',json={'snapshot_id':s['id'],'operation':'summary'});assert summary.status_code==200,summary.text
    assert summary.json()['network']=='disabled' and 'configuration_differences' in summary.json()['result']['result']

def test_c_optimization_suggestion_authorized_execute_and_update(client,tmp_path):
    s,refs=imported(client,dataset(tmp_path/'TEST_SEARCH'))
    body={'refs':refs,'metric':'loss','space':{'x':[0,1]},'algorithm':'bayesian','count':2,'budget':2,'seed':4,'constraints':[{'coefficients':{'x':1},'upper':.8}]}
    response=client.post('/api/v4/optimizations',json=body);assert response.status_code==200,response.text
    proposal=response.json();assert all(c['parameters']['x']<=.8 and c['posterior_sd']>=0 for c in proposal['candidates'])
    assert client.get('/api/executions').json()==[]
    script=tmp_path/'TEST_objective.py';script.write_text("import sys,os,pathlib; x=float(sys.argv[1]); (pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR'])/'metrics.csv').write_text('loss\\n'+str((x-.3)**2)+'\\n')")
    spec={'argv':[sys.executable,str(script),'{x}'],'cwd':str(tmp_path)}
    assert client.post(f"/api/v4/optimizations/{proposal['id']}/dispatch",json={'candidate':0,'spec':spec}).status_code==422
    from backend.main import execution_engine
    engine=execution_engine();engine.start()
    try:
        req={'candidate':0,'spec':spec,'confirmed':True};run=client.post(f"/api/v4/optimizations/{proposal['id']}/dispatch",json=req);assert run.status_code==200,run.text
        id=run.json()['execution']['id'];deadline=time.monotonic()+20
        while time.monotonic()<deadline and engine.get(id)['state'] not in ('Succeeded','Failed'):time.sleep(.05)
        assert engine.get(id)['state']=='Succeeded',engine.get(id)
        duplicate=client.post(f"/api/v4/optimizations/{proposal['id']}/dispatch",json=req).json();assert duplicate['duplicate_request'] and duplicate['execution']['id']==id
        result=client.get(f"/api/v4/optimizations/{proposal['id']}/results").json();actual=result['results'][0]['observations'][0]['value'];assert actual==pytest.approx((proposal['candidates'][0]['parameters']['x']-.3)**2)
        assert result['remaining_budget']==1
        observation=result['results'][0]['observations'][0]
        next_refs=refs+[{'snapshot_id':observation['snapshot_id'],'run_id':observation['run_id']}]
        next_round=client.post('/api/v4/optimizations',json={**body,'refs':next_refs});assert next_round.status_code==200,next_round.text
        assert len(next_round.json()['observations'])==4
        manifest=client.post('/api/v3/reproductions',json={'source_execution':id,'tolerances':{'loss':{'atol':1e-12,'rtol':1e-12}}}).json()
        difference=client.post(f"/api/v4/reproductions/{manifest['id']}/environment-diff").json();assert difference['recorded_package_count']>0 and difference['runner_package_match']=='PASS' and difference['target_environment_consistency']=='UNKNOWN'
        replay=client.post(f"/api/v3/reproductions/{manifest['id']}/start",json={'confirmed':True}).json();deadline=time.monotonic()+20
        while time.monotonic()<deadline and engine.get(replay['execution'])['state'] not in ('Succeeded','Failed'):time.sleep(.05)
        verified=client.post(f"/api/v3/reproductions/{manifest['id']}/evaluate").json();assert verified['scorecard']['result_consistency']['status']=='PASS'
    finally:engine.stop()

def test_d_environment_comparison_and_existing_reproduction(client,tmp_path):
    pip=tmp_path/'TEST_requirements.txt';pip.write_text('numpy==2.0.2\nunknown_test_package==0.0\nscipy>=1\n-r ignored.txt\n')
    d=client.post('/api/v4/environments/import',json={'path':str(pip),'kind':'pip'}).json();assert len(d['unresolved'])==2
    result=client.post(f"/api/v4/environments/{d['id']}/compare").json();assert result['declaration_match']=='FAIL' and result['scientific_reproduction']=='UNKNOWN'
    conda=tmp_path/'TEST_environment.yaml';conda.write_text('name: TEST\ndependencies:\n  - python=3.9\n  - numpy=2.0.2\n  - pip:\n    - scipy==1.13.1\n')
    parsed=environments.declaration(conda,'conda');assert parsed['packages']['numpy']=='2.0.2' and parsed['unresolved']==['python=3.9']
    assert client.get('/api/v4/environments/runner').json()['packages']

def test_optimizer_incomplete_confounded_and_determinism(client,tmp_path):
    s,refs=imported(client,dataset(tmp_path/'TEST',('a','b')))
    base={'refs':refs,'metric':'loss','space':{'x':[0,1]},'algorithm':'bayesian','count':2,'budget':2}
    assert client.post('/api/v4/optimizations',json=base).status_code==422
    base['refs']=refs[:3]
    one=client.post('/api/v4/optimizations',json=base).json();two=client.post('/api/v4/optimizations',json=base).json();assert one['candidates']==two['candidates']
    assert client.post('/api/v4/optimizations',json={**base,'space':{'x':[1,1]}}).status_code==422
    assert client.post(f"/api/v4/optimizations/{one['id']}/dispatch",json={'candidate':0,'spec':{'argv':[],'cwd':str(tmp_path)},'confirmed':True}).status_code==422
    assert client.post('/api/v4/copilot',json={'snapshot_id':s['id'],'operation':'shell','text':'run command'}).status_code==422

def test_e_real_thermal_execution_equation_and_report(client,tmp_path):
    from backend.main import execution_engine
    script=tmp_path/'TEST_radiation.py';script.write_text("import os,pathlib; f=(pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR'])/'metrics.csv').open('w'); f.write('temperature,ambient,power\\n'); [(f.write(str(t)+',250,'+str(.8*5.670374419e-8*2*(t**4-250**4))+'\\n')) for t in (280,300,320)]; f.close()")
    engine=execution_engine();engine.start()
    try:
        run=engine.create({'argv':[sys.executable,str(script)],'cwd':str(tmp_path),'params':{'metric_definitions':{k:{'unit':u,'direction':'minimize','method':'TEST gray surface'} for k,u in [('temperature','K'),('ambient','K'),('power','W')]}}});engine.enqueue(run['id']);deadline=time.monotonic()+20
        while time.monotonic()<deadline and engine.get(run['id'])['state'] not in ('Succeeded','Failed'):time.sleep(.05)
        done=engine.get(run['id']);assert done['state']=='Succeeded',done
        s=storage.get(done['snapshot_id']);r=s['runs'][0];assert r['execution']['environment_manifest']['runner']['distributions']['numpy']
        body={'snapshot_id':done['snapshot_id'],'run_id':r['id'],'temperature':'temperature','ambient':'ambient','power':'power','area_m2':2,'emissivity':.8,'atol':1e-10,'rtol':1e-12}
        response=client.post('/api/v4/science/radiation',json=body);assert response.status_code==200,response.text
        assert response.json()['result']['status']=='PASS' and response.json()['scientific_model_validity']=='UNKNOWN'
        wrong=client.post('/api/v4/science/radiation',json={**body,'emissivity':.5}).json();assert wrong['result']['status']=='FAIL'
        assert client.get(f"/api/v2/snapshots/{done['snapshot_id']}/report.pdf").content.startswith(b'%PDF')
    finally:engine.stop()

def test_optimization_fault_reservation_and_workflow_revision_diff(client,tmp_path,monkeypatch):
    from backend.v3 import workflows
    s,refs=imported(client,dataset(tmp_path/'TEST_FAULT'))
    proposal=optimization.propose(refs,'loss',{'x':[0,1]},'random',1,1,0,[])
    engine=Orchestrator(tmp_path/'executor')
    def fail(spec):raise RuntimeError('TEST pre-create crash')
    monkeypatch.setattr(engine,'create',fail)
    with pytest.raises(RuntimeError):optimization.dispatch(engine,proposal['id'],0,{'argv':[sys.executable,'-c','pass'],'cwd':str(tmp_path)},True)
    with pytest.raises(ValueError,match='Interrupted reservation'):optimization.dispatch(engine,proposal['id'],0,{'argv':[sys.executable,'-c','pass'],'cwd':str(tmp_path)},True)
    assert optimization.results(engine,proposal['id'])['remaining_budget']==0
    definition={'name':'TEST diff','nodes':[{'id':'import','kind':'import','config':{'path':str(tmp_path)}}]};one=workflows.save(definition);two=workflows.save({**definition,'nodes':[{'id':'import','kind':'import','config':{'path':str(tmp_path/'TEST_FAULT')}}]},one['id'],1)
    diff=client.get(f"/api/v4/workflows/{one['id']}/diff?left=1&right=2").json();assert diff['changed']==['import'] and not diff['cache_reuse']

def test_cross_interpreter_isolated_replay(client,tmp_path):
    import venv,os
    from backend.v3 import reproduction
    target=tmp_path/'TEST_ISOLATED_ENV';venv.EnvBuilder(with_pip=False).create(target)
    executable=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    script=tmp_path/'TEST_numeric.py';script.write_text("import math,os,pathlib,json,sys; p=pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR']); (p/'metrics.csv').write_text('loss\\n'+str(sum(math.sin(i)**2 for i in range(10)))+'\\n'); (p/'target_config.json').write_text(json.dumps({'researchaudit_execution':{'target_prefix':sys.prefix}}))")
    params={'seed':0,'dataset':'TEST','dataset_version':'1','split':'test','evaluation_protocol':'TEST','metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST sum of sine squares'}}}
    engine=Orchestrator(tmp_path/'execution');engine.start()
    def wait(id):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            r=engine.get(id)
            if r['state'] in ('Succeeded','Failed'):return r
            time.sleep(.05)
        raise AssertionError(engine.get(id))
    try:
        original=engine.create({'argv':[sys.executable,str(script)],'cwd':str(tmp_path),'params':params});engine.enqueue(original['id']);assert wait(original['id'])['state']=='Succeeded'
        manifest=reproduction.create(engine,original['id'],[],{'loss':{'atol':1e-12,'rtol':1e-12}})
        alternate=client.post(f"/api/v4/reproductions/{manifest['id']}/target",json={'executable':str(executable)}).json()
        with pytest.raises(ValueError,match='executable changed'):reproduction.launch(engine,alternate['id'],True)
        replay=reproduction.launch(engine,alternate['id'],True,True);done=wait(replay['execution']);assert done['state']=='Succeeded',done
        target_run=storage.get(done['snapshot_id'])['runs'][0];assert Path(target_run['execution']['target_prefix'])==target
        report=reproduction.evaluate(engine,alternate['id']);assert report['scorecard']['result_consistency']['status']=='PASS' and report['scorecard']['environment_completeness']['status']=='UNKNOWN'
    finally:engine.stop()
