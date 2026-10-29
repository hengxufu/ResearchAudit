"""Controlled TEST DATA for scientific extensions."""
import pytest
from backend import science,storage
from fastapi.testclient import TestClient
from backend.main import app

def test_scientific_numerics():
    assert science.energy([10,10.001],.01,0)['status']=='PASS'
    assert science.energy([0,1],0,.1)['status']=='FAIL'
    assert science.convergence([1,.5,.25],[1,.25,.0625])['observed_order']==pytest.approx(2)
    assert science.sensitivity([1,2,3],[2,4,6])['secant_slopes']==[2,2]
    assert science.propagation([1,2],[[1,.5],[.5,4]],['m','m'])['standard_uncertainty']==pytest.approx(19**.5)
    with pytest.raises(ValueError):science.propagation([1,1],[[1,2],[2,1]],['m','m'])
    with pytest.raises(ValueError):science.convergence([1,1,.5],[1,.2,.1])
    with pytest.raises(ValueError):science.energy([1,float('nan')],0,0)

def test_sample_evidence_and_api(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    root=tmp_path/'TEST_DATA';root.mkdir()
    (root/'samples.csv').write_text('sample_id,target,prediction\na,cat,cat\nb,cat,dog\nb,dog,dog\n')
    (root/'metrics.csv').write_text('energy\n10\n10.001\n')
    c=TestClient(app);s=c.post('/api/import',json={'path':str(root)}).json();id=s['id'];rid=s['runs'][0]['id']
    result=c.get(f'/api/projects/{id}/samples?path=samples.csv').json()
    assert result['summary']['failures']==1 and result['summary']['unique_ids']==2
    assert c.post(f'/api/projects/{id}/science/energy',json={'run_id':rid,'metric':'energy','atol':.01}).json()['result']['status']=='PASS'
    a=c.post('/api/evidence',json={'kind':'table','label':'TEST result','sources':[{'snapshot_id':id,'run_id':rid,'metric':'energy'}]}).json()
    b=c.post('/api/evidence',json={'kind':'claim','label':'TEST claim','sources':[{'evidence_id':a['id']}]}).json()
    assert len(c.get('/api/evidence/'+b['id']+'/trace').json())==2
    assert c.post('/api/evidence',json={'kind':'claim','label':'bad','sources':[{'evidence_id':'missing'}]}).status_code==422
    (root/'samples.csv').write_text('sample_id,target,prediction\na,a,b\n')
    assert c.get(f'/api/projects/{id}/samples?path=samples.csv').status_code==422
