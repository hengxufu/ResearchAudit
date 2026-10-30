"""Versioned methods; independent units and repeated blocks are explicit."""
import json
import numpy as np
from .. import storage,statistics_engine as registry
from ..analysis import compatibility

METHODS={
 'stratified-bootstrap-v1':{'unit':'One independent Run final metric within each declared stratum','assumptions':['independent runs within stratum'],'algorithm':'Percentile bootstrap of arithmetic mean; no pooling across strata'},
 'repeated-block-bootstrap-v1':{'unit':'One matched seed/block difference between two conditions','assumptions':['blocks independent','conditions matched within seed'],'algorithm':'Resample whole paired differences, never epochs'},
}
def analyze(refs,metric,group_by,paired,independent,seed,resamples):
    if not independent:raise ValueError('Explicit independence declaration required')
    rows=[];sources=[];seen=set()
    for ref in refs:
        _,r=registry.source({**ref,'metric':metric})
        if r['id'] in seen:raise ValueError('Duplicate Run identity')
        seen.add(r['id']);rows.append(r);sources.append({'reference':ref,'evidence':r['sources']})
        if r['metrics'][metric] is None or not np.isfinite(r['metrics'][metric]):raise ValueError('Finite final values required')
        if any(r['params'].get(k) is None for k in group_by):raise ValueError('Stratum/condition values must be recorded')
    rng=np.random.default_rng(seed);groups={}
    for r in rows:groups.setdefault(json.dumps({k:r['params'][k] for k in group_by},sort_keys=True),[]).append(r)
    result=[]
    if paired:
        if len(groups)!=2 or compatibility(rows,metric)['status']!='PASS':raise ValueError('Two comparable conditions required')
        blocks=[]
        for group in groups.values():
            seeds=[r['params'].get('seed') for r in group]
            if None in seeds or len(set(map(str,seeds)))!=len(seeds):raise ValueError('One Run per seed per condition required')
            blocks.append({str(r['params']['seed']):r['metrics'][metric] for r in group})
        if blocks[0].keys()!=blocks[1].keys() or len(blocks[0])<3:raise ValueError('At least three complete matched seeds required')
        values=np.array([blocks[1][k]-blocks[0][k] for k in sorted(blocks[0])]);boot=np.array([rng.choice(values,len(values),replace=True).mean() for _ in range(resamples)])
        result={'conditions':list(groups),'n_blocks':len(values),'mean_difference_second_minus_first':float(values.mean()),'ci95':np.quantile(boot,[.025,.975]).tolist(),'block_differences':values.tolist()}
    else:
        for label,group in groups.items():
            if len(group)<3 or compatibility(group,metric)['status']!='PASS':raise ValueError('Each stratum requires >=3 compatible runs')
            values=np.array([r['metrics'][metric] for r in group]);boot=np.array([rng.choice(values,len(values),replace=True).mean() for _ in range(resamples)])
            result.append({'stratum':json.loads(label),'n':len(values),'mean':float(values.mean()),'sd':float(values.std(ddof=1)),'ci95':np.quantile(boot,[.025,.975]).tolist(),'run_ids':[r['id'] for r in group]})
    method='repeated-block-bootstrap-v1' if paired else 'stratified-bootstrap-v1'
    return registry.persist({'method':method,'method_version':'1','definition':METHODS[method],'inputs':{'refs':refs,'metric':metric,'group_by':group_by,'seed':seed,'resamples':resamples,'independence':'caller_declared'},'result':result,'sources':sources,'unit':METHODS[method]['unit'],'warning':'Percentile interval and caller assumptions; no causal or equivalence certification'})
