"""Local metadata exchange. Never downloads DVC remotes or executes MLflow models."""
import json
from pathlib import Path
import yaml
from .. import storage

def inspect(format,path):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>10*1024*1024:raise ValueError('Existing metadata file <=10 MiB required')
    value=yaml.safe_load(p.read_text(encoding='utf-8')) if format=='dvc' else json.loads(p.read_text(encoding='utf-8'))
    if format=='dvc':
        if not isinstance(value,dict) or not isinstance(value.get('outs'),list):raise ValueError('Expected DVC outs list')
        return {'format':'dvc-metadata','raw':value,'outputs':value['outs'],'status':'UNKNOWN','scope':'Declared DVC hashes preserved in their original algorithm; no remote fetch or content verification'}
    if not isinstance(value,dict) or not isinstance(value.get('@graph'),list):raise ValueError('Expected RO-Crate JSON-LD @graph')
    nodes=value['@graph'];ids={n.get('@id') for n in nodes}
    if 'ro-crate-metadata.json' not in ids or './' not in ids:raise ValueError('Missing crate descriptor or root Dataset')
    return {'format':'ro-crate-metadata','raw':value,'entities':len(nodes),'status':'UNKNOWN','scope':'Structural intake only; no JSON-LD expansion, profile certification or fetching'}

def crate(snapshot_id):
    s=storage.get(snapshot_id);root=Path(s['root']);files=[]
    for e in s['evidence']:
        files.append({'@id':(root/e['path']).resolve().as_uri(),'@type':'File','name':e['path'],'contentSize':str(e['bytes']),'description':'Imported SHA256: '+e['sha256']})
    return {'@context':'https://w3id.org/ro/crate/1.1/context','@graph':[{'@id':'ro-crate-metadata.json','@type':'CreativeWork','about':{'@id':'./'},'conformsTo':{'@id':'https://w3id.org/ro/crate/1.1'}},{'@id':'./','@type':'Dataset','name':'ResearchAudit snapshot '+str(snapshot_id),'description':'Local reference-only metadata. External files are not bundled. Licenses and scientific claims are not verified.','hasPart':[{'@id':f['@id']} for f in files]}]+files}
