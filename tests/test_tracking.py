"""TEST DATA: transactional incremental collection and restart reconciliation."""
from backend.tracking.engine import Engine
import logging
import sqlite3
import pytest

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


@pytest.mark.parametrize('error_type', [OSError, RuntimeError, sqlite3.IntegrityError])
def test_scan_isolates_ingest_failure_and_retries(tmp_path, monkeypatch, caplog, error_type):
    root = tmp_path / 'TEST_DATA'
    root.mkdir()
    for name in ('one.csv', 'two.csv'):
        (root / name).write_text('loss\n3\n', encoding='utf-8')
    engine = Engine(tmp_path / 'state.sqlite')
    project_id = engine.register(root)
    original_ingest = engine.ingest
    attempted = []

    def fail_first(project, path, rel):
        attempted.append(rel)
        if len(attempted) == 1:
            raise error_type('TEST DATA ingestion failure')
        return original_ingest(project, path, rel)

    monkeypatch.setattr(engine, 'ingest', fail_first)
    with caplog.at_level(logging.ERROR, logger='backend.tracking.engine'):
        engine.scan()

    # The failed first file must not prevent collecting the next file.
    assert len(attempted) == 2
    assert engine.diagnostics()['metric_count'] == 1
    failure = next(r for r in caplog.records if r.name == 'backend.tracking.engine')
    assert attempted[0] in failure.getMessage()
    assert project_id in failure.getMessage()
    assert failure.exc_info[0] is error_type

    # A later reconciliation retries the failed source without duplicating the good one.
    monkeypatch.setattr(engine, 'ingest', original_ingest)
    engine.scan()
    engine.scan()
    assert engine.diagnostics()['metric_count'] == 2
