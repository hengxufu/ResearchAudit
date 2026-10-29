"""Small, append-only versioned documents for research configuration and evidence."""
import hashlib,json,time,uuid
from .. import storage

def setup(c):
    c.execute('CREATE TABLE IF NOT EXISTS research_documents(kind TEXT,id TEXT,revision INTEGER,created REAL,payload TEXT,sha256 TEXT,PRIMARY KEY(kind,id,revision))')
    c.execute('CREATE INDEX IF NOT EXISTS document_kind ON research_documents(kind,created)')
    c.execute('CREATE TABLE IF NOT EXISTS workflow_runs(id TEXT PRIMARY KEY,workflow_id TEXT,revision INTEGER,state TEXT,created REAL,finished REAL,payload TEXT)')

def save(kind,payload,id=None,expected_revision=0):
    if any(k in payload for k in ('id','revision','created','sha256')):raise ValueError('Reserved document metadata')
    id=id or uuid.uuid4().hex;encoded=json.dumps(payload,sort_keys=True,allow_nan=False,ensure_ascii=False)
    with storage.connect() as c:
        setup(c);c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT OR IGNORE INTO schema_migrations(version) VALUES (3)')
        current=c.execute('SELECT COALESCE(MAX(revision),0) FROM research_documents WHERE kind=? AND id=?',(kind,id)).fetchone()[0]
        if current!=expected_revision:raise ValueError('Revision conflict')
        revision=current+1;c.execute('INSERT INTO research_documents VALUES (?,?,?,?,?,?)',(kind,id,revision,time.time(),encoded,hashlib.sha256(encoded.encode()).hexdigest()))
    return get(kind,id)

def get(kind,id,revision=None):
    with storage.connect() as c:
        setup(c)
        row=c.execute('SELECT revision,created,payload,sha256 FROM research_documents WHERE kind=? AND id=?'+(' AND revision=?' if revision else '')+' ORDER BY revision DESC LIMIT 1',[kind,id]+([revision] if revision else [])).fetchone()
    if not row:raise KeyError(id)
    return {'id':id,'revision':row[0],'created':row[1],'sha256':row[3],**json.loads(row[2])}

def listing(kind,limit=100,offset=0,query=''):
    with storage.connect() as c:
        setup(c)
        rows=c.execute('SELECT d.id,d.revision,d.created,d.payload,d.sha256 FROM research_documents d WHERE kind=? AND revision=(SELECT MAX(revision) FROM research_documents x WHERE x.kind=d.kind AND x.id=d.id) AND instr(lower(payload),lower(?))>0 ORDER BY created DESC LIMIT ? OFFSET ?',(kind,query,limit,offset)).fetchall()
    return [{'id':r[0],'revision':r[1],'created':r[2],'sha256':r[4],**json.loads(r[3])} for r in rows]

def history(kind,id):
    with storage.connect() as c:setup(c);versions=[r[0] for r in c.execute('SELECT revision FROM research_documents WHERE kind=? AND id=? ORDER BY revision DESC',(kind,id))]
    return [get(kind,id,v) for v in versions]
