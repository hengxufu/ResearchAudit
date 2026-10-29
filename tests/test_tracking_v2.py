"""TEST DATA: real file rotation, TFRecord partial frames and forced process crash."""
import os,subprocess,sys,json
import pytest
from pathlib import Path
from backend.tracking.engine import Engine
from tensorboard.summary.writer.event_file_writer import EventFileWriter
from tensorboard.compat.proto.event_pb2 import Event
from tensorboard.compat.proto.summary_pb2 import Summary

def test_rotation_retains_cursor_and_no_duplicate(tmp_path):
    root=tmp_path/'TEST_DATA';root.mkdir();path=root/'train.csv';path.write_text('loss\n3\n2\n')
    e=Engine(tmp_path/'tracking.sqlite');e.register(root);e.scan()
    old=e.diagnostics()['sources'][0]['id']
    path.rename(root/'train.csv.1');path.write_text('loss\n1\n');e.scan();e.scan()
    d=e.diagnostics();assert d['metric_count']==3
    moved=next(s for s in d['sources'] if s['id']==old)
    assert moved['path']=='train.csv.1' and moved['cursor']==(root/'train.csv.1').stat().st_size

def test_tensorboard_partial_frame_crc_and_increment(tmp_path):
    source=tmp_path/'source';source.mkdir();writer=EventFileWriter(str(source));writer.add_event(Event(step=2,summary=Summary(value=[Summary.Value(tag='loss',simple_value=3)])));writer.close()
    content=next(source.iterdir()).read_bytes();root=tmp_path/'TEST_DATA';root.mkdir();path=root/'events.out.tfevents.test';path.write_bytes(content[:-3])
    e=Engine(tmp_path/'tracking.sqlite');e.register(root);e.scan();assert e.diagnostics()['metric_count']==0
    with path.open('ab') as f:f.write(content[-3:])
    e.scan();e.scan();assert e.diagnostics()['metric_count']==1
    corrupted=bytearray(content);corrupted[-1]^=255;path.write_bytes(corrupted);e.scan()
    assert e.diagnostics()['sources'][0]['status']=='error'

@pytest.mark.parametrize('phase',['normalization','cursor_update'])
def test_transaction_process_death_and_restart(tmp_path,phase):
    root=tmp_path/'TEST_DATA';root.mkdir();p=root/'metrics.jsonl';p.write_text('{"metrics":{"loss":3}}\n')
    db=tmp_path/'tracking.sqlite';e=Engine(db);e.register(root);e.scan()
    with p.open('a') as f:f.write('{"metrics":{"loss":2}}\n')
    code='''import os,sys
from pathlib import Path
from backend.tracking.engine import Engine
import backend.tracking.engine as module
engine=Engine(Path(sys.argv[1]))
def crash(record):os._exit(93)
if sys.argv[2]=='normalization':module.normalize=crash
else:
    original=engine.connect
    class CrashConnection:
        def __init__(self):self.connection=original()
        def __enter__(self):self.connection.__enter__();return self
        def __exit__(self,*args):return self.connection.__exit__(*args)
        def execute(self,sql,*args):
            result=self.connection.execute(sql,*args)
            if sql.startswith('UPDATE sources SET generation='):os._exit(93)
            return result
        def __getattr__(self,key):return getattr(self.connection,key)
    engine.connect=CrashConnection
engine.scan()
'''
    process=subprocess.run([sys.executable,'-c',code,str(db),phase],cwd=str(Path(__file__).resolve().parents[1]),timeout=20)
    assert process.returncode==93
    restarted=Engine(db);assert restarted.diagnostics()['metric_count']==1
    restarted.scan();restarted.scan();assert restarted.diagnostics()['metric_count']==2

def test_unchanged_log_skips_content_reads(tmp_path,monkeypatch):
    root=tmp_path/'TEST_DATA';root.mkdir();p=root/'metrics.csv';p.write_text('loss\n1\n')
    e=Engine(tmp_path/'tracking.sqlite',verification_interval=60);e.register(root);e.scan()
    original=Path.open
    def blocked(self,*args,**kwargs):
        if self==p:raise AssertionError('Unchanged log was fully reread')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',blocked);e.scan()
    assert e.diagnostics()['metric_count']==1


def test_continuous_half_record_append_is_exactly_once(tmp_path):
    import threading,time
    root=tmp_path/'TEST_STREAM';root.mkdir();path=root/'metrics.jsonl';path.write_bytes(b'')
    engine=Engine(tmp_path/'db.sqlite',max_read=128);engine.register(root)
    count=100
    def append():
        with path.open('ab',buffering=0) as f:
            for i in range(count):
                line=(json.dumps({'step':i,'metrics':{'loss':float(i)}})+'\n').encode();half=len(line)//2
                f.write(line[:half]);time.sleep(.002);f.write(line[half:]);os.fsync(f.fileno());time.sleep(.002)
    writer=threading.Thread(target=append);writer.start()
    while writer.is_alive():engine.scan();time.sleep(.001)
    writer.join()
    for _ in range(100):
        engine.scan()
        if engine.diagnostics()['sources'][0]['status']=='current':break
    assert engine.diagnostics()['metric_count']==count
    metrics=engine.observations(engine.diagnostics()['runs'][0]['id'])
    assert sorted(r['value'] for r in metrics)==list(map(float,range(count)))

def test_source_generation_hashes_survive_truncation(tmp_path):
    import hashlib
    root=tmp_path/'TEST';root.mkdir();path=root/'m.jsonl';first=b'{"metrics":{"x":1}}\n';second=b'{"metrics":{"x":2}}\n'
    path.write_bytes(first);e=Engine(tmp_path/'journal.sqlite');e.register(root);e.scan()
    path.write_bytes(second);e.scan()
    with e.connect() as c:versions=[dict(r) for r in c.execute('SELECT * FROM source_generations ORDER BY generation')]
    assert len(versions)==2
    assert versions[0]['committed_prefix_sha256']==hashlib.sha256(first).hexdigest()
    assert versions[1]['committed_prefix_sha256']==hashlib.sha256(second).hexdigest()

def test_recycled_file_identity_does_not_merge_unrelated_runs(tmp_path,monkeypatch):
    root=tmp_path/'TEST';(root/'one').mkdir(parents=True);first=root/'one'/'m.csv';first.write_bytes(b'loss\n1\n')
    e=Engine(tmp_path/'db.sqlite');monkeypatch.setattr(e,'file_key',lambda stat:'TEST-recycled-identity');e.register(root);e.scan()
    first.unlink();(root/'two').mkdir();(root/'two'/'m.csv').write_bytes(b'loss\n2\n');e.scan()
    data=e.diagnostics();assert len(data['runs'])==2
    assert len(data['sources'])==2 and data['metric_count']==2
