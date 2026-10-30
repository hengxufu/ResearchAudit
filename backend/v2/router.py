"""Versioned application router. Existing v0.1 contracts remain available."""
import asyncio,json,time,random,io,zipfile,hashlib
from pathlib import Path
from typing import List,Literal,Optional
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import Response,StreamingResponse
from pydantic import BaseModel,Field,ConfigDict
from .. import storage,statistics_engine,evidence
from ..provenance import graph
from . import assets,analysis,audit,plugins
from .telemetry import gpu_status
router=APIRouter(prefix='/api/v2',tags=['ResearchAudit 2'])
from ..api.common import Strict,guard,executor,RunRef,MetricRef
@router.get('/overview')
def overview():
    runs=executor().listing(500);snapshots=storage.listing()
    return {'snapshots':len(snapshots),'execution_states':{s:sum(r['state']==s for r in runs) for s in ('Pending','Queued','Running','Succeeded','Failed','Cancelled','Interrupted')},'assets':len(assets.listing()),'local_only':True,'execution_count_scope':'Most recent 500 executions','version':'2.0-development'}
class AssetRequest(Strict):
    label:str=Field(min_length=1,max_length=200)
    kind:Literal['dataset','model','checkpoint','result']
    path:str
@router.post('/assets',status_code=201)
def asset_create(request:AssetRequest):return guard(assets.register,request.label,request.kind,request.path)
@router.get('/assets')
def asset_list():return assets.listing()
@router.post('/assets/{id}/versions')
def asset_capture(id:str,hash_content:bool=False):return guard(assets.capture,id,hash_content)
@router.get('/assets/{id}/versions')
def asset_versions(id:str):return guard(assets.versions,id)
@router.post('/asset-versions/{id}/verify')
def asset_verify(id:str):return guard(assets.verify,id)
@router.get('/asset-versions/compare')
def asset_compare(left:str,right:str):return guard(assets.compare,left,right)
class BatchAnalysis(Strict):
    refs:List[RunRef]=Field(min_length=1,max_length=1000)
    group_by:List[str]=Field(default_factory=lambda:['model_version','dataset'],max_length=20)
    seed:int=0
@router.post('/analyses/batch')
def batch_analysis(req:BatchAnalysis):return guard(analysis.batch,[r.model_dump() for r in req.refs],req.group_by,req.seed)
class IndependentAnalysis(Strict):
    left:List[MetricRef]=Field(min_length=3,max_length=1000)
    right:List[MetricRef]=Field(min_length=3,max_length=1000)
    independent_runs:bool=False
    seed:int=0
@router.post('/analyses/independent')
def independent_analysis(req:IndependentAnalysis):return guard(analysis.independent,[r.model_dump() for r in req.left],[r.model_dump() for r in req.right],req.independent_runs,req.seed)
class HolmRequest(Strict):ids:List[str]=Field(min_length=1,max_length=100)
@router.post('/analyses/holm')
def holm(req:HolmRequest):return guard(analysis.holm,req.ids)
class CorrelationRequest(Strict):
    reference:MetricRef
    other_metric:str
@router.post('/analyses/correlation')
def correlation(req:CorrelationRequest):return guard(analysis.correlation,req.reference.model_dump(),req.other_metric)
@router.get('/analyses')
def analyses(limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:raise HTTPException(422,'Invalid pagination')
    with storage.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,payload TEXT)')
        return [{'id':r[0],**json.loads(r[1])} for r in c.execute('SELECT id,payload FROM analyses ORDER BY rowid DESC LIMIT ? OFFSET ?',(limit,offset))]
class Bound(Strict):
    metric:str
    minimum:float
    maximum:float
    unit:str=Field(min_length=1,max_length=100)
class AuditRequest(Strict):
    full_hash:bool=False
    bounds:List[Bound]=Field(default_factory=list,max_length=30)
@router.post('/snapshots/{id}/audits')
def audit_run(id:int,req:AuditRequest):
    if any(b.minimum>b.maximum for b in req.bounds):raise HTTPException(422,'Invalid bounds')
    return guard(audit.execute,id,req.full_hash,[b.model_dump() for b in req.bounds])
@router.get('/snapshots/{id}/audits')
def audit_history(id:int):return audit.history(id)
class PluginRequest(Strict):
    path:str
    definitions:dict=Field(default_factory=dict)
@router.post('/plugins/{kind}/parse')
def plugin_parse(kind:Literal['deep_learning','pose','simulation'],req:PluginRequest):
    parsed=guard(plugins.parse,kind,req.path,req.definitions)
    record=statistics_engine.persist({'method':kind+'-file-parser-v1','inputs':{'path':req.path,'definitions':req.definitions},'result':parsed,'sources':[parsed['source']],'unit':'Declared source fields; no scientific validity inferred'})
    return {**parsed,'analysis_id':record['id']}
@router.get('/snapshots/{id}/graph')
def provenance(id:int):
    s=guard(storage.get,id);g=graph(s);g['nodes'].append({'id':'snapshot:'+str(id),'type':'snapshot','attributes':{'label':str(id)}})
    records=evidence.listing();selected={r['id'] for r in records if any(ref.get('snapshot_id')==id for ref in r['sources'])}
    changed=True
    while changed:
        previous=len(selected)
        for record in records:
            refs={ref['evidence_id'] for ref in record['sources'] if 'evidence_id' in ref}
            if record['id'] in selected:selected.update(refs)
            if refs&selected:selected.add(record['id'])
        changed=len(selected)!=previous
    for record in records:
        if record['id'] not in selected:continue
        g['nodes'].append({'id':record['id'],'type':record['kind'],'attributes':{'label':record['label']}})
        for ref in record['sources']:
            origin=ref.get('evidence_id') or ref.get('run_id')
            if origin:g['edges'].append({'from':origin,'to':record['id'],'type':'supports','basis':'user_declared'})
    from .registry import associations,experiments
    latest={}
    for relation in associations(id):latest.setdefault(relation['run_id'],relation)
    exps={e['id']:e for e in experiments()}
    for run_id,relation in latest.items():
        exp=exps[relation['experiment_id']]
        g['nodes'].extend([{'id':exp['id'],'type':'experiment','attributes':{'label':exp['label']}},{'id':exp['project_id'],'type':'project','attributes':{'label':exp['project_id']}}])
        g['edges'].extend([{'from':exp['project_id'],'to':exp['id'],'type':'contains','basis':'registered'},{'from':exp['id'],'to':run_id,'type':'contains','basis':relation['basis']}])
    analysis_ids=[]
    with storage.connect() as c:
        if c.execute("SELECT name FROM sqlite_master WHERE name='analyses' AND type='table'").fetchone():
            for key,payload in c.execute('SELECT id,payload FROM analyses'):
                item=json.loads(payload);refs=[ref.get('reference') for ref in item.get('sources',[]) if isinstance(ref,dict) and ref.get('reference',{}).get('snapshot_id')==id]
                if item.get('inputs',{}).get('snapshot_id')==id:refs.append(item['inputs'])
                if not refs:continue
                analysis_ids.append(key);g['nodes'].append({'id':key,'type':'analysis','attributes':{'label':item['method'],'unit':item.get('unit')}})
                for ref in refs:
                    origin=ref['run_id']+':'+ref['metric'] if ref.get('run_id') and ref.get('metric') else ref.get('run_id','snapshot:'+str(id))
                    g['edges'].append({'from':origin,'to':key,'type':'computed_from','basis':'persisted_analysis_inputs'})
        if c.execute("SELECT name FROM sqlite_master WHERE name='report_records' AND type='table'").fetchone():
            for key,payload in c.execute('SELECT id,spec FROM report_records WHERE snapshot_id=?',(id,)):
                item=json.loads(payload);g['nodes'].append({'id':key,'type':'report','attributes':{'label':item['method'],'sha256':key}})
                for aid in item.get('analysis_ids',[]):g['edges'].append({'from':aid,'to':key,'type':'reported_in','basis':'report_specification'})
    for figure in storage.figures(id):
        g['nodes'].append({'id':figure['id'],'type':'figure','attributes':{'label':figure['metric']+' / '+figure['kind']}})
        for source in figure['sources']:g['edges'].append({'from':source['run_id']+':'+figure['metric'],'to':figure['id'],'type':'plotted_from','basis':'figure_specification'})
    g['nodes']=list({n['id']:n for n in g['nodes']}.values());return g
@router.get('/resources')
def resources():
    import psutil
    active=[]
    with executor().lock:processes=list(executor().processes.items())
    for id,handle in processes:
        try:
            p=psutil.Process(handle.pid);children=p.children(recursive=True);members=[p]+children
            active.append({'run_id':id,'pid':p.pid,'rss_bytes':sum(v.memory_info().rss for v in members if v.is_running()),'cpu_seconds':sum(sum(v.cpu_times()[:2]) for v in members if v.is_running()),'process_count':len(members)})
        except (psutil.NoSuchProcess,psutil.AccessDenied):continue
    return {'active':active,'system_memory':dict(psutil.virtual_memory()._asdict()),'logical_cpus':psutil.cpu_count(),'gpu':gpu_status(),'hard_limits':False,'concurrency_limit':executor().limit}
@router.get('/executions/{id}/events')
async def execution_events(id:str,request:Request,max_events:int=300):
    guard(executor().get,id)
    if not 1<=max_events<=1000:raise HTTPException(422,'Invalid event limit')
    async def events():
        offsets={'stdout':0,'stderr':0}
        for _ in range(max_events):
            if await request.is_disconnected():break
            state=executor().get(id);logs={}
            for stream in offsets:
                entry=executor().logs(id,stream,offsets[stream]);offsets[stream]=entry['next_offset'];logs[stream]=entry['text']
            yield 'data: '+json.dumps({'state':state['state'],'logs':logs})+'\n\n'
            if state['state'] in ('Succeeded','Failed','Cancelled','Interrupted'):break
            await asyncio.sleep(.5)
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-cache'})
class DependencyRequest(Strict):dependencies:List[str]=Field(max_length=100)
@router.put('/executions/{id}/dependencies')
def set_dependencies(id:str,req:DependencyRequest):
    engine=executor()
    with engine.lock:
        target=guard(engine.get,id)
        if target['state']!='Pending':raise HTTPException(409,'Only Pending dependencies can change')
        nodes={r['id']:r['spec'].get('dependencies',[]) for r in engine.listing(100000)}
        if any(dep not in nodes for dep in req.dependencies):raise HTTPException(422,'Unknown dependency')
        nodes[id]=req.dependencies
        visiting=set();done=set()
        def visit(key):
            if key in visiting:raise ValueError('Dependency cycle')
            if key in done:return
            visiting.add(key)
            for dep in nodes[key]:visit(dep)
            visiting.remove(key);done.add(key)
        guard(visit,id)
        spec=target['spec'];spec['dependencies']=req.dependencies;engine.change(id,spec=json.dumps(spec))
    return engine.get(id)
class SearchBatch(Strict):
    spec:dict
    choices:dict[str,List[float]]
    count:int=Field(ge=1,le=100)
    seed:int=0
@router.post('/execution-batches/random',status_code=201)
def random_search(req:SearchBatch):
    from ..main import ExecutionSpec
    try:base=ExecutionSpec(**req.spec).model_dump()
    except ValueError as e:raise HTTPException(422,str(e))
    if not req.choices or any(not v for v in req.choices.values()):raise HTTPException(422,'Nonempty choices required')
    rng=random.Random(req.seed);runs=[]
    for _ in range(req.count):
        spec={**base,'params':dict(base['params'])};p={k:rng.choice(v) for k,v in req.choices.items()};spec['params'].update(p)
        spec['argv']=[__import__('functools').reduce(lambda arg,kv:arg.replace('{'+kv[0]+'}',str(kv[1])),p.items(),arg) for arg in base['argv']]
        runs.append(guard(executor().create,spec))
    bid=__import__('uuid').uuid4().hex
    with storage.connect() as c:c.execute('CREATE TABLE IF NOT EXISTS execution_batches(id TEXT PRIMARY KEY,payload TEXT)');c.execute('INSERT INTO execution_batches VALUES (?,?)',(bid,json.dumps({'seed':req.seed,'run_ids':[r['id'] for r in runs]})))
    return {'id':bid,'runs':runs,'state':'Pending'}
@router.get('/snapshots/{id}/report.pdf')
def report_pdf(id:int):
    from .reporting import pdf
    return Response(guard(pdf,id),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="researchaudit-{id}.pdf"'})

class IntegrationRequest(Strict):path:str
@router.post('/integrations/{format}/inspect')
def inspect_integration(format:Literal['dvc','ro-crate'],req:IntegrationRequest):
    from .integrations import inspect
    return guard(inspect,format,req.path)
@router.get('/snapshots/{id}/ro-crate-metadata.json')
def crate_metadata(id:int):
    from .integrations import crate
    return guard(crate,id)

class ExperimentRequest(Strict):
    project_id:str
    label:str=Field(min_length=1,max_length=200)
@router.get('/experiments')
def experiment_list():
    from .registry import experiments
    return experiments()
@router.post('/experiments',status_code=201)
def create_experiment(req:ExperimentRequest):
    from ..main import tracking_engine
    from .registry import create
    if not any(p['id']==req.project_id for p in tracking_engine().projects()):raise HTTPException(422,'Register project directory first')
    return create(req.project_id,req.label)
class AssociationRequest(RunRef):experiment_id:str
@router.post('/associations',status_code=201)
def associate_run(req:AssociationRequest):
    from .registry import associate
    return guard(associate,req.snapshot_id,req.run_id,req.experiment_id)
@router.get('/snapshots/{id}/associations')
def run_association_history(id:int):
    from .registry import associations
    return associations(id)
@router.post('/analyses/time-series')
def time_series_analysis(ref:MetricRef):return guard(analysis.time_series,ref.model_dump())
class ParetoRequest(Strict):
    refs:List[RunRef]=Field(min_length=2,max_length=1000)
    metrics:List[str]=Field(min_length=2,max_length=10)
@router.post('/analyses/pareto')
def pareto_analysis(req:ParetoRequest):return guard(analysis.pareto,[r.model_dump() for r in req.refs],req.metrics)
class TrackingSettings(Strict):
    interval_seconds:float=Field(default=5,ge=.2,le=300)
    verification_interval_seconds:float=Field(default=60,ge=1,le=86400)
    max_read_mib:int=Field(default=4,ge=1,le=64)
    delay_per_file_seconds:float=Field(default=0,ge=0,le=1)
@router.put('/tracking/settings')
def tracking_settings(req:TrackingSettings):
    from ..main import tracking_engine
    engine=tracking_engine()
    with engine.lock:
        settings={'interval':req.interval_seconds,'verification_interval':req.verification_interval_seconds,'max_read':req.max_read_mib*1048576,'scan_delay':req.delay_per_file_seconds}
        with engine.connect() as c:
            c.executemany('INSERT INTO tracking_settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',[(key,json.dumps(value)) for key,value in settings.items()])
        for key,value in settings.items():setattr(engine,key,value)
    return {'settings':req.model_dump(),'scope':'Persisted soft limits; not OS CPU or I/O quotas'}
@router.get('/tracking/diagnostics')
def tracking_diagnostics(limit:int=50,offset:int=0):
    from ..main import tracking_engine
    if not 1<=limit<=500 or offset<0:raise HTTPException(422,'Invalid pagination')
    with tracking_engine().connect() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM sources ORDER BY path LIMIT ? OFFSET ?',(limit,offset))]
        summary=dict(c.execute("SELECT COUNT(*) AS total_sources,SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors,SUM(CASE WHEN status!='deleted' AND size>cursor THEN size-cursor ELSE 0 END) AS pending_known_bytes FROM sources").fetchone())
    return {'summary':summary,'items':rows,'scope':'Backlog uses last observed sizes; unseen filesystem writes are not counted'}
@router.get('/tracking/sources/{id}/history')
def source_generations(id:str):
    from ..main import tracking_engine
    with tracking_engine().connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM source_generations WHERE source_id=? ORDER BY generation DESC',(id,))]
