"""Bounded local import worker with durable lifecycle and cooperative cancellation."""
import json,threading,uuid
from concurrent.futures import ThreadPoolExecutor
from . import storage
from .collect import scan
POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix='researchaudit-import')
LOCK=threading.RLock()
TERMINAL={'completed','failed','cancelled','interrupted'}

def setup(c):
    c.execute("CREATE TABLE IF NOT EXISTS import_jobs(id TEXT PRIMARY KEY,path TEXT,status TEXT,processed INTEGER DEFAULT 0,total INTEGER DEFAULT 0,current_file TEXT DEFAULT '',snapshot_id INTEGER,error TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP)")

def recover():
    with storage.connect() as c:
        setup(c)
        c.execute("UPDATE import_jobs SET status='interrupted',error='Service restarted before task completion',updated=CURRENT_TIMESTAMP WHERE status IN ('queued','running','cancelling','committing')")

def get(id):
    with storage.connect() as c:
        setup(c);c.row_factory=__import__('sqlite3').Row
        row=c.execute('SELECT * FROM import_jobs WHERE id=?',(id,)).fetchone()
    if row is None: raise KeyError(id)
    return dict(row)

def listing():
    with storage.connect() as c:
        setup(c);c.row_factory=__import__('sqlite3').Row
        return [dict(r) for r in c.execute('SELECT * FROM import_jobs ORDER BY created DESC,rowid DESC LIMIT 50')]

def change(id,**fields):
    with storage.connect() as c:
        setup(c)
        c.execute('UPDATE import_jobs SET '+','.join(k+'=?' for k in fields)+',updated=CURRENT_TIMESTAMP WHERE id=?',list(fields.values())+[id])

def cancel(id):
    with LOCK:
        job=get(id)
        if job['status']=='committing': raise ValueError('Snapshot commit has started; cancellation is no longer available')
        if job['status'] not in TERMINAL: change(id,status='cancelled' if job['status']=='queued' else 'cancelling')
    return get(id)

def submit(path):
    with LOCK:
        if sum(j['status'] not in TERMINAL for j in listing())>=8: raise ValueError('Import queue is full (8 tasks maximum)')
        id=uuid.uuid4().hex
        with storage.connect() as c:
            setup(c);c.execute('INSERT INTO import_jobs(id,path,status) VALUES (?,?,?)',(id,path,'queued'))
        POOL.submit(execute,id)
    return get(id)

def execute(id):
    try:
        with LOCK:
            if get(id)['status']=='cancelled': return
            change(id,status='running')
        def checkpoint(processed,total,current):
            if get(id)['status']=='cancelling': raise InterruptedError('Import cancelled')
            change(id,processed=processed,total=total,current_file=current)
        result=scan(get(id)['path'],checkpoint=checkpoint)
        with LOCK:
            if get(id)['status']=='cancelling': raise InterruptedError('Import cancelled')
            change(id,status='committing')
        snapshot_id=storage.save(result['root'],result)
        change(id,status='completed',snapshot_id=snapshot_id,current_file='')
    except InterruptedError:
        change(id,status='cancelled',current_file='')
    except Exception as e:
        change(id,status='failed',error=str(e),current_file='')
