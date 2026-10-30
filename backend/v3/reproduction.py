"""Explicit historical reruns and dimension-separated verification."""
import hashlib,json,math,threading,shutil
from pathlib import Path
import numpy as np
from scipy import stats
from ..core import documents
from .. import storage
from ..v2 import assets
launch_lock=threading.RLock()

def metrics(snapshot_id):
    s=storage.get(snapshot_id)
    return {r['name']:{'metrics':r['metrics'],'definitions':r.get('metric_definitions',{}),'params':r['params'],'sources':r['sources']} for r in s['runs']}

def create(engine,source_execution,input_versions,tolerances):
    run=engine.get(source_execution)
    if run['state']!='Succeeded' or not run['snapshot_id']:raise ValueError('A successful source execution with result snapshot is required')
    original=storage.get(run['snapshot_id']);context=next((r.get('execution',{}).get('environment_manifest') for r in original['runs'] if r.get('execution')),None)
    for version in input_versions:assets.version(version)
    return documents.save('reproduction',{'source_execution':source_execution,'source_snapshot':run['snapshot_id'],'spec':run['spec'],'environment':context,'input_versions':input_versions,'tolerances':tolerances,'execution':None,'status':'Draft','scope':'Replay in current local environment; no automatic checkout, dependency install or scientific correctness claim'})

def launch(engine,id,confirmed,allow_code_change=False):
    with launch_lock:return _launch(engine,id,confirmed,allow_code_change)

def _launch(engine,id,confirmed,allow_code_change):
    record=documents.get('reproduction',id)
    if not confirmed:raise ValueError('Explicit execution confirmation required')
    if record['execution']:
        if record['status']!='Prepared' or engine.get(record['execution'])['state']!='Pending':raise ValueError('This manifest already has a replay; create a new manifest to repeat')
    context=record['environment']
    if context and not allow_code_change:
        from ..collect import git
        current=git(record['spec']['cwd'],'rev-parse','HEAD')
        if context['git']['commit'] and current!=context['git']['commit']:raise ValueError('Git commit differs; explicit code-change override required')
        for entry in context['entry_code']:
            path=(Path(record['spec']['cwd'])/entry['path']).resolve()
            if not path.is_file() or assets.digest(path)!=entry['sha256']:raise ValueError('Recorded entry source changed; code-change override required')
        executable=context.get('target_executable',{})
        if executable.get('sha256'):
            current=Path(record['spec']['argv'][0])
            if not current.is_absolute():current=Path(record['spec']['cwd'])/current if (Path(record['spec']['cwd'])/current).is_file() else Path(shutil.which(str(current)) or str(current))
            if not current.is_file() or str(current.resolve())!=executable['resolved'] or assets.digest(current)!=executable['sha256']:raise ValueError('Target executable changed; code-change override required')
    for version in record['input_versions']:
        if assets.verify(version)['status']=='FAIL':raise ValueError('Input asset verification failed')
    if record['execution']:
        engine.enqueue(record['execution'])
        payload={k:v for k,v in record.items() if k not in ('id','revision','created','sha256')};payload['status']='Started'
        return documents.save('reproduction',payload,id,record['revision'])
    spec={**record['spec'],'dependencies':[]};run=engine.create(spec)
    payload={k:v for k,v in record.items() if k not in ('id','revision','created','sha256')};payload.update(execution=run['id'],status='Prepared',code_change_override=allow_code_change)
    prepared=documents.save('reproduction',payload,id,record['revision'])
    engine.enqueue(run['id']);payload['status']='Started'
    return documents.save('reproduction',payload,id,prepared['revision'])

def evaluate(engine,id):
    record=documents.get('reproduction',id);run=engine.get(record['execution']) if record['execution'] else None
    comparisons=[];consistency='UNKNOWN'
    if run and run['state']=='Succeeded' and run['snapshot_id']:
        left=metrics(record['source_snapshot']);right=metrics(run['snapshot_id'])
        for name,original in left.items():
            for metric,value in original['metrics'].items():
                actual=right.get(name,{}).get('metrics',{}).get(metric);tol=record['tolerances'].get(metric)
                result={'run':name,'metric':metric,'original':value,'replayed':actual,'status':'UNKNOWN','sources':original['sources'],'replay_sources':right.get(name,{}).get('sources',[])}
                definition=original['definitions'].get(metric,{})
                compatible=definition==right.get(name,{}).get('definitions',{}).get(metric,{}) and all(k in definition for k in ('unit','method','direction'))
                fields=('dataset','dataset_version','split','evaluation_protocol')
                compatible=compatible and all(original['params'].get(k) is not None and original['params'].get(k)==right.get(name,{}).get('params',{}).get(k) for k in fields)
                result['definition_status']='PASS' if compatible else 'UNKNOWN'
                if value is not None and actual is not None and math.isfinite(value) and math.isfinite(actual) and tol and compatible:
                    error=abs(actual-value);bound=tol['atol']+tol['rtol']*abs(value)
                    result.update(absolute_error=error,relative_error=error/abs(value) if value!=0 else None,tolerance=bound,status='PASS' if error<=bound else 'FAIL')
                comparisons.append(result)
        consistency='FAIL' if any(c['status']=='FAIL' for c in comparisons) else 'PASS' if comparisons and all(c['status']=='PASS' for c in comparisons) else 'UNKNOWN'
    availability=[assets.verify(v)['status'] for v in record['input_versions']]
    scorecard={'environment_completeness':{'status':'UNKNOWN','reason':'Selected runner environment recorded; target closure not certified'},'data_availability':{'status':'FAIL' if 'FAIL' in availability else 'PASS' if availability and all(s=='PASS' for s in availability) else 'UNKNOWN','evidence':availability},'execution_success':{'status':'PASS' if run and run['state']=='Succeeded' else 'FAIL' if run and run['state'] in ('Failed','Cancelled','Interrupted') else 'UNKNOWN','state':run['state'] if run else 'Not started'},'result_consistency':{'status':consistency,'method':'abs(replay-original) <= atol + rtol*abs(original)'},'evidence_completeness':{'status':'PASS' if comparisons and all(c['sources'] and c['replay_sources'] for c in comparisons) else 'UNKNOWN','scope':'Comparison source links only'}}
    result={'manifest_id':id,'manifest_revision':record['revision'],'source_snapshot':record['source_snapshot'],'replay_snapshot':run['snapshot_id'] if run else None,'comparisons':comparisons,'scorecard':scorecard,'scientific_correctness':'UNKNOWN'}
    return documents.save('reproduction_report',result)

def distributions(left_refs,right_refs,independent,seed=0):
    if not independent:raise ValueError('Independent run-level samples must be explicitly declared')
    from ..statistics_engine import source,persist
    from ..analysis import compatibility
    rows=[];ids=set();groups=[];evidence=[]
    for refs in (left_refs,right_refs):
        values=[]
        for ref in refs:
            _,r=source(ref)
            if r['id'] in ids:raise ValueError('Repeated Run identity is not an independent replicate')
            ids.add(r['id']);rows.append(r);v=r['metrics'][ref['metric']]
            if v is None or not math.isfinite(v):raise ValueError('Finite run-level metrics required')
            values.append(v);evidence.append({'reference':ref,'evidence':r['sources']})
        if len(values)<3:raise ValueError('At least three runs per group')
        groups.append(np.array(values))
    metric=left_refs[0]['metric']
    if any(r['metric']!=metric for r in left_refs+right_refs) or compatibility(rows,metric)['status']!='PASS':raise ValueError('Compatible metric definitions required')
    a,b=groups;test=stats.ks_2samp(a,b);rng=np.random.default_rng(seed);differences=[rng.choice(b,len(b),True).mean()-rng.choice(a,len(a),True).mean() for _ in range(2000)]
    return persist({'method':'run-distribution-reproduction-v1','inputs':{'left':left_refs,'right':right_refs,'seed':seed,'resamples':2000},'result':{'ks_statistic':float(test.statistic),'p_two_sided':float(test.pvalue),'wasserstein_distance':float(stats.wasserstein_distance(a,b)),'mean_difference_ci95':np.quantile(differences,[.025,.975]).tolist()},'sources':evidence,'unit':'Independent Run final values, caller-declared','status':'UNKNOWN','warning':'Non-rejection is not proof of distributional equivalence; no equivalence margin specified'})
