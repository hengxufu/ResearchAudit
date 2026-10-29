import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import storage
from .collect import scan
from .analysis import audit,compare
from .validation import REGISTRY
from contextlib import asynccontextmanager
from . import jobs
@asynccontextmanager
async def lifespan(app):
    jobs.recover()
    app.state.tracker=tracking_engine()
    app.state.tracker.start()
    app.state.orchestrator=execution_engine()
    app.state.orchestrator.start()
    from .v3.router import workflow_engine
    app.state.workflows=workflow_engine();app.state.workflows.recover()
    try: yield
    finally:
        app.state.workflows.stop()
        app.state.orchestrator.stop()
        app.state.tracker.stop()
app=FastAPI(lifespan=lifespan,title="ResearchAudit",version="3.0.0-dev.0")
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]','testserver'])
@app.middleware('http')
async def local_origin_boundary(request,call_next):
    from urllib.parse import urlparse
    from fastapi.responses import JSONResponse
    origin=request.headers.get('origin')
    if request.method in ('POST','PUT','PATCH','DELETE') and origin:
        if urlparse(origin).hostname not in ('127.0.0.1','localhost','::1'):
            return JSONResponse({'detail':'Local browser origin required'},status_code=403)
    return await call_next(request)
class ImportRequest(BaseModel):
    path: str
@app.get("/api/projects")
def projects(): return storage.listing()
@app.post("/api/import")
def ingest(req:ImportRequest):
    try:
        s=scan(req.path); id=storage.save(s["root"],s)
        return {"id":id,**s}
    except ValueError as e: raise HTTPException(400,str(e))
def snapshot(id):
    try: return storage.get(id)
    except KeyError: raise HTTPException(404,"Snapshot not found")
@app.get("/api/projects/{id}")
def detail(id:int): return snapshot(id)
@app.get("/api/projects/{id}/audit")
def check(id:int): return audit(snapshot(id))
@app.get("/api/projects/{id}/compare")
def comparison(id:int,metric:str,filters:str="{}"):
    try:
        criteria=json.loads(filters)
        if not isinstance(criteria,dict): raise ValueError("filters must be an object")
        return compare(snapshot(id),metric,criteria)
    except (ValueError,TypeError) as e: raise HTTPException(400,str(e))
@app.get("/api/projects/{id}/report")
def report(id:int):
    s=snapshot(id)
    from .reports import render
    body=render(s,id,storage.figures(id))
    annotations={r['id']:history.revisions(id,r['id']) for r in s['runs']}
    body+='\n## Historical curation (user-declared, separate from imported facts)\n\n```json\n'+json.dumps(annotations,ensure_ascii=False,indent=2)+'\n```\n'
    return Response(body,media_type="text/markdown",headers={"Content-Disposition":f'attachment; filename="researchaudit-{id}.md"'})
@app.post("/api/projects/{id}/validate/{plugin}")
def validate(id:int,plugin:str,run:str,metric:str):
    s=snapshot(id)
    if plugin not in REGISTRY: raise HTTPException(404,"Unknown plugin")
    try:
        r=next(r for r in s["runs"] if r["name"]==run)
        return {"result":REGISTRY[plugin](r["series"][metric]),"sources":r["sources"],"snapshot":id}
    except (StopIteration,KeyError,ValueError) as e: raise HTTPException(400,str(e))
@app.get("/api/projects/{id}/graph")
def evidence_graph(id:int):
    from .provenance import graph
    return graph(snapshot(id))
@app.get("/api/projects/{id}/figure")
def figure(id:int,metric:str,kind:str="curve",format:str="pdf"):
    from .figures import export
    try:
        data,spec=export(snapshot(id),metric,kind,format)
        storage.save_figure(id,spec)
        return Response(data,media_type={"pdf":"application/pdf","png":"image/png","svg":"image/svg+xml"}[format],headers={"Content-Disposition":f'attachment; filename="researchaudit-{id}-{kind}.{format}"',"X-Evidence-ID":spec['id']})
    except ValueError as e: raise HTTPException(400,str(e))
@app.get("/api/projects/{id}/figures")
def figure_evidence(id:int):
    snapshot(id)
    return storage.figures(id)
@app.get("/api/projects/{id}/observations")
def observations(id:int,metric:str,run_id:str=None,limit:int=10000,offset:int=0):
    snapshot(id)
    if not 1<=limit<=100000 or offset<0: raise HTTPException(400,"Invalid page bounds")
    return storage.query_metrics(id,metric,run_id,limit,offset)
# Curation endpoints never modify imported parameters or metrics.
from typing import List, Literal, Union, Optional
from pydantic import Field, ConfigDict
from . import history
class Condition(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    name:str=Field(min_length=1,max_length=100)
    value:Union[str,float,bool]=Field(union_mode="left_to_right")
    unit:str=Field(default="",max_length=100)
    source:str=Field(min_length=1,max_length=2000)
class Variable(Condition):
    role:Literal["independent","dependent","controlled","confounder"]
class Curation(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    expected_revision:int=Field(ge=0)
    title:str=Field(default="",max_length=200)
    tags:List[str]=Field(default_factory=list,max_length=30)
    status:Literal["unreviewed","reviewed","archived"]="unreviewed"
    conditions:List[Condition]=Field(default_factory=list,max_length=100)
    variables:List[Variable]=Field(default_factory=list,max_length=100)
    notes:str=Field(default="",max_length=20000)
@app.get("/api/history")
def historical_records(q:str="",tag:str="",status:str="",limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0: raise HTTPException(400,"Invalid pagination")
    return history.records(q,tag,status,limit,offset)
@app.get("/api/history/{run_id}")
def run_history(run_id:str): return history.history(run_id)
@app.get("/api/projects/{id}/runs/{run_id}/revisions")
def annotation_revisions(id:int,run_id:str):
    try: return history.revisions(id,run_id)
    except KeyError: raise HTTPException(404,"Run or snapshot not found")
@app.put("/api/projects/{id}/runs/{run_id}/annotation")
def annotate(id:int,run_id:str,request:Curation):
    payload=request.model_dump(exclude={"expected_revision"})
    for group in (payload['conditions'],payload['variables']):
        names=[v['name'].strip().casefold() for v in group]
        if any(not n for n in names) or len(set(names))!=len(names): raise HTTPException(422,"Field names must be nonempty and unique")
    try: return history.update(id,run_id,payload,request.expected_revision)
    except KeyError: raise HTTPException(404,"Run or snapshot not found")
    except ValueError as e: raise HTTPException(409,str(e))
@app.post("/api/import-jobs",status_code=202)
def create_import_job(req:ImportRequest):
    try: return jobs.submit(req.path)
    except ValueError as e: raise HTTPException(429,str(e))
@app.get("/api/import-jobs")
def import_jobs(): return jobs.listing()
@app.get("/api/import-jobs/{job_id}")
def import_job(job_id:str):
    try: return jobs.get(job_id)
    except KeyError: raise HTTPException(404,"Import job not found")
@app.post("/api/import-jobs/{job_id}/cancel")
def cancel_import(job_id:str):
    try: return jobs.cancel(job_id)
    except KeyError: raise HTTPException(404,"Import job not found")
    except ValueError as e: raise HTTPException(409,str(e))
from . import science, samples, evidence
class ScientificRequest(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    run_id:str
    metric:str
    x:List[float]=Field(default_factory=list,max_length=10000)
    atol:float=Field(default=0,ge=0)
    rtol:float=Field(default=0,ge=0)
@app.post("/api/projects/{id}/science/{check}")
def scientific_check(id:int,check:Literal["energy","convergence","sensitivity"],request:ScientificRequest):
    s=snapshot(id)
    r=next((r for r in s['runs'] if r['id']==request.run_id),None)
    if not r or request.metric not in r['series']: raise HTTPException(404,"Unknown run series")
    values=r['series'][request.metric]
    try:
        if any(v is None for v in values): raise ValueError("Missing observations must be resolved explicitly")
        result=science.energy(values,request.atol,request.rtol) if check=="energy" else science.convergence(request.x,values) if check=="convergence" else science.sensitivity(request.x,values)
        return {"result":result,"inputs":request.model_dump(),"sources":r.get('metric_sources',{}).get(request.metric,r['sources']),"snapshot_id":id}
    except ValueError as e: raise HTTPException(422,str(e))
class PropagationRequest(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    coefficients:List[float]=Field(max_length=100)
    covariance:List[List[float]]=Field(max_length=100)
    product_units:List[str]=Field(max_length=100)
@app.post("/api/science/linear-propagation")
def linear_propagation(request:PropagationRequest):
    try: return {"result":science.propagation(request.coefficients,request.covariance,request.product_units),"inputs":request.model_dump(),"basis":"user_supplied"}
    except ValueError as e: raise HTTPException(422,str(e))
@app.get("/api/projects/{id}/samples")
def sample_quality(id:int,path:str):
    try: return samples.analyze(snapshot(id),path)
    except (ValueError,OSError) as e: raise HTTPException(422,str(e))
class EvidenceSource(BaseModel):
    model_config=ConfigDict(extra="forbid")
    evidence_id:Optional[str]=None
    snapshot_id:Optional[int]=None
    run_id:Optional[str]=None
    metric:Optional[str]=None
class EvidenceRequest(BaseModel):
    kind:Literal["figure","table","claim","experiment"]
    label:str=Field(min_length=1,max_length=1000)
    sources:List[EvidenceSource]=Field(min_length=1,max_length=100)
@app.post("/api/evidence",status_code=201)
def create_evidence(request:EvidenceRequest):
    sources=[v.model_dump(exclude_none=True) for v in request.sources]
    if any(not (('evidence_id' in v and len(v)==1) or ('evidence_id' not in v and 'snapshot_id' in v and 'run_id' in v)) for v in sources): raise HTTPException(422,"Provide evidence_id OR snapshot_id/run_id/optional metric")
    try:return evidence.add(request.kind,request.label,sources)
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.get("/api/evidence")
def research_evidence(): return evidence.listing()
@app.get("/api/evidence/{evidence_id}/trace")
def trace_evidence(evidence_id:str):
    try:return evidence.trace(evidence_id)
    except KeyError:raise HTTPException(404,"Evidence not found")
from .tracking.engine import Engine
_tracker=None
def tracking_engine():
    global _tracker
    target=storage.DB/'tracking.sqlite'
    if _tracker is None or _tracker.db!=target: _tracker=Engine(target)
    return _tracker
class TrackingProject(BaseModel):
    path:str
    ignores:List[str]=Field(default_factory=list,max_length=100)
@app.post("/api/tracking/projects",status_code=201)
def track_project(request:TrackingProject):
    try:return {"id":tracking_engine().register(request.path,request.ignores)}
    except ValueError as e:raise HTTPException(422,str(e))
@app.get("/api/tracking/health")
def tracking_health():return tracking_engine().diagnostics()
@app.post("/api/tracking/reconcile")
def reconcile_tracking():
    tracking_engine().scan()
    return tracking_engine().diagnostics()
@app.get("/api/tracking/runs/{run_id}/metrics")
def tracking_metrics(run_id:str):return tracking_engine().observations(run_id)
from .orchestrator import Orchestrator
_executor=None
def execution_engine():
    global _executor
    target=(storage.DB/'execution').resolve()
    if _executor is None or _executor.home!=target:_executor=Orchestrator(target,on_enqueue=lambda folder:tracking_engine().register(folder))
    return _executor
class ExecutionSpec(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    argv:List[str]=Field(min_length=1,max_length=100)
    cwd:str
    env:dict[str,str]=Field(default_factory=dict)
    params:dict=Field(default_factory=dict)
    dependencies:List[str]=Field(default_factory=list,max_length=50)
    priority:int=Field(default=0,ge=-100,le=100)
    timeout_seconds:float=Field(default=3600,gt=0,le=604800)
    soft_memory_mb:Optional[float]=Field(default=None,gt=0,le=1048576)
    log_limit_mb:float=Field(default=100,gt=0,le=10240)
    code_files:List[str]=Field(default_factory=list,max_length=50)
@app.post("/api/executions",status_code=201)
def create_execution(spec:ExecutionSpec):
    try:return execution_engine().create(spec.model_dump())
    except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
@app.get("/api/executions")
def executions(limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:raise HTTPException(422,"Invalid pagination")
    return execution_engine().listing(limit,offset)
@app.get("/api/executions/{id}")
def execution(id:str):
    try:return execution_engine().get(id)
    except KeyError:raise HTTPException(404,"Execution not found")
@app.post("/api/executions/{id}/{action}")
def execution_action(id:str,action:Literal["start","cancel","rerun","pause"]):
    try:
        engine=execution_engine()
        if action=='pause':raise HTTPException(409,"Pause is not supported by this executor")
        if action=='start':
            folder=Path(engine.get(id)['output_dir']);folder.mkdir(parents=True,exist_ok=True)
            tracking_engine().register(folder)
            return engine.enqueue(id)
        if action=='cancel':return engine.cancel(id)
        return engine.create(engine.get(id)['spec'])
    except KeyError:raise HTTPException(404,"Execution not found")
    except ValueError as e:raise HTTPException(409,str(e))
@app.get("/api/executions/{id}/logs")
def execution_logs(id:str,stream:Literal["stdout","stderr"]="stdout",offset:int=0,limit:int=65536):
    if offset<0 or not 1<=limit<=1048576:raise HTTPException(422,"Invalid log bounds")
    try:return execution_engine().logs(id,stream,offset,limit)
    except KeyError:raise HTTPException(404,"Execution not found")
from . import statistics_engine
class AnalysisRef(BaseModel):
    snapshot_id:int
    run_id:str
    metric:str
class PairedAnalysis(BaseModel):
    left:List[AnalysisRef]=Field(min_length=3,max_length=1000)
    right:List[AnalysisRef]=Field(min_length=3,max_length=1000)
    independent_pairs:bool=False
    normal_differences:bool=False
    bootstrap_seed:int=0
@app.post("/api/analyses/describe")
def describe_analysis(ref:AnalysisRef):
    try:return statistics_engine.describe(ref.model_dump())
    except (KeyError,ValueError) as e:raise HTTPException(422,str(e))
@app.post("/api/analyses/paired")
def paired_analysis(request:PairedAnalysis):
    try:return statistics_engine.paired([r.model_dump() for r in request.left],[r.model_dump() for r in request.right],request.independent_pairs,request.normal_differences,request.bootstrap_seed)
    except (KeyError,ValueError) as e:raise HTTPException(422,str(e))
@app.get("/api/analyses/{id}")
def analysis_record(id:str):
    try:return statistics_engine.get(id)
    except KeyError:raise HTTPException(404,"Analysis not found")
@app.get("/api/projects/{id}/package")
def evidence_package(id:int):
    from .packages import bundle
    snapshot(id)
    return Response(bundle(id),media_type="application/zip",headers={"Content-Disposition":f'attachment; filename="researchaudit-{id}.zip"'})
@app.get("/api/projects/{id}/report-export")
def report_export(id:int,format:Literal["html","json"]="html"):
    import html
    s=snapshot(id)
    if format=='json':return {"snapshot":s,"audit":audit(s),"figures":storage.figures(id)}
    from .reports import render
    content=html.escape(render(s,id,storage.figures(id)))
    return Response('<!doctype html><meta charset="utf-8"><title>ResearchAudit report</title><style>body{max-width:1000px;margin:40px auto;font:14px system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>ResearchAudit evidence report</h1><pre>'+content+'</pre>',media_type="text/html")
class GridExecution(BaseModel):
    spec:ExecutionSpec
    grid:dict[str,List[Union[str,int,float]]]
@app.post("/api/execution-grid",status_code=201)
def execution_grid(request:GridExecution):
    import itertools,math
    if not request.grid or any(not v for v in request.grid.values()) or math.prod(len(v) for v in request.grid.values())>100:raise HTTPException(422,"Grid must contain 1..100 combinations")
    keys=list(request.grid);created=[]
    for values in itertools.product(*(request.grid[k] for k in keys)):
        spec=request.spec.model_dump();parameters=dict(zip(keys,values));spec['params'].update(parameters)
        for key,value in parameters.items():spec['argv']=[arg.replace('{'+key+'}',str(value)) for arg in spec['argv']]
        try:created.append(execution_engine().create(spec))
        except (ValueError,KeyError) as e:raise HTTPException(422,str(e))
    return {"runs":created,"state":"Pending","note":"Explicit start required for every generated run"}
from .v2.router import router as v2_router
app.include_router(v2_router)
from .v3.router import router as v3_router
app.include_router(v3_router)
if Path("frontend/dist").exists(): app.mount("/",StaticFiles(directory="frontend/dist",html=True),name="ui")
