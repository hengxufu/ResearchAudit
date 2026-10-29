"""Persisted analysis from source snapshots; experimental unit is explicit."""
import hashlib,json
import numpy as np
from scipy import stats
from . import storage
from .analysis import compatibility

def source(ref):
    s=storage.get(ref['snapshot_id']);r=next((r for r in s['runs'] if r['id']==ref['run_id']),None)
    if not r or ref['metric'] not in r['metrics']:raise ValueError('Unknown source metric')
    return s,r

def persist(payload):
    encoded=json.dumps(payload,sort_keys=True,allow_nan=False);id=hashlib.sha256(encoded.encode()).hexdigest()
    with storage.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,payload TEXT)')
        c.execute('INSERT OR IGNORE INTO analyses VALUES (?,?)',(id,encoded))
    return {'id':id,**payload}

def get(id):
    with storage.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,payload TEXT)');r=c.execute('SELECT payload FROM analyses WHERE id=?',(id,)).fetchone()
    if not r:raise KeyError(id)
    return {'id':id,**json.loads(r[0])}

def describe(ref):
    s,r=source(ref);raw=r['series'].get(ref['metric'],[r['metrics'][ref['metric']]])
    a=np.array([x for x in raw if x is not None and np.isfinite(x)],dtype=float)
    result={'count':len(raw),'finite_count':len(a),'missing_or_nonfinite':len(raw)-len(a)}
    if len(a):
        q1,q3=np.quantile(a,[.25,.75]);iqr=q3-q1
        result.update(mean=float(a.mean()),median=float(np.median(a)),minimum=float(a.min()),maximum=float(a.max()),sample_sd=float(a.std(ddof=1)) if len(a)>1 else None,iqr_outlier_count=int(((a<q1-1.5*iqr)|(a>q3+1.5*iqr)).sum()))
    return persist({'method':'descriptive-v1','unit':'observations within one run; no independent-repeat inference','inputs':ref,'result':result,'sources':r.get('metric_sources',{}).get(ref['metric'],r['sources'])})

def paired(left,right,independent_pairs,normal_differences,seed=0):
    if not independent_pairs or not normal_differences:raise ValueError('Paired t-test requires explicit independent pairs and approximately normal difference assumptions')
    if len(left)!=len(right) or not 3<=len(left)<=1000:raise ValueError('Provide 3..1000 explicitly paired run-level results')
    rows=[];seen=set();values=[];pair_seeds=[];sources=[];metric=left[0]['metric']
    for l,r in zip(left,right):
        pair=[]
        for ref in (l,r):
            if ref['metric']!=metric:raise ValueError('Metric names must agree')
            _,run=source(ref)
            identity=run['id']
            if identity in seen:raise ValueError('A run may occur only once; snapshots are not independent replicates')
            seen.add(identity);rows.append(run)
            value=run['metrics'][metric]
            if value is None or not np.isfinite(value):raise ValueError('Finite final values required')
            pair.append(value);sources.append({'reference':ref,'evidence':run.get('metric_sources',{}).get(metric,run['sources'])})
        if rows[-1]['params'].get('seed') is None or rows[-1]['params'].get('seed')!=rows[-2]['params'].get('seed'):raise ValueError('Each pair must share a recorded seed')
        pair_seeds.append(rows[-1]['params']['seed']);values.append(pair)
    if len(set(map(str,pair_seeds)))!=len(pair_seeds):raise ValueError('Distinct seed per pair required')
    gate=compatibility(rows,metric)
    if gate['status']!='PASS':raise ValueError('Comparison metadata must agree: '+json.dumps(gate))
    a=np.array(values);d=a[:,0]-a[:,1];sd=float(d.std(ddof=1))
    if sd==0:raise ValueError('Constant paired differences: t statistic undefined')
    t,p=stats.ttest_1samp(d,0);se=sd/np.sqrt(len(d));critical=stats.t.ppf(.975,len(d)-1)
    rng=np.random.default_rng(seed);boot=np.array([rng.choice(d,len(d),replace=True).mean() for _ in range(2000)])
    return persist({'method':'paired-t-and-percentile-bootstrap-v1','inputs':{'left':left,'right':right,'bootstrap_seed':seed,'resamples':2000},'unit':'one independent seed-paired run difference','assumptions':{'independent_pairs':True,'normal_differences':True,'basis':'user_declared'},'result':{'n_pairs':len(d),'mean_difference':float(d.mean()),'cohen_dz':float(d.mean()/sd),'t':float(t),'p_two_sided':float(p),'t_ci95':[float(d.mean()-critical*se),float(d.mean()+critical*se)],'bootstrap_ci95':np.quantile(boot,[.025,.975]).tolist()},'sources':sources,'warning':'Single planned comparison; no causal inference; assumptions not certified by this computation'})
