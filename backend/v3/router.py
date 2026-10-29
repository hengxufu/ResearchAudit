"""Strict v3 application contracts; legacy routes remain unchanged."""
import json
from typing import List,Optional,Literal,Dict
from fastapi import APIRouter,HTTPException,Query
from fastapi.responses import Response
from pydantic import Field
from ..v2.router import Strict,guard,executor,RunRef,MetricRef
from . import documents,reproduction,data_studio,suites,intelligence,knowledge,workflows
router=APIRouter(prefix='/api/v3',tags=['ResearchAudit 3'])
_workflow=None
def workflow_engine():
    global _workflow
    engine=executor()
    if _workflow is None or _workflow.executor is not engine:_workflow=workflows.WorkflowEngine(engine)
    return _workflow

class Tolerance(Strict):
    atol:float=Field(ge=0)
    rtol:float=Field(ge=0)
class Reproduction(Strict):
    source_execution:str
    input_versions:List[str]=Field(default_factory=list,max_length=50)
    tolerances:Dict[str,Tolerance]=Field(default_factory=dict,max_length=100)
class Confirm(Strict):
    confirmed:bool=False
    allow_code_change:bool=False
@router.post('/reproductions')
def create_reproduction(r:Reproduction):return guard(reproduction.create,executor(),r.source_execution,r.input_versions,{k:v.model_dump() for k,v in r.tolerances.items()})
@router.get('/reproductions')
def reproductions():return documents.listing('reproduction')
@router.post('/reproductions/{id}/start')
def replay(id:str,r:Confirm):return guard(reproduction.launch,executor(),id,r.confirmed,r.allow_code_change)
@router.post('/reproductions/{id}/evaluate')
def evaluate(id:str):return guard(reproduction.evaluate,executor(),id)
@router.get('/reproductions/{id}/manifest.json')
def manifest(id:str):return Response(json.dumps(guard(documents.get,'reproduction',id),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="reproduction-manifest.json"'})
@router.get('/reproduction-reports/{id}.json')
def reproduction_report(id:str):return Response(json.dumps(guard(documents.get,'reproduction_report',id),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="reproduction-report.json"'})
@router.post('/assets/{id}/notebook')
def notebook(id:str,path:str):
    from .notebooks import read
    return guard(read,id,path)
class Distribution(Strict):
    left:List[MetricRef]=Field(min_length=3,max_length=200)
    right:List[MetricRef]=Field(min_length=3,max_length=200)
    independent_runs:bool=False
    seed:int=0
@router.post('/reproductions/distribution')
def distribution(r:Distribution):return guard(reproduction.distributions,[v.model_dump() for v in r.left],[v.model_dump() for v in r.right],r.independent_runs,r.seed)

@router.get('/assets/{id}/files')
def files(id:str,path:str='',limit:int=Query(100,ge=1,le=500)):return guard(data_studio.files,id,path,limit)
@router.get('/assets/{id}/inspect')
def inspect(id:str,path:str=''):return guard(data_studio.inspect,id,path)
class Slice(Strict):
    path:str=''
    key:str
    slices:List[List[int]]=Field(max_length=8)
@router.post('/assets/{id}/slice')
def slice_array(id:str,r:Slice):
    if any(len(s)!=3 for s in r.slices):raise HTTPException(422,'Slices must be [start,stop,step]')
    return guard(data_studio.array_slice,id,r.path,r.key,r.slices)
@router.get('/assets/{id}/table')
def table(id:str,path:str='',offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=500)):return guard(data_studio.table,id,path,offset,limit)
@router.get('/assets/{id}/image')
def image(id:str,path:str='',size:int=Query(768,ge=32,le=1024)):return Response(guard(data_studio.image_preview,id,path,size),media_type='image/jpeg')

class Pose(RunRef):
    columns:Dict[str,List[str]]
    quaternion_order:Literal['xyzw','wxyz']
    convention:Literal['active','passive']
    frame:str=Field(min_length=1,max_length=100)
    translation_unit:str=Field(min_length=1,max_length=100)
    failure_rotation_degrees:Optional[float]=Field(None,ge=0)
    failure_translation:Optional[float]=Field(None,ge=0)
@router.post('/suites/pose')
def pose(r:Pose):return guard(suites.pose,**r.model_dump())
class Balance(RunRef):
    energy_metric:str
    power_metric:str
    time_metric:str
    unit_energy:Literal['J']
    unit_power:Literal['W']
    unit_time:Literal['s']
    atol:float=Field(ge=0)
    rtol:float=Field(ge=0)
@router.post('/suites/energy-balance')
def balance(r:Balance):return guard(suites.balance,**r.model_dump())
class Trend(RunRef):
    x_metric:str
    y_metric:str
    kind:Literal['convergence','sensitivity']
@router.post('/suites/simulation-trend')
def trend(r:Trend):return guard(suites.simulation_trend,**r.model_dump())
class Training(Strict):
    snapshot_id:int
    metric:str
@router.post('/suites/training')
def training(r:Training):return guard(suites.training,r.snapshot_id,r.metric)
class Diagnosis(Strict):
    snapshot_id:int
    loss_metric:str='loss'
    validation_metric:Optional[str]=None
    window:int=Field(5,ge=2,le=1000)
    relative_threshold:float=Field(.1,gt=0,le=10)
@router.post('/intelligence/diagnose')
def diagnose(r:Diagnosis):return guard(intelligence.diagnose,**r.model_dump())
class Question(Strict):
    snapshot_id:int
    text:str=Field(min_length=1,max_length=1000)
    metric:Optional[str]=None
@router.post('/intelligence/query')
def question(r:Question):return guard(intelligence.query,**r.model_dump())
class Summary(Strict):
    snapshot_id:int
    run_ids:List[str]=Field(min_length=1,max_length=500)
@router.post('/intelligence/summary')
def summary(r:Summary):return guard(intelligence.summarize,r.snapshot_id,r.run_ids)

class Node(Strict):
    id:str=Field(min_length=1,max_length=80)
    kind:Literal['command','import','describe','batch','audit','figure','report','balance','asset_verify']
    config:dict
    depends_on:List[str]=Field(default_factory=list,max_length=100)
    retries:int=Field(0,ge=0,le=2)
    condition:Optional[dict]=None
class Workflow(Strict):
    name:str=Field(min_length=1,max_length=200)
    description:str=Field('',max_length=10000)
    nodes:List[Node]=Field(min_length=1,max_length=100)
class WorkflowStart(Strict):
    revision:Optional[int]=Field(None,ge=1)
    confirmed:bool=False
@router.post('/workflows')
def workflow_create(r:Workflow):return guard(workflows.save,r.model_dump())
@router.put('/workflows/{id}')
def workflow_update(id:str,r:Workflow,revision:int=Query(...,ge=1)):return guard(workflows.save,r.model_dump(),id,revision)
@router.get('/workflows')
def workflow_list():return documents.listing('workflow')
@router.get('/workflows/{id}/history')
def workflow_history(id:str):return guard(documents.history,'workflow',id)
@router.post('/workflows/{id}/start')
def workflow_start(id:str,r:WorkflowStart):return guard(workflow_engine().start,id,r.revision,r.confirmed)
@router.get('/workflow-runs')
def workflow_runs(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):return workflow_engine().listing(limit,offset)
@router.get('/workflow-runs/{id}')
def workflow_run(id:str):return guard(workflow_engine().get,id)
@router.post('/workflow-runs/{id}/cancel')
def workflow_cancel(id:str):return guard(workflow_engine().cancel,id)
@router.get('/workflow-runs/{id}/artifacts/{node}')
def workflow_artifact(id:str,node:str):
    result=guard(workflow_engine().get,id)['nodes'].get(node,{})
    path=result.get('output',{}).get('path')
    if not path:raise HTTPException(404,'No exported artifact')
    from pathlib import Path
    from .. import storage
    p=Path(path).resolve();root=(storage.DB/'workflows'/id).resolve()
    if not p.is_relative_to(root):raise HTTPException(422,'Invalid artifact reference')
    from fastapi.responses import FileResponse
    return FileResponse(p,filename=p.name)

class Reference(Strict):
    kind:Literal['snapshot','analysis','figure','knowledge']
    id:str
    snapshot_id:Optional[int]=None
    run_id:Optional[str]=None
    revision:Optional[int]=None
class Knowledge(Strict):
    kind:Literal['note','hypothesis','design','claim','issue','milestone']
    title:str=Field(min_length=1,max_length=200)
    body:str=Field('',max_length=50000)
    conditions:str=Field('',max_length=10000)
    validation_status:Literal['unverified','reviewed','disputed']='unverified'
    review_reason:str=Field('',max_length=10000)
    supporting:List[Reference]=Field(default_factory=list,max_length=100)
    conflicting:List[Reference]=Field(default_factory=list,max_length=100)
@router.post('/knowledge')
def knowledge_create(r:Knowledge):return guard(knowledge.save,r.model_dump())
@router.put('/knowledge/{id}')
def knowledge_update(id:str,r:Knowledge,revision:int=Query(...,ge=1)):return guard(knowledge.save,r.model_dump(),id,revision)
@router.get('/knowledge')
def knowledge_list(q:str='',limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):return documents.listing('knowledge',limit,offset,q)
@router.get('/knowledge/{id}/history')
def knowledge_history(id:str):return guard(documents.history,'knowledge',id)
@router.get('/snapshots/{id}/graph')
def graph(id:int):
    from ..v2.router import provenance
    g=provenance(id);known={n['id'] for n in g['nodes']}
    records=documents.listing('knowledge',500)
    selected=set()
    for record in records:
        for ref in record.get('supporting',[])+record.get('conflicting',[]):
            origin='snapshot:'+ref['id'] if ref['kind']=='snapshot' else ref['id']
            if origin in known:selected.add(record['id'])
    # Include multi-level knowledge dependencies reachable from current evidence.
    changed=True
    while changed:
        before=len(selected)
        for record in records:
            if any(ref['kind']=='knowledge' and ref['id'] in selected for ref in record.get('supporting',[])+record.get('conflicting',[])):selected.add(record['id'])
        changed=len(selected)!=before
    for record in records:
        if record['id'] not in selected:continue
        g['nodes'].append({'id':record['id'],'type':record['kind'],'attributes':{'label':record['title'],'revision':record['revision'],'validation_status':record['validation_status']}})
        for relation in ('supporting','conflicting'):
            for ref in record[relation]:
                origin='snapshot:'+ref['id'] if ref['kind']=='snapshot' else ref['id']
                if origin in known or origin in selected:g['edges'].append({'from':origin,'to':record['id'],'type':relation,'basis':'user_declared','evidence_revision':ref.get('revision')})
    for record in documents.listing('reproduction_report',500):
        if id not in (record['source_snapshot'],record['replay_snapshot']):continue
        g['nodes'].append({'id':record['id'],'type':'reproduction_report','attributes':{'label':'Reproduction scorecard','scorecard':record['scorecard']}})
        for sid in (record['source_snapshot'],record['replay_snapshot']):
            if sid is None:continue
            origin='snapshot:'+str(sid)
            if origin not in known:g['nodes'].append({'id':origin,'type':'snapshot','attributes':{'label':str(sid)}});known.add(origin)
            g['edges'].append({'from':origin,'to':record['id'],'type':'compared_in','basis':'executed_rerun_evidence'})
    g['scope']='Imported, computed and user-declared evidence; knowledge view limited to 500 latest documents per kind'
    return g
