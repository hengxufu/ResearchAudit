"""Durable versioned DAG execution. Only explicitly started workflows run commands.

Coordination is serial per DAG; ready command nodes share the bounded executor.
Restart marks an unfinished workflow Interrupted rather than replaying side effects.
"""
import copy,json,re,threading,time,uuid
from pathlib import Path
from . import documents
from .. import storage,statistics_engine

KINDS={'command','import','describe','batch','audit','figure','report','balance','asset_verify'}
TERMINAL={'Succeeded','Failed','Cancelled','Interrupted'}

def has_reference(value):
    if isinstance(value,dict):return '$ref' in value or any(has_reference(v) for v in value.values())
    return isinstance(value,list) and any(has_reference(v) for v in value)

def validate(definition):
    nodes=definition.get('nodes',[])
    if not 1<=len(nodes)<=100:raise ValueError('Workflow requires 1..100 nodes')
    ids=[n['id'] for n in nodes]
    if len(set(ids))!=len(ids) or any(not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',i) for i in ids):raise ValueError('Unique node ids must use 1..80 ASCII letters, digits, underscore or hyphen')
    edges={n['id']:set(n.get('depends_on',[])) for n in nodes}
    for n in nodes:
        if n['kind'] not in KINDS:raise ValueError('Unknown node kind')
        if not edges[n['id']]<=set(ids):raise ValueError('Unknown dependency')
        if not isinstance(n.get('retries',0),int) or not 0<=n.get('retries',0)<=2:raise ValueError('Retries must be 0..2')
        condition=n.get('condition')
        if condition and (condition.get('node') not in edges[n['id']] or condition.get('op') not in ('eq','ne','lt','le','gt','ge')):raise ValueError('Condition must reference a direct dependency with a supported operator')
        if n['kind']=='command' and not has_reference(n['config']):
            from ..main import ExecutionSpec
            ExecutionSpec.model_validate(n['config'])
    visited=set()
    while len(visited)<len(ids):
        ready={i for i,deps in edges.items() if i not in visited and deps<=visited}
        if not ready:raise ValueError('Workflow contains a cycle')
        visited|=ready
    return definition

def save(definition,id=None,revision=0):return documents.save('workflow',validate(definition),id,revision)

def pick(value,path):
    for part in path.split('.') if path else []:value=value[int(part)] if isinstance(value,list) else value[part]
    return value

def resolve(value,results,dependencies):
    if isinstance(value,dict) and set(value)=={'$ref'}:
        node,_,path=value['$ref'].partition('.')
        if node not in dependencies:raise ValueError('References must target a direct dependency')
        return pick(results[node]['output'],path)
    if isinstance(value,dict):return {k:resolve(v,results,dependencies) for k,v in value.items()}
    if isinstance(value,list):return [resolve(v,results,dependencies) for v in value]
    return value

class WorkflowEngine:
    def __init__(self,executor):
        self.executor=executor;self.lock=threading.RLock();self.workers={};self.stopping=False
        with storage.connect() as c:
            documents.setup(c)
            c.execute('INSERT OR IGNORE INTO schema_migrations(version) VALUES (3)')

    def get(self,id):
        with storage.connect() as c:row=c.execute('SELECT workflow_id,revision,state,created,finished,payload FROM workflow_runs WHERE id=?',(id,)).fetchone()
        if not row:raise KeyError(id)
        return {'id':id,'workflow_id':row[0],'revision':row[1],'state':row[2],'created':row[3],'finished':row[4],**json.loads(row[5])}

    def listing(self,limit=100,offset=0):
        with storage.connect() as c:ids=[r[0] for r in c.execute('SELECT id FROM workflow_runs ORDER BY created DESC LIMIT ? OFFSET ?',(limit,offset))]
        return [self.get(i) for i in ids]

    def write(self,id,payload,state='Running'):
        # Cancellation and recovery cannot be overwritten by a late worker.
        with storage.connect() as c:
            c.execute("UPDATE workflow_runs SET state=?,finished=?,payload=? WHERE id=? AND state='Running'",(state,time.time() if state in TERMINAL else None,json.dumps(payload,allow_nan=False),id))

    def recover(self):
        self.stopping=False
        with storage.connect() as c:c.execute("UPDATE workflow_runs SET state='Interrupted',finished=? WHERE state='Running'",(time.time(),))

    def start(self,workflow_id,revision,confirmed):
        if not confirmed:raise ValueError('Explicit confirmation required: workflow may execute commands')
        with self.lock:
            if self.stopping:raise ValueError('Workflow service is stopping')
            if len(self.workers)>=4:raise ValueError('At most four active workflows')
            definition=documents.get('workflow',workflow_id,revision);validate(definition);id=uuid.uuid4().hex
            nodes={n['id']:{'state':'Pending','attempts':0,'execution_ids':[]} for n in definition['nodes']}
            payload={'nodes':nodes,'definition_sha256':definition['sha256']}
            with storage.connect() as c:c.execute('INSERT INTO workflow_runs VALUES (?,?,?,?,?,?,?)',(id,workflow_id,definition['revision'],'Running',time.time(),None,json.dumps(payload)))
            worker=threading.Thread(target=self.run,args=(id,definition,payload),daemon=True);self.workers[id]=worker;worker.start()
        return self.get(id)

    def cancel(self,id):
        with self.lock:
            run=self.get(id)
            if run['state']!='Running':return run
            with storage.connect() as c:c.execute("UPDATE workflow_runs SET state='Cancelled',finished=? WHERE id=? AND state='Running'",(time.time(),id))
            for node in run['nodes'].values():
                for execution in node['execution_ids']:self.executor.cancel(execution)
        return self.get(id)

    def stop(self):
        with self.lock:self.stopping=True;ids=list(self.workers)
        for id in ids:self.cancel(id)
        for worker in list(self.workers.values()):worker.join(timeout=10)

    def run(self,id,definition,payload):
        results=payload['nodes']
        try:
            while self.get(id)['state']=='Running':
                for node in definition['nodes']:
                    result=results[node['id']];deps=node.get('depends_on',[])
                    if result['state'] in ('Succeeded','Failed','Skipped','Blocked'):continue
                    if any(results[d]['state'] in ('Failed','Skipped','Blocked') for d in deps):result['state']='Blocked';continue
                    if any(results[d]['state']!='Succeeded' for d in deps):continue
                    try:
                        if result['state']=='Pending':
                            result['attempts']+=1
                            condition=node.get('condition')
                            if condition:
                                actual=pick(results[condition['node']]['output'],condition.get('path',''));expected=condition['value']
                                import operator
                                if not getattr(operator,condition['op'])(actual,expected):result['state']='Skipped';continue
                            config=resolve(node.get('config',{}),results,set(deps))
                            if node['kind']=='command':
                                from ..main import ExecutionSpec
                                spec=ExecutionSpec.model_validate(config).model_dump()
                                # Serialize reservation and cancellation so no command escapes cancellation.
                                with self.lock:
                                    if self.get(id)['state']!='Running':return
                                    execution=self.executor.create(spec);result['execution_ids'].append(execution['id']);result['state']='Running';self.write(id,payload)
                                    self.executor.enqueue(execution['id'])
                            else:
                                result['output']=self.perform(node['kind'],config,id,node['id']);result['state']='Succeeded'
                        if node['kind']=='command' and result['state']=='Running':
                            execution=self.executor.get(result['execution_ids'][-1])
                            if execution['state']=='Succeeded':
                                snapshot=storage.get(execution['snapshot_id'])
                                result.update(state='Succeeded',output={'execution_id':execution['id'],'snapshot_id':execution['snapshot_id'],'output_dir':execution['output_dir'],'runs':[{'run_id':r['id'],'name':r['name'],'metrics':r['metrics']} for r in snapshot['runs']]})
                            elif execution['state'] in TERMINAL:raise ValueError(execution.get('error') or execution['state'])
                    except Exception as error:
                        result['error']=str(error);result['state']='Pending' if result['attempts']<=node.get('retries',0) else 'Failed'
                    self.write(id,payload)
                if all(r['state'] in ('Succeeded','Failed','Skipped','Blocked') for r in results.values()):
                    self.write(id,payload,'Failed' if any(r['state'] in ('Failed','Blocked') for r in results.values()) else 'Succeeded');return
                time.sleep(.1)
        except Exception as error:
            payload['error']=str(error);self.write(id,payload,'Failed')
        finally:
            with self.lock:self.workers.pop(id,None)

    def perform(self,kind,config,workflow_id,node_id):
        if kind=='import':
            from ..collect import scan
            s=scan(config['path']);sid=storage.save(s['root'],s);return {'snapshot_id':sid,'runs':[{'run_id':r['id'],'name':r['name'],'metrics':r['metrics']} for r in s['runs']]}
        if kind=='describe':return statistics_engine.describe(config)
        if kind=='batch':
            from ..v2.analysis import batch
            return batch(config['refs'],config.get('group_by',['model_version']),config.get('seed',0))
        if kind=='audit':
            from ..v2.audit import execute
            return execute(config['snapshot_id'],config.get('full_hash',False),config.get('bounds',[]))
        if kind=='balance':
            from .suites import balance
            return balance(**config)
        if kind=='asset_verify':
            from ..v2.assets import verify
            return verify(config['version_id'])
        folder=storage.DB/'workflows'/workflow_id;folder.mkdir(parents=True,exist_ok=True)
        if kind=='figure':
            from ..figures import export
            fmt=config.get('format','svg');data,spec=export(storage.get(config['snapshot_id']),config['metric'],config.get('kind','curve'),fmt);storage.save_figure(config['snapshot_id'],spec)
            path=folder/(node_id.encode().hex()+'.'+fmt);path.write_bytes(data)
            return {'figure_id':spec['id'],'path':str(path),'bytes':len(data)}
        if kind=='report':
            from ..v2.reporting import pdf
            data=pdf(config['snapshot_id']);path=folder/(node_id.encode().hex()+'.pdf');path.write_bytes(data)
            return {'path':str(path),'bytes':len(data),'snapshot_id':config['snapshot_id']}
        raise ValueError('Unsupported workflow node')
