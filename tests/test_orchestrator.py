"""TEST DATA: actual subprocess -> metrics -> audit -> report -> source hash."""
import json,sys,time
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage,main

def wait(c,id):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        result=c.get('/api/executions/'+id).json()
        if result['state'] in ('Succeeded','Failed','Cancelled','Interrupted'):return result
        time.sleep(.05)
    raise AssertionError('Execution did not finish')

def test_real_execution_workflow(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    with TestClient(app) as c:
        script="import os,pathlib; p=pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR']); (p/'metrics.csv').write_text('loss\\n3\\n1\\n'); print('TEST DATA complete')"
        spec={'argv':[sys.executable,'-c',script],'cwd':str(tmp_path)}
        run=c.post('/api/executions',json=spec).json();id=run['id']
        assert run['state']=='Pending'
        assert c.get('/api/executions/'+id+'/logs').json()['text']==''
        assert c.post('/api/executions/'+id+'/pause').status_code==409
        assert c.post('/api/executions/'+id+'/start').json()['state']=='Queued'
        result=wait(c,id);assert result['state']=='Succeeded',result
        assert result['exit_code']==0
        assert 'TEST DATA complete' in c.get('/api/executions/'+id+'/logs').json()['text']
        snapshot=c.get('/api/projects/'+str(result['snapshot_id'])).json()
        assert snapshot['runs'][0]['metrics']['loss']==1
        assert c.get('/api/projects/'+str(result['snapshot_id'])+'/audit').status_code==200
        report=c.get('/api/projects/'+str(result['snapshot_id'])+'/report').text
        assert snapshot['evidence'][0]['sha256'] in report
        again=c.post('/api/executions/'+id+'/rerun').json();assert again['id']!=id and again['state']=='Pending'

def test_fail_dependency_cancel_and_recovery(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    with TestClient(app) as c:
        bad=c.post('/api/executions',json={'argv':[sys.executable,'-c','import sys; print("TEST failure",file=sys.stderr); sys.exit(7)'],'cwd':str(tmp_path)}).json()
        c.post('/api/executions/'+bad['id']+'/start');assert wait(c,bad['id'])['state']=='Failed'
        child=c.post('/api/executions',json={'argv':[sys.executable,'-c','pass'],'cwd':str(tmp_path),'dependencies':[bad['id']]}).json()
        c.post('/api/executions/'+child['id']+'/start');assert wait(c,child['id'])['state']=='Interrupted'
        slow=c.post('/api/executions',json={'argv':[sys.executable,'-c','import time;time.sleep(30)'],'cwd':str(tmp_path)}).json()
        c.post('/api/executions/'+slow['id']+'/start')
        c.post('/api/executions/'+slow['id']+'/cancel');assert c.get('/api/executions/'+slow['id']).json()['state']=='Cancelled'
        engine=main.execution_engine();engine.change(child['id'],state='Running');engine.recover()
        assert engine.get(child['id'])['state']=='Interrupted'

def test_legacy_schema_migration_preserves_snapshot(tmp_path,monkeypatch):
    import sqlite3,json
    monkeypatch.setattr(storage,'DB',tmp_path/'db');storage.DB.mkdir()
    legacy={'root':'TEST legacy','runs':[],'evidence':[],'issues':[],'git':{'commit':None,'status':None}}
    with sqlite3.connect(str(storage.DB/'audit.sqlite')) as c:
        c.execute('CREATE TABLE snapshots(id INTEGER PRIMARY KEY,created TEXT,root TEXT,payload TEXT)')
        c.execute('INSERT INTO snapshots VALUES (1,?,?,?)',('TEST timestamp','TEST legacy',json.dumps(legacy)))
    assert storage.get(1)==legacy
    engine=main.Orchestrator(storage.DB/'execution');engine.recover()
    assert storage.get(1)==legacy
    with storage.connect() as c:assert 'fingerprint' in [r[1] for r in c.execute('PRAGMA table_info(snapshots)')]

def test_grid_pending_and_real_concurrency(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    with TestClient(app) as c:
        result=c.post('/api/execution-grid',json={'spec':{'argv':[sys.executable,'-c','import time;time.sleep(.3)'],'cwd':str(tmp_path)},'grid':{'seed':[1,2,3]}})
        assert result.status_code==201
        runs=result.json()['runs'];assert len(runs)==3 and all(r['state']=='Pending' for r in runs)
        for r in runs:c.post('/api/executions/'+r['id']+'/start')
        for r in runs:assert wait(c,r['id'])['state']=='Succeeded'
        finished=[c.get('/api/executions/'+r['id']).json() for r in runs]
        for r in finished:
            active=sum(other['started']<=r['started']<other['finished'] for other in finished)
            assert active<=2
        assert c.post('/api/execution-grid',json={'spec':{'argv':['python'],'cwd':str(tmp_path)},'grid':{'seed':list(range(101))}}).status_code==422

def test_running_process_termination_and_soft_watchdog(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    with TestClient(app) as c:
        request={'argv':[sys.executable,'-c','import time;time.sleep(30)'],'cwd':str(tmp_path)}
        run=c.post('/api/executions',json=request).json();rid=run['id'];c.post('/api/executions/'+rid+'/start')
        engine=main.execution_engine();deadline=time.monotonic()+10
        while rid not in engine.processes and time.monotonic()<deadline:time.sleep(.05)
        assert rid in engine.processes
        process=engine.processes[rid]
        assert c.post('/api/executions/'+rid+'/cancel').json()['state']=='Cancelled'
        assert process.poll() is not None
        request['soft_memory_mb']=.001
        limited=c.post('/api/executions',json=request).json();c.post('/api/executions/'+limited['id']+'/start')
        result=wait(c,limited['id'])
        assert result['state']=='Failed' and 'Soft memory watchdog' in result['error']

def test_cpp_execution_if_compiler_available(tmp_path,monkeypatch):
    import shutil,subprocess,os
    import pytest
    compiler=shutil.which('g++') or shutil.which('clang++')
    if not compiler:pytest.skip('No g++/clang++ available; C++ execution not verified on this host')
    source=tmp_path/'TEST_program.cpp';binary=tmp_path/('TEST_program.exe' if os.name=='nt' else 'TEST_program')
    source.write_text('#include <fstream>\n#include <cstdlib>\n#include <string>\nint main(){const char* p=std::getenv("RESEARCHAUDIT_OUTPUT_DIR"); if(!p)return 2;std::ofstream f(std::string(p)+"/metrics.csv"); f<<"energy\\n1\\n1\\n";return 0;}')
    subprocess.run([compiler,str(source),'-o',str(binary)]+(['-static'] if os.name=='nt' else []),check=True,capture_output=True,timeout=30)
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    with TestClient(app) as c:
        run=c.post('/api/executions',json={'argv':[str(binary)],'cwd':str(tmp_path)}).json();c.post('/api/executions/'+run['id']+'/start')
        result=wait(c,run['id']);assert result['state']=='Succeeded',result
        snapshot=c.get('/api/projects/'+str(result['snapshot_id'])).json();assert snapshot['runs'][0]['metrics']['energy']==1

def test_execution_metadata_is_not_a_research_parameter(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    with TestClient(app) as c:
        script="import os,pathlib;pathlib.Path(os.environ['RESEARCHAUDIT_OUTPUT_DIR'],'metrics.csv').write_text('loss\\n1\\n');print('测试 UTF8')"
        run=c.post('/api/executions',json={'argv':[sys.executable,'-c',script],'cwd':str(tmp_path),'params':{'seed':1,'dataset':'TEST'}}).json();c.post('/api/executions/'+run['id']+'/start');result=wait(c,run['id'])
        assert result['state']=='Succeeded'
        snapshot=c.get('/api/projects/'+str(result['snapshot_id'])).json();r=snapshot['runs'][0]
        assert r['params']=={'seed':1,'dataset':'TEST'}
        assert r['execution']['execution_id']==run['id'] and r['execution']['exit_code']==0
        log=main.execution_engine().logs(run['id'],limit=1)
        assert log['text']=='测' and log['next_offset']==3
