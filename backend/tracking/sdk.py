"""Optional SDK. JSONL protocol is also writable from C++ without this module."""
import json,os,threading,time
class RunLogger:
    def __init__(self,path,run_id):self.path=path;self.run_id=run_id;self.lock=threading.Lock()
    def log(self,metrics,step,state='running',units=None,definitions=None):
        value={'run_id':self.run_id,'step':step,'timestamp':time.time(),'state':state,'metrics':metrics,'units':units or {},'definitions':definitions or {}}
        data=(json.dumps(value,allow_nan=False)+'\n').encode()
        with self.lock,open(self.path,'ab') as f:f.write(data);f.flush();os.fsync(f.fileno())
