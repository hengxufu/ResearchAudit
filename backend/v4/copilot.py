"""Allowlisted deterministic tools. No arbitrary query, code or network operations."""
from .. import storage,statistics_engine
from ..v3 import intelligence
from ..v2 import audit
TOOLS={'query','summary','audit','analysis_plan'}
def run(snapshot_id,operation,text=''):
    if operation not in TOOLS:raise ValueError('Unsupported Copilot tool')
    s=storage.get(snapshot_id);refs=[{'snapshot_id':snapshot_id,'run_id':r['id']} for r in s['runs']]
    if len(refs)>500:raise ValueError('Select a snapshot with <=500 runs for this tool')
    if operation=='query':output=intelligence.query(snapshot_id,text)
    elif operation=='summary':output=intelligence.summarize(snapshot_id,[r['run_id'] for r in refs])
    elif operation=='audit':output=audit.execute(snapshot_id,False,[])
    else:output={'plan':['Check metric direction/unit/method and dataset/split/protocol compatibility.','Declare independent Run or matched seed block as the experimental unit.','Select stratified or repeated-block bootstrap; specify resamples and seed.','Inspect source anomalies, missingness and assumptions before interpreting uncertainty.'],'status':'PLAN_NOT_EXECUTED','run_refs':refs}
    return statistics_engine.persist({'method':'copilot-allowlisted-tools-v1','inputs':{'snapshot_id':snapshot_id,'operation':operation,'text':text},'result':output,'sources':refs,'unit':'Deterministic local tool result','model':'none','network':'disabled','scope':'No ungrounded interpretation; language-model provider execution is not enabled'})
