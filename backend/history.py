"""Historical experiment curation. Imported facts remain immutable."""
import json
from . import storage

def setup(c):
    c.execute('CREATE TABLE IF NOT EXISTS experiment_revisions(snapshot_id INTEGER, run_id TEXT, revision INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP, payload TEXT NOT NULL, PRIMARY KEY(snapshot_id,run_id,revision))')

def run(snapshot_id,run_id):
    s=storage.get(snapshot_id)
    for r in s['runs']:
        if r.get('id')==run_id: return s,r
    raise KeyError('Run not found')

def revisions(snapshot_id,run_id):
    run(snapshot_id,run_id)
    with storage.connect() as c:
        setup(c)
        return [dict(revision=r[0],created=r[1],**json.loads(r[2])) for r in c.execute('SELECT revision,created,payload FROM experiment_revisions WHERE snapshot_id=? AND run_id=? ORDER BY revision DESC',(snapshot_id,run_id))]

def update(snapshot_id,run_id,payload,expected_revision):
    run(snapshot_id,run_id)
    encoded=json.dumps(payload,allow_nan=False,ensure_ascii=False)
    with storage.connect() as c:
        setup(c);c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT COALESCE(MAX(revision),0) FROM experiment_revisions WHERE snapshot_id=? AND run_id=?',(snapshot_id,run_id)).fetchone()[0]
        if current!=expected_revision: raise ValueError('Revision conflict: reload before saving')
        c.execute('INSERT INTO experiment_revisions(snapshot_id,run_id,revision,payload) VALUES (?,?,?,?)',(snapshot_id,run_id,current+1,encoded))
    return revisions(snapshot_id,run_id)[0]

def records(q='',tag='',status='',limit=100,offset=0):
    storage.ensure_run_index()
    default={'revision':0,'title':'','tags':[],'status':'unreviewed','conditions':[],'variables':[],'notes':''}
    clauses=[];args=[]
    if status:clauses.append("COALESCE(json_extract(a.payload,'$.status'),'unreviewed')=?");args.append(status)
    if tag:clauses.append("EXISTS (SELECT 1 FROM json_each(json_extract(a.payload,'$.tags')) WHERE value=?)");args.append(tag)
    if q:
        clauses.append("instr(lower(r.params || r.metrics || r.name || COALESCE(a.payload,'')),lower(?))>0");args.append(q)
    base="FROM run_index r JOIN snapshots s ON s.id=r.snapshot_id LEFT JOIN experiment_revisions a ON a.snapshot_id=r.snapshot_id AND a.run_id=r.run_id AND a.revision=(SELECT MAX(revision) FROM experiment_revisions x WHERE x.snapshot_id=r.snapshot_id AND x.run_id=r.run_id)"
    where=(' WHERE '+' AND '.join(clauses)) if clauses else ''
    with storage.connect() as c:
        setup(c)
        total=c.execute('SELECT COUNT(*) '+base+where,args).fetchone()[0]
        rows=c.execute('SELECT r.snapshot_id,s.created,s.root,r.run_id,r.name,r.params,r.metrics,a.revision,a.created,a.payload '+base+where+' ORDER BY r.snapshot_id DESC,r.name LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()
    items=[]
    for r in rows:
        annotation={**json.loads(r[9]),'revision':r[7],'created':r[8]} if r[9] else dict(default)
        items.append(dict(snapshot_id=r[0],created=r[1],root=r[2],run_id=r[3],name=r[4],imported_params=json.loads(r[5]),metrics=json.loads(r[6]),annotation=annotation))
    return {'total':total,'items':items}

def history(run_id):
    return [r for r in records(limit=1000000)['items'] if r['run_id']==run_id]
