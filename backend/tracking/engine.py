from ..db import ClosingConnection
"""Local tracking authority: serialized transactions commit records and cursors together."""
import sqlite3,json,uuid,hashlib,os,fnmatch,threading,time,logging,csv
from pathlib import Path
from .parsers import PARSERS,normalize,tensorboard_records
LOG=logging.getLogger(__name__)
SCHEMA='''
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,root TEXT UNIQUE,ignores TEXT);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,project_id TEXT,directory TEXT,state TEXT,basis TEXT,UNIQUE(project_id,directory));
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,project_id TEXT,run_id TEXT,path TEXT,generation INTEGER DEFAULT 0,cursor INTEGER DEFAULT 0,prefix TEXT,header TEXT,size INTEGER,mtime INTEGER,status TEXT,error TEXT,UNIQUE(project_id,path));
CREATE TABLE IF NOT EXISTS records(source_id TEXT,generation INTEGER,ordinal INTEGER,payload TEXT,PRIMARY KEY(source_id,generation,ordinal));
CREATE TABLE IF NOT EXISTS metrics(source_id TEXT,generation INTEGER,ordinal INTEGER,name TEXT,value REAL,PRIMARY KEY(source_id,generation,ordinal,name));
CREATE TABLE IF NOT EXISTS artifacts(project_id TEXT,path TEXT,size INTEGER,mtime INTEGER,PRIMARY KEY(project_id,path));
CREATE TABLE IF NOT EXISTS tracking_settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS source_generations(source_id TEXT,generation INTEGER,initial_path TEXT,committed_bytes INTEGER,committed_prefix_sha256 TEXT,first_seen TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(source_id,generation));
'''
class Engine:
    def __init__(self,db,max_read=4*1024*1024,interval=5,verification_interval=60,scan_delay=0):
        self.db=Path(db);self.db.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.stop_event=threading.Event();self.max_read=max_read;self.interval=interval;self.thread=None
        self.verification_interval=verification_interval;self.scan_delay=scan_delay
        with self.connect() as c:
            c.executescript(SCHEMA)
            columns={r[1] for r in c.execute('PRAGMA table_info(sources)')}
            for name,typ in [('file_key','TEXT'),('format','TEXT'),('checked','REAL DEFAULT 0')]:
                if name not in columns:c.execute('ALTER TABLE sources ADD COLUMN '+name+' '+typ)
            c.execute('INSERT OR IGNORE INTO source_generations(source_id,generation,initial_path,committed_bytes,committed_prefix_sha256) SELECT id,generation,path,cursor,prefix FROM sources WHERE prefix IS NOT NULL')
            c.execute('CREATE INDEX IF NOT EXISTS source_identity ON sources(project_id,file_key)')
            c.execute('CREATE INDEX IF NOT EXISTS metrics_name ON metrics(name,source_id,generation,ordinal)')
            for key,value in c.execute('SELECT key,value FROM tracking_settings'):
                if key in ('interval','verification_interval','max_read','scan_delay'):setattr(self,key,json.loads(value))
    def connect(self):
        c=sqlite3.connect(str(self.db),timeout=30,factory=ClosingConnection);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL');return c
    def register(self,root,ignores=None):
        path=Path(root).resolve()
        if not path.is_dir():raise ValueError('Project directory does not exist')
        with self.lock,self.connect() as c:
            existing=c.execute('SELECT id FROM projects WHERE root=?',(str(path),)).fetchone()
            id=existing['id'] if existing else hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()[:24]
            c.execute('INSERT INTO projects VALUES (?,?,?) ON CONFLICT(root) DO UPDATE SET ignores=excluded.ignores',(id,str(path),json.dumps(ignores or [])))
        return id
    def projects(self):
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM projects')]
    @staticmethod
    def file_key(stat):return str(stat.st_dev)+':'+str(stat.st_ino) if stat.st_ino else None
    def reconcile_moves(self,project,paths):
        identities={}
        for path,rel in paths:
            try:
                key=self.file_key(path.stat())
                if key:identities.setdefault(key,[]).append(rel)
            except OSError:continue
        with self.lock,self.connect() as c:
            for source in c.execute('SELECT id,path,file_key,cursor,prefix FROM sources WHERE project_id=?',(project['id'],)).fetchall():
                matches=identities.get(source['file_key'],[])
                if len(matches)!=1 or matches[0]==source['path']:continue
                # File identity, not basename, carries a cursor through rename/rotation.
                candidate=Path(project['root'])/matches[0]
                # Inodes can be recycled after deletion; identity alone is not enough.
                if source['prefix']:
                    try:
                        remaining=source['cursor'];checksum=hashlib.sha256()
                        with candidate.open('rb') as f:
                            while remaining:
                                block=f.read(min(1048576,remaining))
                                if not block:break
                                checksum.update(block);remaining-=len(block)
                        if remaining or checksum.hexdigest()!=source['prefix']:continue
                    except OSError:continue
                occupied=c.execute('SELECT id FROM sources WHERE project_id=? AND path=?',(project['id'],matches[0])).fetchone()
                if not occupied:c.execute('UPDATE sources SET path=? WHERE id=?',(matches[0],source['id']))
    def scan(self):
        for project in self.projects():
            root=Path(project['root']);seen=set();ignores=json.loads(project['ignores'])+['.git','.venv','node_modules','.researchaudit','__pycache__','.pytest_cache','.test-runs-*','test-results','playwright-report']
            if not root.is_dir():continue
            paths=[]
            for directory,dirs,names in os.walk(root,followlinks=False):
                if self.stop_event.is_set():return
                dirs[:]=[d for d in dirs if not (Path(directory)/d).is_symlink() and not any(fnmatch.fnmatch(d,p) or fnmatch.fnmatch((Path(directory)/d).relative_to(root).as_posix(),p) for p in ignores)]
                for name in names:
                    path=Path(directory)/name;rel=path.relative_to(root).as_posix()
                    if path.is_symlink() or any(fnmatch.fnmatch(rel,p) or fnmatch.fnmatch(name,p) for p in ignores):continue
                    seen.add(rel);paths.append((path,rel))
            self.reconcile_moves(project,paths)
            for path,rel in paths:
                if self.stop_event.is_set():return
                try:self.ingest(project,path,rel)
                except Exception:LOG.exception('Unable to ingest %s (project %s)',rel,project['id'])
                if self.scan_delay:self.stop_event.wait(self.scan_delay)
            with self.lock,self.connect() as c:
                for row in c.execute('SELECT id,path FROM sources WHERE project_id=?',(project['id'],)).fetchall():
                    if row['path'] not in seen:c.execute("UPDATE sources SET status='deleted' WHERE id=?",(row['id'],))
    def ingest(self,project,path,rel):
        stat=path.stat()
        with self.lock,self.connect() as c:
            existing=c.execute('SELECT * FROM sources WHERE project_id=? AND path=?',(project['id'],rel)).fetchone()
            format=existing['format'] if existing and existing['format'] else 'tensorboard' if path.name.startswith('events.out.tfevents') else path.suffix.lower()
            if format not in PARSERS and format!='tensorboard':
                c.execute('INSERT INTO artifacts VALUES (?,?,?,?) ON CONFLICT(project_id,path) DO UPDATE SET size=excluded.size,mtime=excluded.mtime',(project['id'],rel,stat.st_size,stat.st_mtime_ns));return
            run=hashlib.sha256((project['id']+'/'+str(Path(rel).parent)).encode()).hexdigest()[:24]
            c.execute("INSERT OR IGNORE INTO runs VALUES (?,?,?,'unknown','directory_inferred_pending_confirmation')",(run,project['id'],str(Path(rel).parent)))
            sid=existing['id'] if existing else uuid.uuid4().hex
            c.execute("INSERT OR IGNORE INTO sources(id,project_id,run_id,path,status) VALUES (?,?,?,?,'new')",(sid,project['id'],run,rel))
            source=c.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone();cursor=source['cursor'];generation=source['generation'];header=json.loads(source['header']) if source['header'] else None
            if source['status']=='current' and source['size']==stat.st_size and source['mtime']==stat.st_mtime_ns and time.time()-(source['checked'] or 0)<self.verification_interval:return
            c.execute('UPDATE sources SET file_key=?,format=? WHERE id=?',(self.file_key(stat),format,sid))
            # Rehash the committed prefix to detect even same-size/middle overwrites.
            with path.open('rb') as f:
                digest=hashlib.sha256();remaining=cursor
                while remaining:
                    chunk=f.read(min(1024*1024,remaining))
                    if not chunk:break
                    digest.update(chunk);remaining-=len(chunk)
                if remaining or (cursor and digest.hexdigest()!=source['prefix']):
                    generation+=1;cursor=0;header=None;f.seek(0);digest=hashlib.sha256()
                data=f.read(self.max_read);boundary=data.rfind(b'\n')+1;complete=data[:boundary]
                c.execute("SAVEPOINT batch")
                try:
                    if format=='tensorboard':
                        records,boundary=tensorboard_records(data);complete=data[:boundary]
                    else:records,header=PARSERS[format](complete,header)
                    if boundary==0 and len(data)==self.max_read:raise ValueError('Record exceeds incremental read bound')
                    current=path.stat()
                    if (current.st_size,current.st_mtime_ns)!=(stat.st_size,stat.st_mtime_ns):raise ValueError('Source changed during read; retry after stable write')
                    ordinal=c.execute('SELECT COUNT(*) FROM records WHERE source_id=? AND generation=?',(sid,generation)).fetchone()[0]
                    for record in records:
                        metrics=normalize(record)
                        c.execute('INSERT INTO records VALUES (?,?,?,?)',(sid,generation,ordinal,json.dumps(record,allow_nan=False)))
                        c.executemany('INSERT INTO metrics VALUES (?,?,?,?,?)',[(sid,generation,ordinal,k,v) for k,v in metrics.items()]);ordinal+=1
                    digest.update(complete)
                    c.execute('UPDATE sources SET checked=? WHERE id=?',(time.time(),sid))
                    c.execute('UPDATE sources SET generation=?,cursor=?,prefix=?,header=?,size=?,mtime=?,status=?,error=NULL WHERE id=?',(generation,cursor+boundary,digest.hexdigest(),json.dumps(header),stat.st_size,stat.st_mtime_ns,'pending' if cursor+boundary<stat.st_size else 'current',sid))
                    c.execute('INSERT INTO source_generations(source_id,generation,initial_path,committed_bytes,committed_prefix_sha256) VALUES (?,?,?,?,?) ON CONFLICT(source_id,generation) DO UPDATE SET committed_bytes=excluded.committed_bytes,committed_prefix_sha256=excluded.committed_prefix_sha256',(sid,generation,rel,cursor+boundary,digest.hexdigest()))
                except (ValueError,TypeError,UnicodeError,csv.Error) as error:
                    # Whole batch and cursor remain uncommitted on invalid input.
                    c.execute("ROLLBACK TO batch")
                    c.execute("UPDATE sources SET status='error',error=? WHERE id=?",(str(error),sid))
    def diagnostics(self):
        with self.connect() as c:
            return {'projects':self.projects(),'sources':[dict(r) for r in c.execute('SELECT * FROM sources')],'runs':[dict(r) for r in c.execute('SELECT * FROM runs')],'metric_count':c.execute('SELECT COUNT(*) FROM metrics').fetchone()[0]}
    def observations(self,run):
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT m.*,s.path FROM metrics m JOIN sources s ON m.source_id=s.id WHERE s.run_id=? ORDER BY s.path,m.generation,m.ordinal',(run,))]
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop_event.clear()
        def work():
            from watchfiles import watch
            while not self.stop_event.is_set():
                try:
                    self.scan();roots=[p['root'] for p in self.projects() if Path(p['root']).is_dir()]
                    if not roots:self.stop_event.wait(self.interval);continue
                    for changes in watch(*roots,stop_event=self.stop_event,yield_on_timeout=True,rust_timeout=int(self.interval*1000)):
                        self.scan();break
                except Exception:LOG.exception('Tracking retry');self.stop_event.wait(self.interval)
        self.thread=threading.Thread(target=work,daemon=True);self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=10)
    def backup(self,target):
        with self.lock,self.connect() as c,sqlite3.connect(str(target)) as backup:c.backup(backup)
