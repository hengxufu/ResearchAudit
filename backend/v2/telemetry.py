"""Read-only optional NVIDIA telemetry. No driver installation or GPU control."""
import csv,io,shutil,subprocess,time,threading
LOCK=threading.Lock();CACHE=None;STAMP=0

def gpu_status():
    global CACHE,STAMP
    with LOCK:
        if CACHE is not None and time.monotonic()-STAMP<5:return CACHE
        executable=shutil.which('nvidia-smi')
        if not executable:result={'status':'UNKNOWN','reason':'nvidia-smi is not available','gpus':[]}
        else:
            try:
                response=subprocess.run([executable,'--query-gpu=index,name,utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,check=True)
                rows=[]
                for row in csv.reader(io.StringIO(response.stdout)):
                    if len(row)!=5:continue
                    def number(value):
                        try:return float(value.strip())
                        except ValueError:return None
                    rows.append({'index':row[0].strip(),'name':row[1].strip(),'utilization_percent':number(row[2]),'memory_used_mib':number(row[3]),'memory_total_mib':number(row[4])})
                result={'status':'PASS' if rows else 'UNKNOWN','reason':'Read-only device telemetry, not per-run attribution','gpus':rows,'sample_time':time.time()}
            except (OSError,subprocess.SubprocessError) as e:result={'status':'UNKNOWN','reason':str(e),'gpus':[]}
        CACHE=result;STAMP=time.monotonic();return result
