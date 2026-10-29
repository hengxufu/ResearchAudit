"""Controlled TEST DATA benchmark; no external data or model execution."""
import tempfile,time,json,platform,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.tracking.engine import Engine
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/'TEST_DATA';root.mkdir();log=root/'metrics.jsonl'
    log.write_text(''.join(json.dumps({'metrics':{'loss':i/10000}})+'\n' for i in range(10000)))
    model=root/'model.pt'
    with model.open('wb') as f:f.truncate(128*1024*1024)
    e=Engine(Path(tmp)/'state.sqlite');e.register(root)
    cpu=time.process_time();start=time.perf_counter();e.scan();initial=time.perf_counter()-start
    with log.open('a') as f:f.write('{"metrics":{"loss":0.1}}\n')
    start=time.perf_counter();e.scan();latency=time.perf_counter()-start
    result={'platform':platform.platform(),'python':platform.python_version(),'records':10001,'model_bytes_metadata_only':model.stat().st_size,'log_bytes':log.stat().st_size,'initial_scan_seconds':initial,'append_reconcile_seconds':latency,'cpu_seconds':time.process_time()-cpu,'database_bytes':sum(p.stat().st_size for p in Path(tmp).glob('state.sqlite*')),'scope':'single project, warm local filesystem, explicit reconcile; excludes watcher waiting time; no hardware I/O counter measurement'}
    print(json.dumps(result,indent=2))
