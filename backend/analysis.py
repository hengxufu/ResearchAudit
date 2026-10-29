import json, hashlib, math
from collections import defaultdict
import numpy as np

def compatibility(runs, metric):
    fields = ('dataset','dataset_version','split','evaluation_protocol')
    missing = [r['name']+':'+f for r in runs for f in fields if r['params'].get(f) is None]
    definitions = [r.get('metric_definitions',{}).get(metric,{}) for r in runs]
    for r,d in zip(runs,definitions):
        missing += [r['name']+':metric.'+k for k in ('direction','unit','method') if d.get(k) is None]
    differences = [f for f in fields if len({json.dumps(r['params'].get(f),sort_keys=True) for r in runs if r['params'].get(f) is not None})>1]
    if any(len({json.dumps(d[k],sort_keys=True) for d in definitions if k in d})>1 for k in ('direction','unit','method')): differences.append('metric_definition')
    return {'status':'FAIL' if differences else 'UNKNOWN' if missing or not runs else 'PASS','missing':missing,'differences':differences,'scope':'Declared metadata agreement only; not scientific correctness'}

def compare(snapshot, metric, filters=None):
    runs=[r for r in snapshot['runs'] if metric in r['metrics'] and all(str(r['params'].get(k))==str(v) for k,v in (filters or {}).items())]
    gate=compatibility(runs,metric)
    values=[]
    for r in runs:
        seq=r['series'].get(metric,[r['metrics'][metric]])
        finite=[v for v in seq if v is not None]
        d=r.get('metric_definitions',{}).get(metric,{})
        direction=d.get('direction')
        values.append({'run':r['name'],'run_id':r.get('id'),'value':seq[-1] if seq else None,'last_finite':finite[-1] if finite else None,'best':(min(finite) if direction=='minimize' else max(finite)) if finite and direction in ('minimize','maximize') else None,'definition':d,'sources':r.get('metric_sources',{}).get(metric,[])})
    groups=defaultdict(list)
    for r,v in zip(runs,values):
        key=json.dumps({k:x for k,x in r['params'].items() if k!='seed'},sort_keys=True)
        groups[key].append((r,v))
    summaries=[]
    for key,items in groups.items():
        seeds=[r['params'].get('seed') for r,v in items]
        valid=gate['status']=='PASS' and None not in seeds and len(set(map(str,seeds)))==len(seeds) and all(v['value'] is not None for r,v in items)
        a=np.array([v['value'] for r,v in items if v['value'] is not None],dtype=float)
        summaries.append({'parameters':json.loads(key),'seeds':seeds,'n':len(items),'status':'PASS' if valid else 'UNKNOWN','mean':float(a.mean()) if valid and len(a) else None,'std':float(a.std(ddof=1)) if valid and len(a)>1 else None,'method':'Arithmetic mean and sample standard deviation (ddof=1); independence not established'})
    return {'metric':metric,'values':values,'n':len(values),'compatibility':gate,'seed_groups':summaries,'mean':None,'std':None}

RULES=[]
def rule(name):
    def decorate(fn): RULES.append((name,fn)); return fn
    return decorate
@rule('run_integrity')
def integrity(s):
    for r in s['runs']:
        checks=[('configuration','PASS' if r.get('config_sources') else 'WARN','Provide a config.json or config.yaml'),('seed','PASS' if r['params'].get('seed') is not None else 'UNKNOWN','Record random seed'),('metrics','PASS' if r['metrics'] else 'FAIL','Provide numeric metrics'),('finite_values','FAIL' if any(None in v for v in r['series'].values()) else 'PASS','Inspect missing/NaN/Inf observations'),('series_lengths','FAIL' if len({len(v) for k,v in r['series'].items() if not k.endswith('/step')})>1 else 'PASS','Check metric alignment')]
        for check,status,advice in checks: yield {'rule':check,'status':status,'run':r['name'],'message':check+': '+status,'reason':check+': '+status,'suggestion':advice,'evidence':r['sources']}
@rule('version')
def version(s):
    yield {'rule':'git_version','status':'UNKNOWN' if not s['git']['commit'] else 'WARN' if s['git']['status'] else 'PASS','message':'Git state at collection time; original execution version unverified','reason':'Post-hoc collection cannot establish execution version','suggestion':'Record execution commit and archive dirty diff','evidence':s['git']}
@rule('comparability')
def comparability(s):
    for m in sorted({m for r in s['runs'] for m in r['metrics']}):
        gate=compatibility([r for r in s['runs'] if m in r['metrics']],m)
        yield {'rule':'comparability','status':gate['status'],'message':m+': '+gate['status'],'reason':gate,'suggestion':'Record dataset version, split, protocol and metric direction/unit/method','evidence':[{'run':r['name'],'params':r['params'],'definition':r.get('metric_definitions',{}).get(m)} for r in s['runs'] if m in r['metrics']]}
def audit(s):
    results=[item for name,fn in RULES for item in fn(s)]
    results += [dict(rule='import',status='FAIL',reason=i['message'],suggestion='Inspect source file',**i) for i in s['issues']]
    results.append({'rule':'reproduction','status':'UNKNOWN','message':'Reproduction and scientific correctness have not been executed','reason':'Static evidence only','suggestion':'Re-run with pinned environment','evidence':[]})
    return results
