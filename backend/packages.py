"""Reference-only evidence package: bounded outputs, no automatic raw data copying."""
import hashlib,json,io,zipfile,html
from . import storage,evidence
from .reports import render

def bundle(id):
    snapshot=storage.get(id)
    nodes=evidence.listing();selected={n['id'] for n in nodes if any(ref.get('snapshot_id')==id for ref in n['sources'])}
    changed=True
    while changed:
        before=len(selected)
        for node in nodes:
            refs={ref['evidence_id'] for ref in node['sources'] if 'evidence_id' in ref}
            if node['id'] in selected:selected.update(refs)
            if refs & selected:selected.add(node['id'])
        changed=len(selected)!=before
    files={'snapshot.json':json.dumps(snapshot,ensure_ascii=False,indent=2).encode(),'report.md':render(snapshot,id,storage.figures(id)).encode(),'evidence.json':json.dumps([n for n in nodes if n['id'] in selected],ensure_ascii=False,indent=2).encode()}
        
    analyses=[]
    with storage.connect() as c:
        if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analyses'").fetchone():
            for row in c.execute('SELECT id,payload FROM analyses'):
                payload=json.loads(row[1]);refs=payload.get('sources',[])
                if payload.get('inputs',{}).get('snapshot_id')==id or any(isinstance(ref,dict) and ref.get('reference',{}).get('snapshot_id')==id for ref in refs):analyses.append({'id':row[0],**payload})
    files['analyses.json']=json.dumps(analyses,ensure_ascii=False,indent=2).encode()
    from . import history
    files['curation.json']=json.dumps({r['id']:history.revisions(id,r['id']) for r in snapshot['runs']},ensure_ascii=False,indent=2).encode()
    files['figures.json']=json.dumps(storage.figures(id),ensure_ascii=False,indent=2).encode()
    files['replot.py']="""import json
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
s=json.load(open('snapshot.json',encoding='utf-8'))
for spec in json.load(open('figures.json',encoding='utf-8')):
    fig=Figure(figsize=(7.2,4.5),layout='constrained');FigureCanvasAgg(fig);ax=fig.subplots()
    for r in s['runs']:
        metric=spec['metric']
        if metric not in r['series']:continue
        y=np.array([np.nan if v is None else v for v in r['series'][metric]])
        if spec['kind']=='curve':ax.plot(r['series'].get(metric+'/step',range(len(y))),y,label=r['name'])
        elif np.isfinite(y).any():ax.hist(y[np.isfinite(y)],bins='auto',alpha=.45,label=r['name'])
    ax.legend();ax.set_title(spec['metric']+' | '+spec['kind']);ax.set_xlabel('Observation / step' if spec['kind']=='curve' else spec['metric']);ax.set_ylabel(spec['metric'] if spec['kind']=='curve' else 'Count');fig.savefig(spec['id']+'.png',dpi=300)
""".encode()
    files['README.txt']=b'Original datasets and weights are referenced by snapshot hashes and paths, not embedded. This package does not prove scientific correctness.'
    manifest={name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in files.items()}
    files['manifest.json']=json.dumps(manifest,indent=2).encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    return buffer.getvalue()
