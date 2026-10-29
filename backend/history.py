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
    results=[]
    for item in storage.listing():
        s=storage.get(item['id'])
        for r in s['runs']:
            history=revisions(item['id'],r['id']);annotation=history[0] if history else {'revision':0,'title':'','tags':[],'status':'unreviewed','conditions':[],'variables':[],'notes':''}
            record={'snapshot_id':item['id'],'created':item['created'],'root':item['root'],'run_id':r['id'],'name':r['name'],'imported_params':r['params'],'metrics':r['metrics'],'annotation':annotation}
            if tag and tag not in annotation['tags']: continue
            if status and status!=annotation['status']: continue
            if q.casefold() not in json.dumps(record,ensure_ascii=False).casefold(): continue
            results.append(record)
    return {'total':len(results),'items':results[offset:offset+limit]}

def history(run_id):
    return [r for r in records(limit=1000000)['items'] if r['run_id']==run_id]
