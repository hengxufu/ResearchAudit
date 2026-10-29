"""Local tracking authority: serialized transactions commit records and cursors together."""
import sqlite3,json,uuid,hashlib,os,fnmatch,threading,time,logging,csv
from pathlib import Path
from .parsers import PARSERS,normalize
LOG=logging.getLogger(__name__)
SCHEMA='''
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,root TEXT UNIQUE,ignores TEXT);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,project_id TEXT,directory TEXT,state TEXT,basis TEXT,UNIQUE(project_id,directory));
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,project_id TEXT,run_id TEXT,path TEXT,generation INTEGER DEFAULT 0,cursor INTEGER DEFAULT 0,prefix TEXT,header TEXT,size INTEGER,mtime INTEGER,status TEXT,error TEXT,UNIQUE(project_id,path));
CREATE TABLE IF NOT EXISTS records(source_id TEXT,generation INTEGER,ordinal INTEGER,payload TEXT,PRIMARY KEY(source_id,generation,ordinal));
CREATE TABLE IF NOT EXISTS metrics(source_id TEXT,generation INTEGER,ordinal INTEGER,name TEXT,value REAL,PRIMARY KEY(source_id,generation,ordinal,name));
CREATE TABLE IF NOT EXISTS artifacts(project_id TEXT,path TEXT,size INTEGER,mtime INTEGER,PRIMARY KEY(project_id,path));
'''
class Engine:
    def __init__(self,db,max_read=4*1024*1024,interval=5):
        self.db=Path(db);self.db.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.stop_event=threading.Event();self.max_read=max_read;self.interval=interval;self.thread=None
        with self.connect() as c:c.executescript(SCHEMA)
    def connect(self):
        c=sqlite3.connect(str(self.db),timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL');return c
    def register(self,root,ignores=None):
        path=Path(root).resolve()
        if not path.is_dir():raise ValueError('Project directory does not exist')
        with self.lock,self.connect() as c:
            id=hashlib.sha256(str(path).casefold().encode()).hexdigest()[:24]
            c.execute('INSERT INTO projects VALUES (?,?,?) ON CONFLICT(root) DO UPDATE SET ignores=excluded.ignores',(id,str(path),json.dumps(ignores or [])))
        return id
    def projects(self):
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM projects')]
    def scan(self):
        for project in self.projects():
            root=Path(project['root']);seen=set();ignores=json.loads(project['ignores'])+['.git','.venv','node_modules','.researchaudit','__pycache__']
            if not root.is_dir():continue
            for directory,dirs,names in os.walk(root,followlinks=False):
                if self.stop_event.is_set():return
                dirs[:]=[d for d in dirs if not (Path(directory)/d).is_symlink() and not any(fnmatch.fnmatch(d,p) or fnmatch.fnmatch((Path(directory)/d).relative_to(root).as_posix(),p) for p in ignores)]
                for name in names:
                    path=Path(directory)/name;rel=path.relative_to(root).as_posix()
                    if path.is_symlink() or any(fnmatch.fnmatch(rel,p) or fnmatch.fnmatch(name,p) for p in ignores):continue
                    seen.add(rel)
                    try:self.ingest(project,path,rel)
                    except Exception:
                        # Isolate file/plugin failures so remaining sources are still collected.
                        LOG.exception('Unable to ingest %s (project %s)',rel,project['id'])
            with self.lock,self.connect() as c:
                for row in c.execute('SELECT id,path FROM sources WHERE project_id=?',(project['id'],)).fetchall():
                    if row['path'] not in seen:c.execute("UPDATE sources SET status='deleted' WHERE id=?",(row['id'],))
    def ingest(self,project,path,rel):
        stat=path.stat()
        with self.lock,self.connect() as c:
            if path.suffix.lower() not in PARSERS:
                c.execute('INSERT INTO artifacts VALUES (?,?,?,?) ON CONFLICT(project_id,path) DO UPDATE SET size=excluded.size,mtime=excluded.mtime',(project['id'],rel,stat.st_size,stat.st_mtime_ns));return
            run=hashlib.sha256((project['id']+'/'+str(Path(rel).parent)).encode()).hexdigest()[:24]
            c.execute("INSERT OR IGNORE INTO runs VALUES (?,?,?,'unknown','directory_inferred_pending_confirmation')",(run,project['id'],str(Path(rel).parent)))
            sid=hashlib.sha256((project['id']+'/'+rel).encode()).hexdigest()
            c.execute("INSERT OR IGNORE INTO sources(id,project_id,run_id,path,status) VALUES (?,?,?,?,'new')",(sid,project['id'],run,rel))
            source=c.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone();cursor=source['cursor'];generation=source['generation'];header=json.loads(source['header']) if source['header'] else None
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
                    records,header=PARSERS[path.suffix.lower()](complete,header)
                    ordinal=c.execute('SELECT COUNT(*) FROM records WHERE source_id=? AND generation=?',(sid,generation)).fetchone()[0]
                    for record in records:
                        metrics=normalize(record)
                        c.execute('INSERT INTO records VALUES (?,?,?,?)',(sid,generation,ordinal,json.dumps(record,allow_nan=False)))
                        c.executemany('INSERT INTO metrics VALUES (?,?,?,?,?)',[(sid,generation,ordinal,k,v) for k,v in metrics.items()]);ordinal+=1
                    digest.update(complete)
                    c.execute('UPDATE sources SET generation=?,cursor=?,prefix=?,header=?,size=?,mtime=?,status=?,error=NULL WHERE id=?',(generation,cursor+boundary,digest.hexdigest(),json.dumps(header),stat.st_size,stat.st_mtime_ns,'pending' if cursor+boundary<stat.st_size else 'current',sid))
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
