"""TEST DATA: transactional incremental collection and restart reconciliation."""
from backend.tracking.engine import Engine

def test_append_partial_restart(tmp_path):
    root=tmp_path/'TEST_DATA';root.mkdir();p=root/'log.jsonl';p.write_bytes(b'{"metrics":{"loss":3}}\n{"metrics":')
    engine=Engine(tmp_path/'state.sqlite');engine.register(root);engine.scan()
    assert engine.diagnostics()['metric_count']==1
    assert engine.diagnostics()['sources'][0]['status']=='pending'
    with p.open('ab') as f:f.write(b'{"loss":2}}\n')
    engine=Engine(tmp_path/'state.sqlite');engine.scan();engine.scan()
    assert engine.diagnostics()['metric_count']==2
    p.write_text('{"metrics":{"loss":1}}\n')
    engine.scan()
    assert engine.diagnostics()['sources'][0]['generation']==1
    assert engine.diagnostics()['metric_count']==3

def test_csv_runs_artifacts_and_errors(tmp_path):
    root=tmp_path/'TEST_DATA';root.mkdir()
    for name in ('one','two'):
        d=root/name;d.mkdir();(d/'m.csv').write_text('loss\n3\n2')
    (root/'model.pt').write_bytes(b'FAKE TEST MODEL')
    engine=Engine(tmp_path/'db.sqlite');engine.register(root);engine.scan()
    diag=engine.diagnostics();assert len(diag['runs'])==2 and diag['metric_count']==2
    assert len({r['id'] for r in diag['runs']})==2
    (root/'one'/'m.csv').write_text('loss\nnot,a,valid,row\n')
    engine.scan();assert any(s['status']=='error' for s in engine.diagnostics()['sources'])
    (root/'two'/'m.csv').unlink();engine.scan()
    assert any(s['status']=='deleted' for s in engine.diagnostics()['sources'])
    engine.backup(tmp_path/'backup.sqlite')
    assert Engine(tmp_path/'backup.sqlite').diagnostics()['metric_count']==2
