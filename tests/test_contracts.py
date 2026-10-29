"""Controlled TEST DATA only; values are not research results."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage
from backend.collect import scan
from backend.analysis import compare, audit

@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'registry')
    root=tmp_path/'TEST_DATA';root.mkdir()
    for name,seed,values in [('a',1,[3,1,2]),('b',2,[4,2,3])]:
        d=root/name;d.mkdir()
        (d/'config.yaml').write_text('seed: '+str(seed)+'\ndataset: TEST_DATA\ndataset_version: sha256:test-fixture\nsplit: validation\nevaluation_protocol: test-v1\nmodel_version: test-model\nmetric_definitions:\n  loss:\n    direction: minimize\n    unit: "1"\n    method: mean squared error\n')
        (d/'metrics.csv').write_text('loss\n'+'\n'.join(map(str,values))+'\n')
    return root

def test_idempotence_and_changed_evidence(project):
    c=TestClient(app)
    a=c.post('/api/import',json={'path':str(project)}).json()
    b=c.post('/api/import',json={'path':str(project)}).json()
    assert a['id']==b['id']
    (project/'a'/'metrics.csv').write_text('loss\n8\n')
    d=c.post('/api/import',json={'path':str(project)}).json()
    assert d['id']!=a['id']
    assert c.get('/api/projects/'+str(a['id'])).json()['runs'][0]['series']['loss']==[3,1,2]

def test_statistics_and_filter(project):
    s=scan(project); result=compare(s,'loss')
    assert result['compatibility']['status']=='PASS'
    assert [v['best'] for v in result['values']]==[1,2]
    assert [v['value'] for v in result['values']]==[2,3]
    assert result['seed_groups'][0]['mean']==2.5
    assert result['seed_groups'][0]['std']==pytest.approx(2**-0.5)
    assert compare(s,'loss',{'seed':1})['n']==1
    assert all(v['sources'][0]['column']=='loss' for v in result['values'])

def test_conflict_unknown_and_duplicate_seed(project):
    s=scan(project)
    s['runs'][1]['params']['dataset_version']='other'
    assert compare(s,'loss')['compatibility']['status']=='FAIL'
    s=scan(project);s['runs'][0]['metric_definitions']['loss']['method']='different'
    assert compare(s,'loss')['compatibility']['status']=='FAIL'
    s=scan(project);del s['runs'][0]['params']['split']
    assert compare(s,'loss')['compatibility']['status']=='UNKNOWN'
    s=scan(project);s['runs'][1]['params']['seed']=1
    assert compare(s,'loss')['seed_groups'][0]['mean'] is None

def test_nonfinite_final_and_report(project):
    (project/'a'/'metrics.csv').write_text('loss\n3\nNaN\n')
    s=scan(project)
    v=compare(s,'loss')['values'][0]
    assert v['value'] is None and v['last_finite']==3 and v['best']==3
    assert any(f['rule']=='finite_values' and f['status']=='FAIL' for f in audit(s))
    c=TestClient(app);a=c.post('/api/import',json={'path':str(project)}).json()
    report=c.get('/api/projects/'+str(a['id'])+'/report').text
    embedded=json.loads(report.split('```json\n')[1].split('\n```')[0])
    assert embedded['snapshot']['evidence']==a['evidence']
    assert embedded['comparisons']['loss']['values'][0]['value'] is None

def test_duplicate_metric_is_visible(project):
    (project/'a'/'z.csv').write_text('loss\n999\n')
    s=scan(project)
    assert s['runs'][0]['series']['loss']==[3,1,2]
    assert any('Duplicate metric' in f['message'] for f in s['issues'])
