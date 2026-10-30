from typing import List,Dict,Literal,Optional
from fastapi import APIRouter,Query
from fastapi.responses import Response
from pydantic import Field
from ..v2.router import Strict,guard,executor,RunRef,MetricRef
from ..v3 import documents
from . import projects,environments,optimization,statistics,figures,copilot
from . import science
router=APIRouter(prefix='/api/v4',tags=['ResearchAudit 4'])
class Discovery(Strict):
    path:str
    ignores:List[str]=Field(default_factory=list,max_length=100)
    max_files:int=Field(20000,ge=1,le=100000)
@router.post('/projects/inspect')
def inspect(r:Discovery):return guard(projects.inspect,r.path,r.ignores,r.max_files)
@router.get('/projects')
def project_list():return documents.listing('project_intelligence')
class Association(Strict):
    directory:str
    experiment_label:str=Field(min_length=1,max_length=200)
    reason:str=Field(min_length=1,max_length=2000)
    revision:int=Field(ge=1)
@router.post('/projects/{id}/associations')
def association(id:str,r:Association):return guard(projects.associate,id,**r.model_dump())
class Backfill(Strict):directories:List[str]=Field(min_length=1,max_length=100)
@router.post('/projects/{id}/backfill')
def backfill(id:str,r:Backfill):return guard(projects.backfill,id,r.directories)
@router.post('/projects/{id}/watch')
def watch(id:str):
    from ..main import tracking_engine
    doc=guard(documents.get,'project_intelligence',id)
    return guard(tracking_engine().register,doc['root'])
class Environment(Strict):
    path:str
    kind:Literal['pip','conda']
@router.post('/environments/import')
def env_import(r:Environment):return guard(environments.declaration,r.path,r.kind)
@router.get('/environments/runner')
def env_runner():return environments.runner()
@router.post('/environments/{id}/compare')
def env_compare(id:str):return guard(environments.compare,id)
@router.post('/reproductions/{id}/environment-diff')
def reproduction_diff(id:str):return guard(environments.reproduction_diff,id)
class Target(Strict):executable:str
@router.post('/reproductions/{id}/target')
def target(id:str,r:Target):return guard(environments.target_manifest,id,r.executable)
@router.get('/environments')
def env_list():return documents.listing('environment_declaration')
class Constraint(Strict):
    coefficients:Dict[str,float]
    upper:float
class Optimize(Strict):
    refs:List[RunRef]=Field(min_length=1,max_length=200)
    metric:str
    space:Dict[str,List[float]]
    algorithm:Literal['grid','random','bayesian']='bayesian'
    count:int=Field(3,ge=1,le=100)
    budget:int=Field(10,ge=1,le=100)
    seed:int=0
    constraints:List[Constraint]=Field(default_factory=list,max_length=20)
@router.post('/optimizations')
def optimize(r:Optimize):return guard(optimization.propose,[v.model_dump() for v in r.refs],r.metric,r.space,r.algorithm,r.count,r.budget,r.seed,[v.model_dump() for v in r.constraints])
@router.get('/optimizations')
def optimizations():return documents.listing('optimization')
class Dispatch(Strict):
    candidate:int=Field(ge=0)
    spec:dict
    confirmed:bool=False
@router.post('/optimizations/{id}/dispatch')
def dispatch(id:str,r:Dispatch):
    from ..main import ExecutionSpec
    spec=guard(ExecutionSpec.model_validate,r.spec)
    return guard(optimization.dispatch,executor(),id,r.candidate,spec.model_dump(),r.confirmed)
@router.get('/optimizations/{id}/results')
def results(id:str):return guard(optimization.results,executor(),id)
class Statistics(Strict):
    refs:List[RunRef]=Field(min_length=3,max_length=500)
    metric:str
    group_by:List[str]=Field(min_length=1,max_length=5)
    paired:bool=False
    independent:bool=False
    seed:int=0
    resamples:int=Field(2000,ge=100,le=10000)
@router.get('/statistics/methods')
def methods():return statistics.METHODS
@router.post('/statistics/bootstrap')
def bootstrap(r:Statistics):return guard(statistics.analyze,[v.model_dump() for v in r.refs],r.metric,r.group_by,r.paired,r.independent,r.seed,r.resamples)
class Panel(Strict):
    label:str=Field(max_length=200)
    refs:List[MetricRef]=Field(min_length=1,max_length=20)
    smooth:int=Field(1,ge=1,le=100)
    scale:Literal['linear','log']='linear'
    xlim:Optional[List[float]]=None
class Figure(Strict):
    panels:List[Panel]=Field(min_length=1,max_length=6)
    title:str=Field(max_length=200)
@router.post('/figures')
def figure(r:Figure):return guard(figures.save,[p.model_dump() for p in r.panels],r.title)
@router.get('/figures/{id}/{format}')
def figure_export(id:str,format:Literal['svg','pdf','png']):
    data,digest=guard(figures.render,id,format)
    return Response(data,media_type={'svg':'image/svg+xml','pdf':'application/pdf','png':'image/png'}[format],headers={'X-Content-SHA256':digest,'Content-Disposition':'attachment; filename="researchaudit-multipanel.'+format+'"'})
class Copilot(Strict):
    snapshot_id:int
    operation:Literal['query','summary','audit','analysis_plan']
    text:str=Field('',max_length=2000)
@router.post('/copilot')
def copilot_run(r:Copilot):return guard(copilot.run,**r.model_dump())
@router.get('/records/{kind}')
def records(kind:Literal['environment_comparison','project_backfill','figure_recipe','optimization'],limit:int=Query(100,ge=1,le=500)):return documents.listing(kind,limit)
class Radiation(RunRef):
    temperature:str
    ambient:str
    power:str
    area_m2:float=Field(gt=0)
    emissivity:float=Field(ge=0,le=1)
    atol:float=Field(ge=0)
    rtol:float=Field(ge=0)
@router.post('/science/radiation')
def radiation(r:Radiation):return guard(science.radiation,**r.model_dump())
@router.get('/workflows/{id}/diff')
def workflow_diff(id:str,left:int=Query(...,ge=1),right:int=Query(...,ge=1)):
    a=guard(documents.get,'workflow',id,left);b=guard(documents.get,'workflow',id,right)
    aa={n['id']:n for n in a['nodes']};bb={n['id']:n for n in b['nodes']}
    return {'workflow_id':id,'left_revision':left,'right_revision':right,'added':sorted(bb.keys()-aa.keys()),'removed':sorted(aa.keys()-bb.keys()),'changed':[k for k in sorted(aa.keys()&bb.keys()) if aa[k]!=bb[k]],'source_hashes':[a['sha256'],b['sha256']],'cache_reuse':False}
