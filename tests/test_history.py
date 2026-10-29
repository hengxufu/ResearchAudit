"""TEST DATA: historical curation must never rewrite observed facts."""
import json
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage

def test_history_workflow(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'metrics.csv').write_text('loss\n3\n1\n')
    (root/'config.json').write_text(json.dumps({'seed':7,'temperature':300}))
    c=TestClient(app);snap=c.post('/api/import',json={'path':str(root)}).json();sid=snap['id'];rid=snap['runs'][0]['id']
    url=f'/api/projects/{sid}/runs/{rid}'
    assert c.get('/api/history').json()['total']==1
    payload={'expected_revision':0,'title':'TEST historical simulation','tags':['thermal'],'status':'reviewed','conditions':[{'name':'temperature','value':300,'unit':'K','source':'TEST log page 1'}],'variables':[{'name':'mesh_size','value':0.1,'unit':'m','role':'independent','source':'TEST configuration'}],'notes':'Retrospective declaration'}
    saved=c.put(url+'/annotation',json=payload)
    assert saved.status_code==200 and saved.json()['revision']==1
    assert c.put(url+'/annotation',json=payload).status_code==409
    payload['expected_revision']=1;payload['notes']='Corrected annotation'
    assert c.put(url+'/annotation',json=payload).json()['revision']==2
    revisions=c.get(url+'/revisions').json()
    assert [v['revision'] for v in revisions]==[2,1]
    assert revisions[1]['notes']=='Retrospective declaration'
    for query in ('q=mesh_size','tag=thermal','status=reviewed'):
        assert c.get('/api/history?'+query).json()['total']==1
    assert c.get('/api/history?tag=missing').json()['total']==0
    assert c.get(f'/api/projects/{sid}').json()['runs']==snap['runs']
    assert 'Corrected annotation' in c.get(f'/api/projects/{sid}/report').text
    (root/'metrics.csv').write_text('loss\n2\n')
    newer=c.post('/api/import',json={'path':str(root)}).json()
    timeline=c.get('/api/history/'+rid).json()
    assert len(timeline)==2 and timeline[0]['snapshot_id']==newer['id']
    assert timeline[0]['annotation']['revision']==0
    payload['variables'][0]['role']='invalid'
    assert c.put(url+'/annotation',json=payload).status_code==422
    assert c.get(f'/api/projects/{sid}/runs/missing/revisions').status_code==404
    assert c.get('/api/history?limit=-1').status_code==400

def test_invalid_duplicate_conditions(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'m.csv').write_text('x\n1\n')
    c=TestClient(app);s=c.post('/api/import',json={'path':str(root)}).json()
    field={'name':'pressure','value':1,'unit':'Pa','source':'TEST'}
    payload={'expected_revision':0,'conditions':[field,field]}
    assert c.put(f"/api/projects/{s['id']}/runs/{s['runs'][0]['id']}/annotation",json=payload).status_code==422
