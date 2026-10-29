"""Versioned Claim–Evidence records. Evidence existence is not claim validation."""
from . import documents
from .. import storage,statistics_engine

def validate_reference(ref):
    if ref['kind']=='snapshot':
        s=storage.get(int(ref['id']))
        if ref.get('run_id') and not any(r['id']==ref['run_id'] for r in s['runs']):raise ValueError('Unknown evidence run')
    elif ref['kind']=='analysis':statistics_engine.get(ref['id'])
    elif ref['kind']=='figure':
        if not any(f['id']==ref['id'] for f in storage.figures(ref['snapshot_id'])):raise ValueError('Unknown figure evidence')
    elif ref['kind']=='knowledge':documents.get('knowledge',ref['id'],ref.get('revision'))
    else:raise ValueError('Unsupported evidence kind')

def save(payload,id=None,revision=0):
    for ref in payload.get('supporting',[])+payload.get('conflicting',[]):
        validate_reference(ref)
        if ref['kind']=='knowledge' and ref.get('revision') is None:ref['revision']=documents.get('knowledge',ref['id'])['revision']
    if payload.get('validation_status')=='reviewed' and (not payload.get('review_reason') or not payload.get('supporting')):raise ValueError('Human-reviewed claim requires supporting references and review reason')
    return documents.save('knowledge',payload,id,revision)
