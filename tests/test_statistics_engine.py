"""TEST DATA: paired run analysis and hash-verifiable report archive."""
import io,json,hashlib,zipfile
import pytest
from backend import storage,statistics_engine as se
from fastapi.testclient import TestClient
from backend.main import app

def test_paired_analysis_and_no_epoch_replicates(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    runs=[];left=[];right=[]
    for model,values in [('a',[1,2,4]),('b',[.5,1,2])]:
        for seed,value in enumerate(values):
            rid=model+str(seed);runs.append({'id':rid,'name':rid,'params':{'seed':seed,'dataset':'TEST','dataset_version':'1','split':'test','evaluation_protocol':'v1'},'metrics':{'loss':value},'series':{'loss':[value]},'sources':[],'metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST mean'}}})
    id=storage.save('TEST',{'root':'TEST','runs':runs,'evidence':[],'git':{'commit':None,'status':None},'issues':[]})
    for r in runs:
        (left if r['id'][0]=='a' else right).append({'snapshot_id':id,'run_id':r['id'],'metric':'loss'})
    result=se.paired(left,right,True,True,42)
    assert result['result']['mean_difference']==pytest.approx(7/6)
    assert result['result']['n_pairs']==3
    assert se.get(result['id'])==result
    assert se.describe(left[0])['result']['finite_count']==1
    with pytest.raises(ValueError):se.paired(left,left,True,True)
    with pytest.raises(ValueError):se.paired(left,right,False,True)
    c=TestClient(app);r=c.get(f'/api/projects/{id}/package');assert r.status_code==200
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        manifest=json.loads(z.read('manifest.json'))
        for path,entry in manifest.items():assert hashlib.sha256(z.read(path)).hexdigest()==entry['sha256']
    assert c.get(f'/api/projects/{id}/report-export?format=html').status_code==200
    assert c.get(f'/api/projects/{id}/report-export?format=json').json()['snapshot']['runs']==runs
