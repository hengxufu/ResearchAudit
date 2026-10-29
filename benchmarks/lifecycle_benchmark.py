"""TEST DATA: 1,000 runs, 100,000 observations, three real queued commands."""
import json,tempfile,time,os,sys,platform,tracemalloc
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import storage
from backend.orchestrator import Orchestrator
tracemalloc.start()
with tempfile.TemporaryDirectory() as tmp:
    previous=storage.DB;storage.DB=Path(tmp)/'db'
    try:
        runs=[{'id':f'TEST-{i}','name':f'TEST-{i}','params':{'seed':i},'metrics':{'loss':float(i)},'series':{'loss':[float(j) for j in range(100)]},'sources':[]} for i in range(1000)]
        cpu=time.process_time();start=time.perf_counter();id=storage.save('TEST_DATA',{'root':'TEST_DATA','runs':runs,'evidence':[],'issues':[],'git':{'commit':None,'status':None}});import_seconds=time.perf_counter()-start
        start=time.perf_counter();page=storage.query_metrics(id,'loss',limit=100000);query_seconds=time.perf_counter()-start
        engine=Orchestrator(storage.DB/'execution',concurrency=2);engine.start();ids=[]
        start=time.perf_counter()
        for i in range(3):
            r=engine.create({'argv':[sys.executable,'-c','import time;print("TEST DATA");time.sleep(.2)'],'cwd':tmp});ids.append(r['id']);engine.enqueue(r['id'])
        deadline=time.monotonic()+30
        while time.monotonic()<deadline and any(engine.get(i)['state'] not in ('Succeeded','Failed','Cancelled','Interrupted') for i in ids):time.sleep(.05)
        states=[engine.get(i)['state'] for i in ids];execution_seconds=time.perf_counter()-start;engine.stop()
        result={'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'python':platform.python_version(),'runs':1000,'observations':len(page),'import_seconds':import_seconds,'duckdb_query_seconds':query_seconds,'three_command_seconds':execution_seconds,'command_states':states,'cpu_seconds_parent':time.process_time()-cpu,'peak_python_allocation_bytes':tracemalloc.get_traced_memory()[1],'storage_bytes':sum(p.stat().st_size for p in storage.DB.rglob('*') if p.is_file()),'conditions':'Temporary local directory, warm cache, concurrency limit 2. CPU excludes children; tracemalloc excludes native allocations; browser not measured.'}
        print(json.dumps(result,indent=2));assert len(page)==100000 and states==['Succeeded']*3
    finally:storage.DB=previous
