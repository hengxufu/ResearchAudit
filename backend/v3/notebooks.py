"""Read stored Jupyter outputs as evidence; never execute cells or render HTML."""
import hashlib,json
from .data_studio import resolve
from ..statistics_engine import persist

def read(asset_id,path):
    p=resolve(asset_id,path)
    if p.suffix!='.ipynb' or p.stat().st_size>10*1024*1024:raise ValueError('Notebook JSON must be .ipynb and <=10 MiB')
    data=p.read_bytes();notebook=json.loads(data)
    if notebook.get('nbformat')!=4 or not isinstance(notebook.get('cells'),list):raise ValueError('Notebook format 4 required')
    if len(notebook['cells'])>1000:raise ValueError('Notebook preview capped at 1000 cells')
    cells=[]
    for index,cell in enumerate(notebook['cells']):
        if cell.get('cell_type')!='code':continue
        text=cell.get('source',[]);text=''.join(text) if isinstance(text,list) else str(text)
        outputs=[]
        for o in cell.get('outputs',[])[:100]:
            if o.get('output_type')=='stream':outputs.append({'stream':o.get('name'),'text':''.join(o.get('text',[]))[:8000]})
            elif o.get('output_type') in ('display_data','execute_result'):
                safe={k:v for k,v in o.get('data',{}).items() if k in ('text/plain','application/json')};outputs.append({'data':safe})
            elif o.get('output_type')=='error':outputs.append({'error':o.get('ename'),'value':o.get('evalue')})
        cells.append({'index':index,'execution_count':cell.get('execution_count'),'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'source':text[:8000],'outputs':outputs})
    return persist({'method':'jupyter-stored-output-import-v1','inputs':{'asset_id':asset_id,'path':path},'result':cells,'sources':[{'path':path,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}],'unit':'Stored notebook evidence only; execution order, environment and truth not verified','status':'UNKNOWN'})
