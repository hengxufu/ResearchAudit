"""TEST DATA for figure exports and columnar query."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import storage

@pytest.mark.parametrize('format,signature',[('pdf',b'%PDF'),('png',b'\x89PNG'),('svg',b'<?xml')])
def test_exports(tmp_path,monkeypatch,format,signature):
    monkeypatch.setattr(storage,'DB',tmp_path/'store')
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'metrics.csv').write_text('loss\n3\n1\n2\n')
    c=TestClient(app);s=c.post('/api/import',json={'path':str(root)}).json();id=s['id']
    for kind in ('curve','distribution'):
        r=c.get(f'/api/projects/{id}/figure',params={'metric':'loss','format':format,'kind':kind})
        assert r.status_code==200 and r.content.startswith(signature)
        assert r.headers['x-evidence-id']
    assert len(c.get(f'/api/projects/{id}/figures').json())==2
    rows=c.get(f'/api/projects/{id}/observations',params={'metric':'loss','limit':2,'offset':1}).json()
    assert [r['value'] for r in rows]==[1,2]
    assert c.get(f'/api/projects/{id}/observations?metric=loss&limit=-1').status_code==400
    graph=c.get(f'/api/projects/{id}/graph').json()
    assert any(e['type']=='derived_from' for e in graph['edges'])
    assert (storage.DB/'metrics'/f'{id}.parquet').exists()
