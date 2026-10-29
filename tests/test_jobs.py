"""TEST DATA: durable task lifecycle and cancellation commit boundary."""
from backend import jobs,storage
from backend.main import app
from fastapi.testclient import TestClient

def queued(tmp_path,monkeypatch,id='test'):
    monkeypatch.setattr(storage,'DB',tmp_path/'db')
    root=tmp_path/'TEST_DATA';root.mkdir();(root/'metrics.csv').write_text('loss\n3\n1\n')
    with storage.connect() as c:
        jobs.setup(c);c.execute('INSERT INTO import_jobs(id,path,status) VALUES (?,?,?)',(id,str(root),'queued'))
    return id

def test_worker_success(tmp_path,monkeypatch):
    id=queued(tmp_path,monkeypatch);jobs.execute(id)
    result=jobs.get(id)
    assert result['status']=='completed'
    assert storage.get(result['snapshot_id'])['runs'][0]['metrics']['loss']==1

def test_running_cancel_never_commits(tmp_path,monkeypatch):
    id=queued(tmp_path,monkeypatch)
    def cancelling_scan(path,checkpoint):
        jobs.cancel(id);checkpoint(1,2,'TEST_DATA');raise AssertionError('Cancellation was ignored')
    monkeypatch.setattr(jobs,'scan',cancelling_scan);jobs.execute(id)
    assert jobs.get(id)['status']=='cancelled' and storage.listing()==[]

def test_queue_cancel_recovery_and_errors(tmp_path,monkeypatch):
    id=queued(tmp_path,monkeypatch)
    assert jobs.cancel(id)['status']=='cancelled';jobs.execute(id)
    assert not storage.listing()
    jobs.change(id,status='running');jobs.recover()
    assert jobs.get(id)['status']=='interrupted'
    jobs.change(id,status='queued',path=str(tmp_path/'missing'));jobs.execute(id)
    assert jobs.get(id)['status']=='failed'
    c=TestClient(app)
    assert c.get('/api/import-jobs/missing').status_code==404
    assert c.post('/api/import-jobs/missing/cancel').status_code==404
    jobs.change(id,status='committing')
    assert c.post('/api/import-jobs/test/cancel').status_code==409
