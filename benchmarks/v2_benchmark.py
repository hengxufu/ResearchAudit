"""TEST DATA scale benchmark: indexed history, 1100 runs, 110000 metrics, real concurrent tasks."""
import sys,os,json,time,tempfile,platform
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psutil
from backend import storage,history
from backend.orchestrator import Orchestrator
p=psutil.Process();before=p.io_counters();cpu=time.process_time();old=storage.DB
from benchmarks.paths import temporary_root
with tempfile.TemporaryDirectory(dir=temporary_root(),prefix='.test-runs-benchmark-') as tmp:
    storage.DB=Path(tmp)/'state'
    try:
        runs=[{'id':'TEST-RUN-'+str(i),'name':'TEST-'+str(i),'params':{'seed':i},'metrics':{'loss':float(i)},'series':{'loss':[float(v) for v in range(100)]},'sources':[]} for i in range(1100)]
        start=time.perf_counter();sid=storage.save('TEST_DATA',{'root':'TEST_DATA','runs':runs,'evidence':[],'issues':[],'git':{'commit':None,'status':None}});ingest=time.perf_counter()-start
        start=time.perf_counter();page=history.records(limit=25,offset=1000);history_seconds=time.perf_counter()-start
        start=time.perf_counter();observations=storage.query_metrics(sid,'loss',limit=100000);query=time.perf_counter()-start
        engine=Orchestrator(storage.DB/'execution',2);engine.start();ids=[];start=time.perf_counter()
        for i in range(3):
            r=engine.create({'argv':[sys.executable,'-c','import time;print("TEST DATA");time.sleep(.2)'],'cwd':tmp});ids.append(r['id']);engine.enqueue(r['id'])
        deadline=time.monotonic()+30
        while time.monotonic()<deadline and any(engine.get(id)['state'] not in ('Succeeded','Failed','Cancelled','Interrupted') for id in ids):time.sleep(.05)
        states=[engine.get(id)['state'] for id in ids];execution=time.perf_counter()-start;engine.stop();mem=p.memory_info();after=p.io_counters()
        result={'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':psutil.cpu_count(),'python':platform.python_version(),'runs':1100,'stored_observations':110000,'queried_observations':len(observations),'snapshot_and_index_seconds':ingest,'history_page_offset_1000_seconds':history_seconds,'duckdb_query_seconds':query,'three_commands_seconds':execution,'states':states,'parent_cpu_seconds':time.process_time()-cpu,'parent_rss_bytes':mem.rss,'parent_peak_working_set_bytes':getattr(mem,'peak_wset',None),'parent_io_read_bytes':after.read_bytes-before.read_bytes,'parent_io_write_bytes':after.write_bytes-before.write_bytes,'storage_bytes':sum(f.stat().st_size for f in storage.DB.rglob('*') if f.is_file()),'conditions':'Warm local workspace temporary directory; concurrency=2; cumulative parent process counters, excludes child CPU/memory; synthetic TEST DATA; no GPU measurement.'}
        assert page['total']==1100 and states==['Succeeded']*3
        print(json.dumps(result,indent=2))
    finally:storage.DB=old
