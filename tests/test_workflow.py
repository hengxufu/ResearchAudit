import json
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage

def test_workflow(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    project=tmp_path/'project'; project.mkdir()
    (project/'metrics.csv').write_text('loss,accuracy\n1,0.5\n0.2,0.9\n')
    (project/'config.json').write_text(json.dumps({'seed':42,'dataset':'real-test','split':'test'}))
    c=TestClient(app)
    r=c.post('/api/import',json={'path':str(project)})
    assert r.status_code==200
    s=r.json(); id=s['id']
    assert s['runs'][0]['metrics']['accuracy']==0.9
    assert len(s['evidence'][0]['sha256'])==64
    assert c.get(f'/api/projects/{id}/compare?metric=accuracy').json()['n']==1
    assert c.get(f'/api/projects/{id}/audit').status_code==200
    assert 'sha256' in c.get(f'/api/projects/{id}/report').text
    (project/'metrics.csv').write_text('loss\n9\n')
    assert c.get(f'/api/projects/{id}').json()['runs'][0]['metrics']['accuracy']==0.9
    assert c.post(f'/api/projects/{id}/validate/conservation?run=.&metric=loss').status_code==200
    assert c.get('/api/projects/99999').status_code==404
    assert c.post('/api/import',json={'path':str(tmp_path/'missing')}).status_code==400
