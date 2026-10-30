"""Structural migration contracts: compatibility and generated-state isolation."""
import json
from backend import storage
from backend.collect import scan
from backend.core import documents
from backend.v3 import documents as legacy_documents
from backend.api.common import Strict,RunRef,MetricRef
from backend.v2 import assets
from backend.v4 import projects

def test_legacy_document_import_preserves_identity(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'state')
    assert legacy_documents.save is documents.save
    saved=legacy_documents.save('knowledge',{'title':'TEST compatibility'})
    assert documents.get('knowledge',saved['id'])==saved

def test_api_contracts_are_shared():
    from backend.v2 import router as v2
    from backend.v3 import router as v3
    from backend.v4 import router as v4
    for module in (v2,v3,v4):
        assert module.Strict is Strict and module.RunRef is RunRef and module.MetricRef is MetricRef

def test_generated_artifacts_do_not_become_research_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'state')
    root=tmp_path/'TEST_PROJECT';root.mkdir();(root/'metrics.csv').write_text('loss\n1\n')
    archive=root/'.artifacts'/'archive';archive.mkdir(parents=True);(archive/'metrics.csv').write_text('loss\n999\n')
    snapshot=scan(root)
    assert len(snapshot['runs'])==1 and snapshot['runs'][0]['metrics']['loss']==1
    project=projects.inspect(root);assert all('.artifacts' not in e['path'] for e in project['files'])
    asset=assets.register('TEST project','dataset',root)
    version=assets.capture(asset['id']);assert all('.artifacts' not in e['path'] for e in version['manifest'])
