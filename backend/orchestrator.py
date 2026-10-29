from .db import ClosingConnection
"""Explicitly started local command execution; no shell or import-time execution."""
import json,os,platform,sqlite3,subprocess,threading,time,uuid,logging,codecs
from pathlib import Path
from .collect import git,scan
from . import storage
TERMINAL={'Succeeded','Failed','Cancelled','Interrupted'}
class Orchestrator:
    def __init__(self,home,concurrency=2):
        self.home=Path(home).resolve();self.home.mkdir(parents=True,exist_ok=True)
        self.limit=concurrency;self.lock=threading.RLock();self.processes={};self.workers={};self.stop_event=threading.Event();self.thread=None
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS execution_runs(id TEXT PRIMARY KEY,state TEXT,spec TEXT,created REAL,started REAL,finished REAL,exit_code INTEGER,pid INTEGER,snapshot_id INTEGER,error TEXT)')
    def connect(self):
        c=sqlite3.connect(str(self.home/'executions.sqlite'),timeout=30,factory=ClosingConnection);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');return c
    def get(self,id):
        with self.connect() as c:row=c.execute('SELECT * FROM execution_runs WHERE id=?',(id,)).fetchone()
        if row is None:raise KeyError(id)
        result=dict(row);result['spec']=json.loads(result['spec']);result['pause_supported']=False;result['output_dir']=str(self.home/'runs'/id);return result
    def listing(self,limit=100,offset=0):
        with self.connect() as c:ids=[r[0] for r in c.execute('SELECT id FROM execution_runs ORDER BY created DESC LIMIT ? OFFSET ?',(limit,offset))]
        return [self.get(id) for id in ids]
    def change(self,id,**fields):
        with self.connect() as c:c.execute('UPDATE execution_runs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',list(fields.values())+[id])
    def create(self,spec):
        cwd=Path(spec['cwd']).resolve()
        if not cwd.is_dir() or not spec['argv'] or any(not isinstance(v,str) or '\x00' in v for v in spec['argv']):raise ValueError('Existing cwd and nonempty argv array required')
        for dep in spec.get('dependencies',[]):self.get(dep)
        id=uuid.uuid4().hex;spec={**spec,'cwd':str(cwd)}
        with self.connect() as c:c.execute('INSERT INTO execution_runs(id,state,spec,created) VALUES (?,?,?,?)',(id,'Pending',json.dumps(spec,allow_nan=False),time.time()))
        return self.get(id)
    def enqueue(self,id):
        with self.lock:
            if self.get(id)['state']!='Pending':raise ValueError('Only Pending runs can be queued; use rerun for terminal runs')
            self.change(id,state='Queued')
        return self.get(id)
    def cancel(self,id,final_state="Cancelled",reason=None):
        with self.lock:
            state=self.get(id)['state']
            if state in TERMINAL:return self.get(id)
            process=self.processes.get(id)
            if process and process.poll() is None:
                import psutil
                try:children=psutil.Process(process.pid).children(recursive=True)
                except psutil.NoSuchProcess:children=[]
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=15)
                else:
                    import signal
                    try:os.killpg(process.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                for child in children:
                    try:child.kill()
                    except psutil.NoSuchProcess:pass
                try:process.wait(timeout=2)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            self.change(id,state=final_state,finished=time.time(),error=reason,exit_code=process.poll() if process else None)
        return self.get(id)
    def recover(self):
        # Never resume a queued command or signal a possibly reused PID after restart.
        with self.connect() as c:c.execute("UPDATE execution_runs SET state='Interrupted',finished=?,error='Service restarted; process status unverified; explicit rerun required' WHERE state IN ('Queued','Running')",(time.time(),))
    def tick(self):
        with self.lock:
            with self.connect() as c:ids=[r[0] for r in c.execute("SELECT id FROM execution_runs WHERE state='Queued' ORDER BY json_extract(spec,'$.priority') DESC,created")]
            for id in ids:
                if len(self.workers)>=self.limit:break
                run=self.get(id);deps=[self.get(d)['state'] for d in run['spec'].get('dependencies',[])]
                if any(d in TERMINAL and d!='Succeeded' for d in deps):self.change(id,state='Interrupted',finished=time.time(),error='Dependency did not succeed');continue
                if any(d!='Succeeded' for d in deps):continue
                self.change(id,state='Running',started=time.time())
                worker=threading.Thread(target=self.execute,args=(id,),daemon=True);self.workers[id]=worker;worker.start()
    def execute(self,id):
        folder=self.home/'runs'/id;folder.mkdir(parents=True,exist_ok=True)
        try:
            run=self.get(id);spec=run['spec'];env=os.environ.copy();env.update(spec.get('env',{}));env['RESEARCHAUDIT_OUTPUT_DIR']=str(folder);env['RESEARCHAUDIT_RUN_ID']=id;env.setdefault('PYTHONIOENCODING','utf-8');env.setdefault('PYTHONUNBUFFERED','1')
            metadata={**spec.get('params',{}),'execution_id':id,'argv':spec['argv'],'cwd':spec['cwd'],'params':spec.get('params',{}),'git_commit':git(spec['cwd'],'rev-parse','HEAD'),'git_status':git(spec['cwd'],'status','--porcelain'),'runner_python':platform.python_version(),'environment_capture_scope':'Runner metadata, not a complete target dependency lock','platform':platform.platform(),'environment_keys':sorted(spec.get('env',{}))}
            (folder/'config.json').write_text(json.dumps({**spec.get('params',{}),'researchaudit_execution':metadata},indent=2),encoding='utf-8')
            with (folder/'stdout.log').open('wb') as stdout,(folder/'stderr.log').open('wb') as stderr:
                with self.lock:
                    if self.get(id)['state']=='Cancelled':return
                    process=subprocess.Popen(spec['argv'],cwd=spec['cwd'],env=env,stdout=stdout,stderr=stderr,shell=False,start_new_session=os.name!='nt')
                    self.processes[id]=process;self.change(id,pid=process.pid)
                deadline=time.monotonic()+spec.get('timeout_seconds',3600)
                while True:
                    try:code=process.wait(timeout=.25);break
                    except subprocess.TimeoutExpired:
                        reason=None
                        if time.monotonic()>deadline:reason='Execution timeout'
                        if spec.get('soft_memory_mb'):
                            import psutil
                            try:
                                parent=psutil.Process(process.pid);rss=sum(p.memory_info().rss for p in [parent]+parent.children(recursive=True))
                                if rss>spec['soft_memory_mb']*1048576:reason='Soft memory watchdog exceeded (not an OS hard limit)'
                            except psutil.NoSuchProcess:pass
                        if sum((folder/name).stat().st_size for name in ('stdout.log','stderr.log'))>spec.get('log_limit_mb',100)*1048576:reason='Soft log size limit exceeded'
                        if reason:
                            self.cancel(id,final_state='Failed',reason=reason);code=process.wait(timeout=5);break
            with self.lock:
                if self.get(id)['state']=='Cancelled':return
            if code!=0 and not self.get(id)['error']:
                diagnosis={3221225781:'Windows DLL not found; check runtime dependencies',3221225785:'Windows DLL entry point not found; check runtime DLL versions'}.get(code,'Process exited with nonzero code; inspect stderr')
                self.change(id,error=diagnosis)
            self.change(id,exit_code=code)
            (folder/'execution_config.json').write_text(json.dumps({'researchaudit_execution':{'execution_id':id,'exit_code':code,'started':self.get(id)['started'],'process_finished':time.time(),'argv':spec['argv'],'cwd':spec['cwd']}},indent=2),encoding='utf-8')
            captured=scan(folder);snapshot_id=storage.save(captured['root'],captured)
            with self.lock:
                if self.get(id)['state']!='Cancelled':self.change(id,state='Succeeded' if code==0 and not self.get(id)['error'] else 'Failed',finished=time.time(),snapshot_id=snapshot_id)
        except Exception as e:
            with self.lock:
                if self.get(id)['state']!='Cancelled':self.change(id,state='Failed',finished=time.time(),error=str(e))
        finally:
            with self.lock:self.processes.pop(id,None);self.workers.pop(id,None)
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.recover();self.stop_event.clear()
        def loop():
            while not self.stop_event.wait(.15):
                try:self.tick()
                except Exception:logging.getLogger(__name__).exception('Scheduler iteration failed; retrying')
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=3)
        with self.lock:ids=list(self.workers)
        for id in ids:self.cancel(id)
        for worker in list(self.workers.values()):worker.join(timeout=20)
    def logs(self,id,stream='stdout',offset=0,limit=65536):
        self.get(id);path=self.home/'runs'/id/(stream+'.log')
        if not path.exists():return {'text':'','next_offset':offset}
        with path.open('rb') as f:
            f.seek(offset);data=f.read(limit);decoder=codecs.getincrementaldecoder('utf-8')(errors='replace');text=decoder.decode(data)
            for _ in range(3):
                if not decoder.getstate()[0]:break
                extra=f.read(1)
                if not extra:break
                data+=extra;text+=decoder.decode(extra)
            pending=decoder.getstate()[0]
        return {'text':text,'next_offset':offset+len(data)-len(pending)}

