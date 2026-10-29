"""Versioned persistent audit evaluations, separate from immutable input snapshots."""
import json,time,uuid
from pathlib import Path
from .. import storage
from ..analysis import audit
from .assets import digest

def execute(snapshot_id,full_hash=False,bounds=None):
    snapshot=storage.get(snapshot_id);findings=audit(snapshot)
    for e in snapshot['evidence']:
        path=Path(snapshot['root'])/e['path']
        status='FAIL' if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(Path(snapshot['root']).resolve()) else ('PASS' if digest(path)==e['sha256'] else 'FAIL') if full_hash else 'UNKNOWN'
        findings.append({'rule':'source_content','rule_version':'2.0','layer':'integrity','status':status,'condition':'Full current SHA256 comparison' if full_hash else 'Existence only; hash verification not requested','evidence':e,'reason':'Source reference check','suggestion':'Restore original source or import a new snapshot'})
    for bound in bounds or []:
        for r in snapshot['runs']:
            values=r['series'].get(bound['metric'])
            unit=r.get('metric_definitions',{}).get(bound['metric'],{}).get('unit')
            finite=[v for v in values or [] if v is not None]
            if not unit or unit!=bound['unit'] or not finite:status='UNKNOWN'
            elif any(v<bound['minimum'] or v>bound['maximum'] for v in finite):status='FAIL'
            elif len(finite)!=len(values):status='UNKNOWN'
            else:status='PASS'
            findings.append({'rule':'physical_range','rule_version':'1.0','layer':'numerical','status':status,'condition':bound,'evidence':r['sources'],'reason':'Caller-defined physical bounds; unit contract supplied by caller','run':r['name']})
    findings.append({'rule':'execution_reproduction','rule_version':'2.0','layer':'reproducibility','status':'UNKNOWN','condition':'Requires independently rerun experiment','evidence':snapshot['git'],'reason':'Record presence does not establish reproduced result'})
    findings.append({'rule':'evidence_source_links','rule_version':'2.0','layer':'evidence','status':'PASS' if snapshot['evidence'] and all(r.get('metric_sources') for r in snapshot['runs'] if r['metrics']) else 'UNKNOWN','condition':'Imported metric-source mappings present','evidence':[r.get('metric_sources',{}) for r in snapshot['runs']],'reason':'Link presence only, not claim validity'})
    result={'id':uuid.uuid4().hex,'snapshot_id':snapshot_id,'created':time.time(),'configuration':{'full_hash':full_hash,'bounds':bounds or []},'findings':findings}
    with storage.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS audit_runs(id TEXT PRIMARY KEY,snapshot_id INTEGER,created REAL,payload TEXT)');c.execute('INSERT INTO audit_runs VALUES (?,?,?,?)',(result['id'],snapshot_id,result['created'],json.dumps(result)))
    return result

def history(snapshot_id):
    with storage.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS audit_runs(id TEXT PRIMARY KEY,snapshot_id INTEGER,created REAL,payload TEXT)')
        return [json.loads(r[0]) for r in c.execute('SELECT payload FROM audit_runs WHERE snapshot_id=? ORDER BY created DESC',(snapshot_id,))]
