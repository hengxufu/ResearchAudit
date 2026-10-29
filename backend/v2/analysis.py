"""Run-level batch analysis, independent comparisons, correlations and multiplicity."""
import json
import numpy as np
from scipy import stats
from .. import statistics_engine as registry,storage
from ..analysis import compatibility,compare

def batch(refs,group_by,seed=0):
    rows=[];sources=[];seen=set();common=None
    for ref in refs:
        snapshot=storage.get(ref['snapshot_id']);r=next((r for r in snapshot['runs'] if r['id']==ref['run_id']),None)
        if not r:raise ValueError('Unknown run')
        if r['id'] in seen:raise ValueError('Duplicate run identity across selected snapshots')
        seen.add(r['id']);rows.append(r);sources.append({'reference':ref,'evidence':r['sources']})
        common=set(r['metrics']) if common is None else common&set(r['metrics'])
    groups={}
    for row in rows:
        key=json.dumps({k:row['params'].get(k) for k in group_by},sort_keys=True)
        groups.setdefault(key,[]).append(row)
    result={}
    for metric in sorted(common or []):
        gate=compatibility(rows,metric);summaries=[]
        for key,runs in groups.items():
            values=[r['metrics'][metric] for r in runs];finite=[v for v in values if v is not None and np.isfinite(v)]
            seeds=[r['params'].get('seed') for r in runs];independent_seeds=None not in seeds and len(set(map(str,seeds)))==len(seeds)
            summaries.append({'group':json.loads(key),'n_runs':len(runs),'n_finite':len(finite),'mean':float(np.mean(finite)) if finite and gate['status']=='PASS' else None,'sd':float(np.std(finite,ddof=1)) if len(finite)>1 and gate['status']=='PASS' else None,'seed_identity_complete':independent_seeds,'values':values,'run_ids':[r['id'] for r in runs]})
        result[metric]={'compatibility':gate,'groups':summaries}
    return registry.persist({'method':'batch-final-metrics-v1','inputs':{'refs':refs,'group_by':group_by,'seed':seed},'result':result,'sources':sources,'unit':'Run final values; groups descriptive only; independence not certified'})

def independent(left,right,assumptions,seed=0):
    if not assumptions:raise ValueError('Explicit independent run assumption required')
    groups=[];rows=[];sources=[];seen=set();metric=left[0]['metric']
    for refs in (left,right):
        values=[]
        for ref in refs:
            if ref['metric']!=metric:raise ValueError('Metric names differ')
            _,r=registry.source(ref)
            if r['id'] in seen:raise ValueError('Repeated Run ID is not an independent sample')
            seen.add(r['id']);rows.append(r);v=r['metrics'][metric]
            if v is None or not np.isfinite(v):raise ValueError('Finite final results required')
            values.append(v);sources.append({'reference':ref,'evidence':r['sources']})
        if len(values)<3:raise ValueError('At least three runs per group')
        groups.append(np.array(values,dtype=float))
    gate=compatibility(rows,metric)
    if gate['status']!='PASS':raise ValueError('Incompatible or incomplete evaluation contracts')
    a,b=groups;va=a.var(ddof=1);vb=b.var(ddof=1);denom=np.sqrt(va/len(a)+vb/len(b))
    if denom==0:raise ValueError('Degenerate sample variance')
    t,p=stats.ttest_ind(a,b,equal_var=False);df=(va/len(a)+vb/len(b))**2/((va/len(a))**2/(len(a)-1)+(vb/len(b))**2/(len(b)-1));diff=float(a.mean()-b.mean())
    pooled=np.sqrt(((len(a)-1)*va+(len(b)-1)*vb)/(len(a)+len(b)-2));rng=np.random.default_rng(seed)
    boot=[rng.choice(a,len(a),replace=True).mean()-rng.choice(b,len(b),replace=True).mean() for _ in range(2000)]
    return registry.persist({'method':'welch-t-bootstrap-v1','inputs':{'left':left,'right':right,'bootstrap_seed':seed,'resamples':2000},'result':{'mean_difference':diff,'t':float(t),'p_two_sided':float(p),'degrees_freedom':float(df),'ci95':[float(diff-stats.t.ppf(.975,df)*denom),float(diff+stats.t.ppf(.975,df)*denom)],'bootstrap_ci95':np.quantile(boot,[.025,.975]).tolist(),'cohen_d':float(diff/pooled)},'sources':sources,'unit':'Independent Run final values','assumptions':{'independence':'user_declared','distribution':'Approximately normal run-level sampling; not certified'},'warning':'No automatic scientific significance or causal interpretation'})

def holm(ids):
    records=[registry.get(id) for id in ids]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate tests')
    p=np.array([r['result']['p_two_sided'] for r in records],dtype=float)
    order=np.argsort(p);adjusted=np.empty(len(p));adjusted[order]=np.minimum(1,np.maximum.accumulate(p[order]*(len(p)-np.arange(len(p)))))
    return registry.persist({'method':'holm-familywise-v1','inputs':{'analysis_ids':ids},'result':[{'analysis_id':id,'p_raw':float(raw),'p_adjusted':float(adj)} for id,raw,adj in zip(ids,p,adjusted)],'sources':[{'analysis_id':id} for id in ids],'unit':'Explicit user-selected family of tests'})

def correlation(ref,other_metric):
    _,r=registry.source(ref);a=r['series'].get(ref['metric']);b=r['series'].get(other_metric)
    if a is None or b is None or len(a)!=len(b):raise ValueError('Aligned equal-length metric series required')
    pairs=np.array([(x,y) for x,y in zip(a,b) if x is not None and y is not None and np.isfinite(x) and np.isfinite(y)])
    if len(pairs)<3 or np.ptp(pairs[:,0])==0 or np.ptp(pairs[:,1])==0:raise ValueError('Three nonconstant complete pairs required')
    return registry.persist({'method':'spearman-descriptive-v1','inputs':{'reference':ref,'other_metric':other_metric},'result':{'rho':float(stats.spearmanr(pairs[:,0],pairs[:,1]).statistic),'n_pairs':len(pairs),'missing_pairs':len(a)-len(pairs)},'sources':[{'reference':ref,'evidence':r['sources']}],'unit':'Aligned observations; no independent-repeat p-value','warning':'Correlation is not causation; time dependence unmodeled'})

def time_series(ref):
    _,run=registry.source(ref);values=run['series'].get(ref['metric'])
    if not values:raise ValueError('Metric series required')
    steps=run['series'].get(ref['metric']+'/step',list(range(len(values))))
    if len(steps)!=len(values):raise ValueError('Step/value length mismatch')
    pairs=[(x,y) for x,y in zip(steps,values) if x is not None and y is not None and np.isfinite(x) and np.isfinite(y)]
    if len(pairs)<3:raise ValueError('Three complete observations required')
    a=np.array(pairs,dtype=float)
    if np.ptp(a[:,0])==0:raise ValueError('Distinct step coordinates required')
    slope,intercept=np.polyfit(a[:,0],a[:,1],1)
    lag=None
    if len(a)>3 and np.ptp(a[:-1,1])>0 and np.ptp(a[1:,1])>0:lag=float(np.corrcoef(a[:-1,1],a[1:,1])[0,1])
    return registry.persist({'method':'time-trend-descriptive-v1','inputs':ref,'result':{'n_complete':len(pairs),'missing':len(values)-len(pairs),'slope_per_step':float(slope),'intercept':float(intercept),'lag1_correlation':lag,'net_change':float(a[-1,1]-a[0,1])},'sources':[{'reference':ref,'evidence':run['sources']}],'unit':'Within-run observations','warning':'Descriptive trend only; no independent-epoch significance or convergence proof'})

def pareto(refs,metrics):
    rows=[]
    for ref in refs:
        s=storage.get(ref['snapshot_id']);r=next((r for r in s['runs'] if r['id']==ref['run_id']),None)
        if r is None:raise ValueError('Unknown run')
        rows.append(r)
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Repeated run identities')
    gates={m:compatibility(rows,m) for m in metrics}
    if any(g['status']!='PASS' for g in gates.values()):raise ValueError('Complete matching contracts required for every metric')
    values=[]
    for row in rows:
        v=[]
        for metric in metrics:
            direction=row.get('metric_definitions',{}).get(metric,{}).get('direction')
            value=row['metrics'].get(metric)
            if direction not in ('minimize','maximize') or value is None or not np.isfinite(value):raise ValueError('Explicit direction and finite final metric required')
            v.append(value if direction=='minimize' else -value)
        values.append(v)
    a=np.array(values);front=[rows[i]['id'] for i in range(len(rows)) if not any(np.all(a[j]<=a[i]) and np.any(a[j]<a[i]) for j in range(len(rows)) if i!=j)]
    return registry.persist({'method':'pareto-final-metrics-v1','inputs':{'refs':refs,'metrics':metrics},'result':{'nondominated_runs':front,'compatibility':gates},'sources':[{'reference':ref,'evidence':r['sources']} for ref,r in zip(refs,rows)],'unit':'Run final metric vectors','warning':'Pareto optimality under supplied directions, not scientific superiority'})
