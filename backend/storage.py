import sqlite3, os, json, hashlib
from pathlib import Path
DB = Path(os.environ.get("RESEARCHAUDIT_HOME", ".researchaudit"))
def connect():
    DB.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB / "audit.sqlite"))
    c.execute("CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, root TEXT, payload TEXT)")
    if "fingerprint" not in [r[1] for r in c.execute("PRAGMA table_info(snapshots)")]:
        c.execute("ALTER TABLE snapshots ADD COLUMN fingerprint TEXT")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS snapshot_fingerprint ON snapshots(fingerprint)")
    return c
def save(root, payload):
    encoded=json.dumps(payload,allow_nan=False,sort_keys=True)
    fingerprint=hashlib.sha256(encoded.encode()).hexdigest()
    with connect() as c:
        found=c.execute("SELECT id FROM snapshots WHERE fingerprint=?",(fingerprint,)).fetchone()
        if found: return found[0]
        cur = c.execute("INSERT OR IGNORE INTO snapshots(root,payload,fingerprint) VALUES (?,?,?)", (root,encoded,fingerprint))
        row=c.execute("SELECT id FROM snapshots WHERE fingerprint=?",(fingerprint,)).fetchone()
        snapshot_id=row[0]
        write_metrics(snapshot_id,payload)
        return snapshot_id
def get(id):
    with connect() as c:
        row = c.execute("SELECT payload FROM snapshots WHERE id=?", (id,)).fetchone()
    if not row: raise KeyError(id)
    return json.loads(row[0])
def listing():
    with connect() as c:
        return [dict(zip(("id","created","root"),r)) for r in c.execute("SELECT id,created,root FROM snapshots ORDER BY id DESC")]


def save_figure(snapshot_id,spec):
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS figures(snapshot_id INTEGER, evidence_id TEXT, spec TEXT, PRIMARY KEY(snapshot_id,evidence_id))")
        c.execute("INSERT OR IGNORE INTO figures VALUES (?,?,?)",(snapshot_id,spec['id'],json.dumps(spec)))
def figures(snapshot_id):
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS figures(snapshot_id INTEGER, evidence_id TEXT, spec TEXT, PRIMARY KEY(snapshot_id,evidence_id))")
        return [json.loads(r[0]) for r in c.execute("SELECT spec FROM figures WHERE snapshot_id=?",(snapshot_id,))]


def write_metrics(snapshot_id,payload):
    import polars as pl
    import uuid
    rows=[{'run_id':r['id'],'metric':m,'observation':i,'value':v} for r in payload['runs'] for m,values in r['series'].items() for i,v in enumerate(values)]
    frame=pl.DataFrame(rows,schema={'run_id':pl.String,'metric':pl.String,'observation':pl.Int64,'value':pl.Float64})
    folder=DB/'metrics';folder.mkdir(exist_ok=True)
    target=folder/(str(snapshot_id)+'.parquet')
    frame.write_parquet(target)

def query_metrics(snapshot_id,metric,run_id=None,limit=10000,offset=0):
    import duckdb
    path=DB/'metrics'/(str(snapshot_id)+'.parquet')
    if not path.exists(): write_metrics(snapshot_id,get(snapshot_id))
    with duckdb.connect() as c:
        query="SELECT run_id,metric,observation,value FROM read_parquet(?) WHERE metric=?"
        args=[str(path),metric]
        if run_id: query+=' AND run_id=?';args.append(run_id)
        query+=' ORDER BY run_id,observation LIMIT ? OFFSET ?';args.extend([limit,offset])
        return [dict(zip(('run_id','metric','observation','value'),r)) for r in c.execute(query,args).fetchall()]
