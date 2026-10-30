"""TEST DATA: stat-only project discovery and GP proposals; measured local counters."""
import sys,time,json,tempfile,platform
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psutil
from backend import storage
from backend.v4 import projects,optimization

from benchmarks.paths import temporary_root

def main():
    previous=storage.DB;p=psutil.Process()
    with tempfile.TemporaryDirectory(dir=temporary_root(),prefix='.test-runs-v4-benchmark-') as tmp:
        root=Path(tmp)/'TEST_PROJECT';root.mkdir();storage.DB=Path(tmp)/'state'
        for i in range(1000):(root/f'log{i}.csv').write_text('loss\n1\n')
        with (root/'TEST_weights.pt').open('wb') as f:f.truncate(1024**3)
        before=p.io_counters();cpu=time.process_time();rss=p.memory_info().rss;start=time.perf_counter()
        try:
            doc=projects.inspect(root);scan_seconds=time.perf_counter()-start
            runs=[]
            for i in range(30):
                x=i/29;value=(x-.3)**2
                runs.append({'id':'TEST'+str(i),'name':'TEST'+str(i),'params':{'x':x,'seed':i,'dataset':'TEST','dataset_version':'1','split':'test','evaluation_protocol':'TEST','metric_definitions':{}},'metrics':{'loss':value},'series':{'loss':[value]},'metric_definitions':{'loss':{'direction':'minimize','unit':'1','method':'TEST squared error'}},'sources':[]})
            sid=storage.save('TEST',{'root':'TEST','runs':runs,'evidence':[],'issues':[],'git':{}});refs=[{'snapshot_id':sid,'run_id':r['id']} for r in runs]
            start=time.perf_counter();proposal=optimization.propose(refs,'loss',{'x':[0,1]},'bayesian',5,5,7,[]);gp_seconds=time.perf_counter()-start
            after=p.io_counters();assert len(doc['files'])==1001 and len(proposal['candidates'])==5
            print(json.dumps({'platform':platform.platform(),'cpu':platform.processor(),'logical_cpus':psutil.cpu_count(),'python':platform.python_version(),'files':1001,'stat_only_sparse_model_logical_bytes':1024**3,'project_discovery_seconds':scan_seconds,'observations':30,'gp_pool':512,'gp_suggest_5_seconds':gp_seconds,'parent_cpu_seconds':time.process_time()-cpu,'parent_rss_before':rss,'parent_rss_after':p.memory_info().rss,'parent_io_read_bytes':after.read_bytes-before.read_bytes,'parent_io_write_bytes':after.write_bytes-before.write_bytes,'persistent_bytes':sum(f.stat().st_size for f in storage.DB.rglob('*') if f.is_file()),'conditions':'TEST DATA only, warm local desktop, one run; sparse 1 GiB model is stat-only test not dense throughput; generation excluded, parent counters not physical disk, no peak/endurance claim'},indent=2))
        finally:storage.DB=previous
if __name__=='__main__':main()
