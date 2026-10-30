"""Shared request contracts; version routers must not import each other for these."""
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)

class RunRef(Strict):
    snapshot_id:int
    run_id:str

class MetricRef(RunRef):
    metric:str

def guard(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except KeyError as e:raise HTTPException(404,str(e))
    except (ValueError,TypeError,OSError) as e:raise HTTPException(422,str(e))

def executor():
    from ..main import execution_engine
    return execution_engine()
