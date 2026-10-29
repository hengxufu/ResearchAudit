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
    yield
app=FastAPI(lifespan=lifespan,title="ResearchAudit",version="0.1.0")
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
if Path("frontend/dist").exists(): app.mount("/",StaticFiles(directory="frontend/dist",html=True),name="ui")
