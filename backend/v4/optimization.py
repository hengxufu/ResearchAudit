"""Bounded historical-data optimization. Suggestions never execute commands."""
import itertools,json,math,threading,time
import numpy as np
from scipy.linalg import cho_factor,cho_solve
from scipy.special import ndtr
from .. import storage,statistics_engine
from ..analysis import compatibility
from ..core import documents
LOCK=threading.RLock()

def propose(refs,metric,space,algorithm,count,budget,seed,constraints):
    rows=[];observed=[];seen=set();keys=sorted(space)
    if not keys or len(keys)>6 or not 1<=count<=budget<=100:raise ValueError('1..6 dimensions and 1 <= count <= budget <=100 required')
    for k,b in space.items():
        if len(b)!=2 or not all(math.isfinite(v) for v in b) or b[0]>=b[1]:raise ValueError('Finite increasing parameter bounds required')
    for ref in refs:
        _,r=statistics_engine.source({**ref,'metric':metric})
        if r['id'] in seen:raise ValueError('Duplicate Run identity')
        seen.add(r['id']);rows.append(r)
        x=[r['params'].get(k) for k in keys];value=r['metrics'][metric]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in x) or value is None or not math.isfinite(value):raise ValueError('Finite numeric observed parameters and objective required')
        observed.append({'reference':ref,'parameters':dict(zip(keys,x)),'value':value,'sources':r['sources']})
    if not rows or compatibility(rows,metric)['status']!='PASS':raise ValueError('Compatible complete evaluation contracts required')
    controls={k for r in rows for k in r['params']} - set(keys) - {'seed','metric_definitions'}
    if any(len({json.dumps(r['params'].get(k),sort_keys=True) for r in rows})>1 for k in controls):raise ValueError('Uncontrolled parameter differences confound the proposed surrogate; filter the source runs')
    direction=rows[0]['metric_definitions'][metric]['direction']
    if direction not in ('minimize','maximize'):raise ValueError('Explicit objective direction required')
    if len(rows)>200:raise ValueError('Surrogate fitting capped at 200 independent Run observations')
    lower=np.array([space[k][0] for k in keys]);width=np.array([space[k][1]-space[k][0] for k in keys]);rng=np.random.default_rng(seed)
    x=(np.array([[o['parameters'][k] for k in keys] for o in observed])-lower)/width
    if np.any(x<0) or np.any(x>1):raise ValueError('Historical parameters outside declared space')
    if algorithm=='grid':
        resolution=min(8,max(2,int(512**(1/len(keys)))));pool=np.array(list(itertools.product(np.linspace(0,1,resolution),repeat=len(keys))))
    else:pool=rng.random((512,len(keys)))
    # Parameter-space linear constraints; no claim of learned outcome feasibility.
    valid=[]
    for p in pool:
        raw=dict(zip(keys,(lower+p*width).tolist()))
        if any(np.max(np.abs(p-o))<1e-10 for o in x):continue
        good=True
        for c in constraints:
            if not set(c['coefficients'])<=set(keys):raise ValueError('Unknown constrained parameter')
            if sum(float(v)*raw[k] for k,v in c['coefficients'].items())>c['upper']:good=False
        if good:valid.append(p)
    if len(valid)<count:raise ValueError('Not enough distinct feasible candidates')
    pool=np.array(valid);means=None;sd=None;acquisition=None
    if algorithm=='bayesian':
        if len(rows)<3 or len(np.unique(x,axis=0))<3:raise ValueError('At least three distinct parameter locations required for GP')
        y=np.array([o['value'] for o in observed]);scale=float(y.std())
        if scale<1e-12:raise ValueError('Constant objective: surrogate uncertainty cannot be calibrated')
        target=(y-y.mean())/scale
        if direction=='maximize':target=-target
        def kernel(a,b):return np.exp(-.5*np.sum(((a[:,None]-b[None,:])/.25)**2,axis=2))
        factor=cho_factor(kernel(x,x)+np.eye(len(x))*1e-6,lower=True);cross=kernel(pool,x);mu=cross@cho_solve(factor,target);variance=np.maximum(0,1-np.sum(cross*cho_solve(factor,cross.T).T,axis=1));sd=np.sqrt(variance)
        improvement=target.min()-mu-.01;z=np.divide(improvement,sd,out=np.zeros_like(improvement),where=sd>1e-12);acquisition=improvement*ndtr(z)+sd*np.exp(-.5*z*z)/np.sqrt(2*np.pi);acquisition[sd<=1e-12]=0
        order=np.argsort(-acquisition);means=(mu*(-1 if direction=='maximize' else 1))*scale+y.mean();sd=sd*scale
    else:order=rng.permutation(len(pool)) if algorithm=='random' else np.arange(len(pool))
    candidates=[]
    for index in order[:count]:candidates.append({'parameters':dict(zip(keys,(lower+pool[index]*width).tolist())),'predicted_mean':float(means[index]) if means is not None else None,'posterior_sd':float(sd[index]) if sd is not None else None,'expected_improvement_standardized':float(acquisition[index]) if acquisition is not None else None,'state':'Suggested'})
    return documents.save('optimization',{'metric':metric,'direction':direction,'space':space,'algorithm':algorithm,'method_version':'1','seed':seed,'budget':budget,'observations':observed,'candidates':candidates,'constraints':constraints,'control_parameters':{k:rows[0]['params'].get(k) for k in controls},'surrogate':{'kernel':'RBF normalized length_scale=0.25','noise_variance':1e-6,'xi':.01,'hyperparameters':'fixed, not fitted'} if algorithm=='bayesian' else None,'evaluation_contract':{k:rows[0]['params'][k] for k in ('dataset','dataset_version','split','evaluation_protocol')},'metric_definition':rows[0]['metric_definitions'][metric],'scope':'Algorithm suggestions only; GP uncertainty conditional on fixed kernel, not calibrated coverage or optimality guarantee'})

def setup(c):c.execute('CREATE TABLE IF NOT EXISTS optimization_dispatch(proposal_id TEXT,candidate INTEGER,state TEXT,execution_id TEXT,spec TEXT,PRIMARY KEY(proposal_id,candidate))')

def dispatch(engine,id,index,spec,confirmed):
    if not confirmed:raise ValueError('Explicit authorization required')
    with LOCK:
        proposal=documents.get('optimization',id)
        if not 0<=index<len(proposal['candidates']):raise ValueError('Unknown candidate')
        for k,v in proposal.get('control_parameters',{}).items():
            if k in spec.get('params',{}) and spec['params'][k]!=v:raise ValueError('Execution parameters contradict historical controls: '+k)
        spec={**spec,'params':{**proposal.get('control_parameters',{}),**spec.get('params',{}),**proposal['evaluation_contract'],**proposal['candidates'][index]['parameters']}}
        spec['params']['metric_definitions']={**spec['params'].get('metric_definitions',{}),proposal['metric']:proposal['metric_definition']}
        # Substitute only explicit placeholders in an argv array, never a shell.
        for k,v in proposal['candidates'][index]['parameters'].items():spec['argv']=[a.replace('{'+k+'}',str(v)) for a in spec['argv']]
        encoded=json.dumps(spec,sort_keys=True,allow_nan=False)
        with storage.connect() as c:
            setup(c);c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT state,execution_id,spec FROM optimization_dispatch WHERE proposal_id=? AND candidate=?',(id,index)).fetchone()
            if row:
                if row[2]!=encoded:raise ValueError('Candidate already reserved with a different command')
                if row[1]:
                    existing=engine.get(row[1])
                    if existing['state']=='Pending':
                        engine.enqueue(existing['id']);c.execute('UPDATE optimization_dispatch SET state=? WHERE proposal_id=? AND candidate=?',('Started',id,index))
                    return {'execution':engine.get(row[1]),'duplicate_request':True}
                raise ValueError('Interrupted reservation; inspect before manually creating a replacement')
            used=c.execute('SELECT count(*) FROM optimization_dispatch WHERE proposal_id=?',(id,)).fetchone()[0]
            if used>=proposal['budget']:raise ValueError('Execution budget exhausted')
            c.execute('INSERT INTO optimization_dispatch VALUES (?,?,?,?,?)',(id,index,'Reserved',None,encoded))
        run=engine.create(spec)
        with storage.connect() as c:c.execute('UPDATE optimization_dispatch SET state=?,execution_id=? WHERE proposal_id=? AND candidate=?',('Prepared',run['id'],id,index))
        engine.enqueue(run['id'])
        with storage.connect() as c:c.execute('UPDATE optimization_dispatch SET state=? WHERE proposal_id=? AND candidate=?',('Started',id,index))
        return {'execution':engine.get(run['id']),'duplicate_request':False}

def results(engine,id):
    proposal=documents.get('optimization',id);values=[]
    with storage.connect() as c:setup(c);rows=c.execute('SELECT candidate,state,execution_id FROM optimization_dispatch WHERE proposal_id=?',(id,)).fetchall()
    for index,state,execution in rows:
        run=engine.get(execution) if execution else None;observations=[]
        if run and run['state']=='Succeeded' and run['snapshot_id']:
            for r in storage.get(run['snapshot_id'])['runs']:
                if proposal['metric'] in r['metrics']:observations.append({'snapshot_id':run['snapshot_id'],'run_id':r['id'],'value':r['metrics'][proposal['metric']],'sources':r['sources']})
        values.append({'candidate':index,'dispatch_state':state,'execution':run,'observations':observations})
    return {'proposal_id':id,'results':values,'remaining_budget':proposal['budget']-len(rows),'scope':'Actual outputs; no scientific optimality claim'}
