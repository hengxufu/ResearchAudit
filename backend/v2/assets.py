"""Reference-only immutable dataset/model versions and independent integrity checks."""
import hashlib,json,os,time,uuid
from pathlib import Path
from .. import storage

def setup(c):
    c.executescript('CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,label TEXT,kind TEXT,root TEXT,created REAL); CREATE TABLE IF NOT EXISTS asset_versions(id TEXT PRIMARY KEY,asset_id TEXT,created REAL,manifest TEXT); CREATE INDEX IF NOT EXISTS versions_asset ON asset_versions(asset_id,created); CREATE TABLE IF NOT EXISTS asset_checks(id TEXT PRIMARY KEY,version_id TEXT,created REAL,payload TEXT);')

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def register(label,kind,root):
    root=Path(root).resolve()
    if not root.exists():raise ValueError('Asset path does not exist')
    id=uuid.uuid4().hex
    with storage.connect() as c:
        setup(c);c.execute('INSERT INTO assets VALUES (?,?,?,?,?)',(id,label,kind,str(root),time.time()))
    return {'id':id,'label':label,'kind':kind,'root':str(root)}

def listing():
    with storage.connect() as c:
        setup(c);c.row_factory=__import__('sqlite3').Row
        return [dict(r) for r in c.execute('SELECT * FROM assets ORDER BY created DESC')]

def asset(id):
    found=next((a for a in listing() if a['id']==id),None)
    if not found:raise KeyError(id)
    return found

def capture(id,hash_content=False):
    a=asset(id);root=Path(a['root']);paths=[]
    if root.is_file():paths=[root]
    else:
        for directory,dirs,names in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if d not in ('.git','.venv','node_modules','.researchaudit') and not (Path(directory)/d).is_symlink()]
            paths.extend(Path(directory)/n for n in names)
    manifest=[]
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():continue
        before=path.stat();entry={'path':path.name if root.is_file() else path.relative_to(root).as_posix(),'bytes':before.st_size,'mtime_ns':before.st_mtime_ns,'sha256':digest(path) if hash_content else None}
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Asset changed during capture')
        manifest.append(entry)
    encoded=json.dumps(manifest,sort_keys=True);vid=hashlib.sha256((id+encoded).encode()).hexdigest()
    with storage.connect() as c:setup(c);c.execute('INSERT OR IGNORE INTO asset_versions VALUES (?,?,?,?)',(vid,id,time.time(),encoded))
    return {'id':vid,'asset_id':id,'manifest':manifest,'hash_mode':'full' if hash_content else 'metadata_only'}

def versions(id):
    asset(id)
    with storage.connect() as c:
        setup(c)
        return [{'id':r[0],'created':r[1],'manifest':json.loads(r[2])} for r in c.execute('SELECT id,created,manifest FROM asset_versions WHERE asset_id=? ORDER BY created DESC',(id,))]

def version(id):
    with storage.connect() as c:setup(c);r=c.execute('SELECT asset_id,manifest FROM asset_versions WHERE id=?',(id,)).fetchone()
    if not r:raise KeyError(id)
    return asset(r[0]),json.loads(r[1])

def verify(id):
    a,manifest=version(id);root=Path(a['root']);findings=[]
    for entry in manifest:
        p=root if root.is_file() else root/entry['path']
        if not p.is_file():status='FAIL';reason='missing reference'
        elif entry['sha256']:
            status='PASS' if digest(p)==entry['sha256'] else 'FAIL';reason='SHA256 comparison'
        else:
            status='WARN' if p.stat().st_size!=entry['bytes'] or p.stat().st_mtime_ns!=entry['mtime_ns'] else 'UNKNOWN';reason='No baseline content hash; metadata only'
        findings.append({'path':entry['path'],'status':status,'reason':reason})
    result={'id':uuid.uuid4().hex,'version_id':id,'findings':findings,'status':'FAIL' if any(f['status']=='FAIL' for f in findings) else 'UNKNOWN' if not findings or any(f['status']!='PASS' for f in findings) else 'PASS'}
    with storage.connect() as c:setup(c);c.execute('INSERT INTO asset_checks VALUES (?,?,?,?)',(result['id'],id,time.time(),json.dumps(result)))
    return result

def compare(left,right):
    _,a=version(left);_,b=version(right);a={e['path']:e for e in a};b={e['path']:e for e in b}
    return {'left':left,'right':right,'added':sorted(b.keys()-a.keys()),'removed':sorted(a.keys()-b.keys()),'changed':sorted(k for k in a.keys()&b.keys() if (a[k]['sha256']!=b[k]['sha256'] if a[k]['sha256'] and b[k]['sha256'] else (a[k]['bytes'],a[k]['mtime_ns'])!=(b[k]['bytes'],b[k]['mtime_ns']))),'metadata_changed':sorted(k for k in a.keys()&b.keys() if (a[k]['bytes'],a[k]['mtime_ns'])!=(b[k]['bytes'],b[k]['mtime_ns'])),'method':'Path + SHA256 where present, otherwise size/mtime; metadata is not content equivalence'}
