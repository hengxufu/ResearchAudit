"""Append-only research evidence links, including multi-level claims."""
import uuid,json
from . import storage

def setup(c):
    c.execute('CREATE TABLE IF NOT EXISTS research_evidence(id TEXT PRIMARY KEY,kind TEXT,label TEXT,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP)')

def listing():
    with storage.connect() as c:
        setup(c)
        return [dict(id=r[0],kind=r[1],label=r[2],**json.loads(r[3])) for r in c.execute('SELECT id,kind,label,payload FROM research_evidence ORDER BY created,rowid')]

def add(kind,label,sources):
    existing={e['id'] for e in listing()}
    for source in sources:
        if 'evidence_id' in source:
            if source['evidence_id'] not in existing: raise ValueError('Unknown evidence reference')
        else:
            snapshot=storage.get(source['snapshot_id'])
            run=next((r for r in snapshot['runs'] if r['id']==source['run_id']),None)
            if not run: raise ValueError('Unknown run')
            if source.get('metric') and source['metric'] not in run['metrics']: raise ValueError('Unknown metric')
    id=uuid.uuid4().hex
    with storage.connect() as c:
        setup(c);c.execute('INSERT INTO research_evidence(id,kind,label,payload) VALUES (?,?,?,?)',(id,kind,label,json.dumps({'sources':sources,'basis':'user_declared'})))
    return next(e for e in listing() if e['id']==id)

def trace(id):
    records={r['id']:r for r in listing()}
    if id not in records: raise KeyError(id)
    found={}
    def visit(key):
        if key in found:return
        node=records[key];found[key]=node
        for source in node['sources']:
            if 'evidence_id' in source:visit(source['evidence_id'])
    visit(id)
    return list(found.values())
