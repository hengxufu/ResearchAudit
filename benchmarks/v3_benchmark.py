"""TEST DATA ONLY: reproducible local data browsing + DAG latency benchmark."""
import sys,json,time,platform,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import h5py,polars as pl,psutil
from backend import storage
from backend.v2 import assets
from backend.v3 import data_studio,workflows
from backend.orchestrator import Orchestrator

from benchmarks.paths import temporary_root

def main():
    process=psutil.Process();old=storage.DB
    with tempfile.TemporaryDirectory(dir=temporary_root(),prefix='.test-runs-v3-benchmark-') as temp:
        root=Path(temp);storage.DB=root/'state';storage.DB.mkdir()
        rng=np.random.default_rng(7)
        # Dense 32 MB HDF5 on disk, produced in chunks rather than a sparse logical file.
        with h5py.File(root/'TEST_field.h5','w') as f:
            a=f.create_dataset('temperature',(4000,1000),dtype='f8',chunks=(100,100))
            for i in range(0,4000,100):a[i:i+100]=rng.normal(300,2,size=(100,1000))
        pl.DataFrame({'step':np.arange(100000),'loss':rng.random(100000)}).write_csv(root/'TEST_table.csv')
        asset=assets.register('TEST benchmark','dataset',root);base_rss=process.memory_info().rss;peak=[base_rss];stop=threading.Event()
        def sample():
            while not stop.wait(.01):peak[0]=max(peak[0],process.memory_info().rss)
        sampler=threading.Thread(target=sample,daemon=True);sampler.start();io=process.io_counters();cpu=time.process_time()
        def timed(fn):
            start=time.perf_counter();result=fn();return time.perf_counter()-start,result
        meta,_=timed(lambda:data_studio.inspect(asset['id'],'TEST_field.h5'))
        durations=[]
        for _ in range(30):
            duration,result=timed(lambda:data_studio.array_slice(asset['id'],'TEST_field.h5','temperature',[[500,510,1],[500,510,1]]));durations.append(duration);assert result['shape']==[10,10]
        table,result=timed(lambda:data_studio.table(asset['id'],'TEST_table.csv',90000,50));assert result['returned']==50
        engine=Orchestrator(root/'executor',2);engine.start();wf=workflows.WorkflowEngine(engine)
        try:
            spec={'argv':[sys.executable,'-c','print("TEST benchmark")'],'cwd':str(root)}
            definition=workflows.save({'name':'TEST concurrent DAG','nodes':[{'id':str(i),'kind':'command','config':spec} for i in range(4)]})
            start=time.perf_counter();run=wf.start(definition['id'],1,True);deadline=time.monotonic()+30
            while wf.get(run['id'])['state']=='Running' and time.monotonic()<deadline:time.sleep(.025)
            final=wf.get(run['id']);elapsed=time.perf_counter()-start;assert final['state']=='Succeeded',final
            end_io=process.io_counters();stop.set();sampler.join();peak[0]=max(peak[0],process.memory_info().rss)
            result={'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':psutil.cpu_count(),'physical_memory_bytes':psutil.virtual_memory().total,'python':platform.python_version(),'numpy':np.__version__,'h5py':h5py.__version__,'polars':pl.__version__,'hdf5_logical_bytes':32000000,'hdf5_disk_bytes':(root/'TEST_field.h5').stat().st_size,'csv_rows':100000,'csv_disk_bytes':(root/'TEST_table.csv').stat().st_size,'hdf5_metadata_seconds':meta,'hdf5_slice_100_elements_30_trials_median_seconds':float(np.median(durations)),'hdf5_slice_p95_seconds':float(np.quantile(durations,.95)),'csv_page_offset_90000_50_rows_seconds':table,'four_command_dag_seconds':elapsed,'dag_state':final['state'],'concurrency':2,'parent_cpu_seconds':time.process_time()-cpu,'parent_rss_baseline_bytes':base_rss,'sampled_parent_peak_rss_bytes':peak[0],'sampled_parent_rss_growth_bytes':peak[0]-base_rss,'parent_io_read_bytes':end_io.read_bytes-io.read_bytes,'parent_io_write_bytes':end_io.write_bytes-io.write_bytes,'persistent_state_bytes':sum(p.stat().st_size for p in storage.DB.rglob('*') if p.is_file()),'conditions':'Warm local Windows workspace disk; data generation excluded; all files synthetic TEST DATA; 10 ms parent RSS sampling can miss short peaks; parent counters exclude child processes; IO counters are OS process accounting, not physical device traffic; one benchmark run, not an endurance or cold-cache claim.'}
            print(json.dumps(result,indent=2))
        finally:wf.stop();engine.stop();storage.DB=old
if __name__=='__main__':main()
