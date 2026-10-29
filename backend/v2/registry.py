"""Explicit Project/Experiment/Run associations with append-only correction history."""
import json,time,uuid
from .. import storage

def setup(c):
    c.execute('CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,project_id TEXT,label TEXT,created REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS run_associations(id TEXT PRIMARY KEY,snapshot_id INTEGER,run_id TEXT,experiment_id TEXT,created REAL,basis TEXT)')
    c.execute('CREATE INDEX IF NOT EXISTS association_run ON run_associations(snapshot_id,run_id,created)')

def experiments():
    with storage.connect() as c:
        setup(c);return [dict(id=r[0],project_id=r[1],label=r[2],created=r[3]) for r in c.execute('SELECT * FROM experiments ORDER BY created DESC')]

def create(project_id,label):
    id=uuid.uuid4().hex
    with storage.connect() as c:setup(c);c.execute('INSERT INTO experiments VALUES (?,?,?,?)',(id,project_id,label,time.time()))
    return next(e for e in experiments() if e['id']==id)

def associate(snapshot_id,run_id,experiment_id):
    s=storage.get(snapshot_id)
    if not any(r['id']==run_id for r in s['runs']):raise ValueError('Unknown run')
    if not any(e['id']==experiment_id for e in experiments()):raise ValueError('Unknown experiment')
    result=dict(id=uuid.uuid4().hex,snapshot_id=snapshot_id,run_id=run_id,experiment_id=experiment_id,created=time.time(),basis='user_confirmed_association_not_execution_proof')
    with storage.connect() as c:setup(c);c.execute('INSERT INTO run_associations VALUES (?,?,?,?,?,?)',tuple(result[k] for k in ('id','snapshot_id','run_id','experiment_id','created','basis')))
    return result

def associations(snapshot_id):
    with storage.connect() as c:
        setup(c);return [dict(id=r[0],snapshot_id=r[1],run_id=r[2],experiment_id=r[3],created=r[4],basis=r[5]) for r in c.execute('SELECT * FROM run_associations WHERE snapshot_id=? ORDER BY created DESC',(snapshot_id,))]
