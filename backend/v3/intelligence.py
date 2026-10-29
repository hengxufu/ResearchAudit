"""Local, inspectable rules and finite natural-language query grammar. No AI service."""
import math,re
import numpy as np
from .. import storage,statistics_engine
from ..analysis import compatibility

def diagnose(snapshot_id,loss_metric='loss',validation_metric=None,window=5,relative_threshold=.1):
    s=storage.get(snapshot_id);findings=[]
    for r in s['runs']:
        def add(rule,status,reason,values=None):findings.append({'rule':rule,'version':'1','status':status,'reason':reason,'inputs':{'run_id':r['id'],'metric':loss_metric,'window':window,'relative_threshold':relative_threshold},'observations':values,'evidence':r['sources'],'confidence_condition':'Descriptive heuristic; training dynamics and experimental conditions require researcher review'})
        missing=[k for k in ('seed','evaluation_protocol','dataset_version') if r['params'].get(k) is None]
        add('metadata','WARN' if missing else 'PASS',{'missing':missing})
        if r.get('metric_definitions',{}).get(loss_metric,{}).get('direction')!='minimize':
            add('training_trend','UNKNOWN','Training-loss rules require an explicitly minimizing metric definition');continue
        raw=r.get('series',{}).get(loss_metric,[])
        if len(raw)<2*window or any(v is None or not math.isfinite(v) for v in raw):
            add('training_trend','UNKNOWN','Need at least two complete finite windows');continue
        a=np.asarray(raw);early=float(np.mean(a[-2*window:-window]));late=float(np.mean(a[-window:]));scale=max(abs(early),1e-12);change=(late-early)/scale
        add('loss_divergence','WARN' if change>relative_threshold else 'PASS','Recent mean loss increased beyond declared relative threshold' if change>relative_threshold else 'No threshold trigger',{'previous_mean':early,'recent_mean':late,'relative_change':change})
        add('loss_plateau','WARN' if abs(change)<relative_threshold else 'PASS','Relative mean change below threshold' if abs(change)<relative_threshold else 'No threshold trigger',{'relative_change':change})
        volatility=float(np.std(np.diff(a[-window:]))/max(abs(late),1e-12));add('loss_volatility','WARN' if volatility>relative_threshold else 'PASS','Std of successive differences / abs(recent mean)',{'relative_volatility':volatility})
        if validation_metric:
            if r.get('metric_definitions',{}).get(validation_metric,{}).get('direction')!='minimize':
                add('overfit_hint','UNKNOWN','Validation trend requires an explicitly minimizing validation loss');continue
            v=r.get('series',{}).get(validation_metric,[])
            if len(v)!=len(raw) or any(x is None for x in v):add('overfit_hint','UNKNOWN','Aligned complete validation loss required')
            else:
                val=np.asarray(v);delta=float(val[-window:].mean()-val[-2*window:-window].mean());add('overfit_hint','WARN' if change<0 and delta>0 else 'PASS','Opposing train/validation loss window trends only; not a causal finding',{'train_relative_change':change,'validation_absolute_change':delta})
    return statistics_engine.persist({'method':'training-diagnostics-v1','inputs':{'snapshot_id':snapshot_id,'loss_metric':loss_metric,'validation_metric':validation_metric,'window':window,'relative_threshold':relative_threshold},'result':findings,'sources':s['evidence'],'unit':'Within-run observation windows; no independent replicate inference','unverified':['Causal explanation','GPU bottleneck attribution','Learning-rate intervention effect']})

def query(snapshot_id,text,metric=None):
    s=storage.get(snapshot_id);text=text.strip().lower()
    if any(w in text for w in ('缺失','没有记录','missing','incomplete')):
        rows=[{'run_id':r['id'],'name':r['name'],'missing':[k for k in ('seed','evaluation_protocol','dataset_version') if r['params'].get(k) is None],'sources':r['sources']} for r in s['runs']];rows=[r for r in rows if r['missing']]
        return {'query':{'operation':'missing_metadata','fields':['seed','evaluation_protocol','dataset_version'],'snapshot_id':snapshot_id},'rows':rows}
    if any(w in text for w in ('最低','最高','最好','best','lowest','highest','rank','排序')):
        candidates={k for r in s['runs'] for k in r['metrics']}
        if metric is None:
            matches=[k for k in candidates if k.lower() in text]
            if len(matches)!=1:raise ValueError('Choose one exact source metric; ambiguous natural-language metric mapping is not guessed')
            metric=matches[0]
        rows=[r for r in s['runs'] if metric in r['metrics']];gate=compatibility(rows,metric)
        if gate['status']!='PASS':raise ValueError('Ranking blocked: incompatible or incomplete evaluation definitions')
        direction=rows[0]['metric_definitions'][metric]['direction']
        if direction not in ('minimize','maximize'):raise ValueError('Explicit metric direction required')
        rows=sorted([r for r in rows if r['metrics'][metric] is not None],key=lambda r:r['metrics'][metric],reverse=direction=='maximize')[:100]
        return {'query':{'operation':'rank','metric':metric,'direction':direction,'snapshot_id':snapshot_id,'limit':100},'compatibility':gate,'rows':[{'run_id':r['id'],'name':r['name'],'value':r['metrics'][metric],'sources':r['sources']} for r in rows],'scope':'Selected snapshot only; metric direction determines ordering'}
    raise ValueError('Supported local grammar: missing metadata / best or rank + exact metric. No arbitrary SQL or ungrounded answer generated')

def summarize(snapshot_id,run_ids):
    import json
    s=storage.get(snapshot_id);rows=[r for r in s['runs'] if r['id'] in run_ids]
    if len(rows)!=len(set(run_ids)) or not rows:raise ValueError('Select existing distinct runs')
    fields=sorted({k for r in rows for k in r['params']})
    differences={k:[{'run_id':r['id'],'value':r['params'].get(k)} for r in rows] for k in fields if len({json.dumps(r['params'].get(k),sort_keys=True) for r in rows})>1}
    metrics={}
    for metric in sorted({k for r in rows for k in r['metrics']}):
        selected=[r for r in rows if metric in r['metrics']]
        metrics[metric]={'compatibility':compatibility(selected,metric),'final_values':[{'run_id':r['id'],'value':r['metrics'][metric]} for r in selected],'missing_run_ids':[r['id'] for r in rows if metric not in r['metrics']]}
    missing=[{'run_id':r['id'],'fields':[k for k in ('seed','dataset_version','evaluation_protocol') if r['params'].get(k) is None],'nonfinite_or_missing_values':sum(v is None for a in r['series'].values() for v in a)} for r in rows]
    return statistics_engine.persist({'method':'evidence-bounded-experiment-summary-v1','inputs':{'snapshot_id':snapshot_id,'run_ids':run_ids},'result':{'configuration_differences':differences,'metrics':metrics,'record_quality':missing,'unverified_hypotheses':['Observed model/domain differences are not causal effects.','Independent seed replication and evaluation conditions require verification.'],'suggested_controls':['Hold dataset version, split and evaluation protocol constant.','Use explicitly paired seeds or independent run-level replication before inferential comparison.']},'sources':[{'reference':{'snapshot_id':snapshot_id,'run_id':r['id']},'evidence':r['sources']} for r in rows],'unit':'Descriptive original final values; no invented significance or causal conclusion'})
