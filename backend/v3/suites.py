"""Explicit convention-aware pose evaluation and equation-based simulation checks."""
import numpy as np
from scipy.spatial.transform import Rotation
from ..statistics_engine import persist
from .. import storage

def training(snapshot_id,metric):
    from ..analysis import compatibility
    s=storage.get(snapshot_id);rows=[]
    for r in s['runs']:
        if metric not in r['metrics']:continue
        values=r.get('series',{}).get(metric,[]);definition=r.get('metric_definitions',{}).get(metric,{});direction=definition.get('direction');finite=[(i,v) for i,v in enumerate(values) if v is not None and np.isfinite(v)]
        best=(min(finite,key=lambda p:p[1]) if direction=='minimize' else max(finite,key=lambda p:p[1])) if finite and direction in ('minimize','maximize') else None
        checkpoints=[f for f in r['sources'] if f['path'].endswith(('.pt','.pth','.ckpt','.onnx','.npz'))]
        execution=r.get('execution',{});duration=execution['process_finished']-execution['started'] if execution.get('process_finished') is not None and execution.get('started') is not None else None
        rows.append({'run_id':r['id'],'parameters':r['params'],'final':r['metrics'][metric],'wall_time_seconds':duration,'resource_scope':'Observed executor wall time only; GPU/device cost not attributed','best_observation':{'index':best[0],'value':best[1]} if best else None,'checkpoint_candidates':checkpoints,'best_checkpoint_status':'UNKNOWN','reason':'A best metric does not establish which checkpoint contains those weights','sources':r['sources']})
    gate=compatibility([r for r in s['runs'] if metric in r['metrics']],metric)
    return persist({'method':'training-history-v1','inputs':{'snapshot_id':snapshot_id,'metric':metric},'result':{'runs':rows,'compatibility':gate},'sources':s['evidence'],'unit':'Original metric definition; best observation index is not necessarily an epoch'})

def simulation_trend(snapshot_id,run_id,x_metric,y_metric,kind):
    from .. import science
    s=storage.get(snapshot_id);r=next((r for r in s['runs'] if r['id']==run_id),None)
    if not r:raise ValueError('Unknown run')
    x=r['series'].get(x_metric);y=r['series'].get(y_metric)
    if x is None or y is None or any(v is None for v in x+y):raise ValueError('Complete source columns required')
    definitions=r.get('metric_definitions',{})
    if any(not definitions.get(k,{}).get('unit') for k in (x_metric,y_metric)):raise ValueError('Explicit source units required')
    result=science.convergence(x,y) if kind=='convergence' else science.sensitivity(x,y)
    return persist({'method':kind+'-source-columns-v1','inputs':{'snapshot_id':snapshot_id,'run_id':run_id,'x_metric':x_metric,'y_metric':y_metric},'result':result,'sources':[{'reference':{'snapshot_id':snapshot_id,'run_id':run_id},'evidence':r['sources']}],'unit':{k:definitions[k]['unit'] for k in (x_metric,y_metric)}})

def pose(snapshot_id,run_id,columns,quaternion_order,convention,frame,translation_unit,failure_rotation_degrees=None,failure_translation=None):
    s=storage.get(snapshot_id);r=next((r for r in s['runs'] if r['id']==run_id),None)
    if r is None:raise ValueError('Unknown run')
    if quaternion_order not in ('xyzw','wxyz') or convention not in ('active','passive') or not frame.strip() or not translation_unit.strip():raise ValueError('Explicit quaternion order, active/passive convention, coordinate frame and translation unit required')
    names=[*columns['truth_quaternion'],*columns['prediction_quaternion'],*columns['truth_translation'],*columns['prediction_translation']]
    if len(columns['truth_quaternion'])!=4 or len(columns['prediction_quaternion'])!=4 or len(columns['truth_translation'])!=3 or len(columns['prediction_translation'])!=3:raise ValueError('Four quaternion and three translation columns per pose required')
    arrays=[r['series'].get(name) for name in names]
    if any(a is None for a in arrays) or len({len(a) for a in arrays})!=1:raise ValueError('Aligned pose columns required')
    if len(arrays[0])>100000:raise ValueError('Pose evaluation capped at 100000 observations per analysis')
    if any(v is None for a in arrays for v in a):raise ValueError('Missing pose values must be resolved before comparison')
    a=np.array(arrays,dtype=float).T
    if not len(a) or not np.isfinite(a).all():raise ValueError('Finite nonempty pose observations required')
    q=a[:,:4];prediction=a[:,4:8]
    if np.any(np.linalg.norm(q,axis=1)<1e-12) or np.any(np.linalg.norm(prediction,axis=1)<1e-12):raise ValueError('Zero quaternion is undefined')
    if quaternion_order=='wxyz':q=q[:,[1,2,3,0]];prediction=prediction[:,[1,2,3,0]]
    angle=(Rotation.from_quat(q).inv()*Rotation.from_quat(prediction)).magnitude()*180/np.pi
    translation=np.linalg.norm(a[:,8:11]-a[:,11:14],axis=1)
    failure=np.zeros(len(a),dtype=bool)
    for values,threshold in ((angle,failure_rotation_degrees),(translation,failure_translation)):
        if threshold is not None:
            if not np.isfinite(threshold) or threshold<0:raise ValueError('Finite nonnegative failure thresholds required')
            failure|=values>threshold
    return persist({'method':'so3-geodesic-and-translation-norm-v1','inputs':{'snapshot_id':snapshot_id,'run_id':run_id,'columns':columns,'quaternion_order':quaternion_order,'convention':convention,'coordinate_frame':frame,'translation_unit':translation_unit,'failure_rotation_degrees':failure_rotation_degrees,'failure_translation':failure_translation},'result':{'rotation_error_degrees':angle.tolist(),'translation_error':translation.tolist(),'mean_rotation_degrees':float(angle.mean()),'mean_translation':float(translation.mean()),'failure_indices':np.flatnonzero(failure).tolist() if failure_rotation_degrees is not None or failure_translation is not None else None,'quaternion_norms_truth':np.linalg.norm(a[:,:4],axis=1).tolist(),'quaternion_norms_prediction':np.linalg.norm(a[:,4:8],axis=1).tolist()},'sources':[{'reference':{'snapshot_id':snapshot_id,'run_id':run_id},'evidence':r['sources']}],'unit':{'rotation':'degree','translation':translation_unit},'scope':'Both poses must already share the declared convention/frame; quaternions normalized by SO(3) conversion; row-index alignment required; no SPEED-specific score assumed'})

def balance(snapshot_id,run_id,energy_metric,power_metric,time_metric,unit_energy,unit_power,unit_time,atol,rtol):
    if not np.isfinite([atol,rtol]).all() or min(atol,rtol)<0:raise ValueError('Nonnegative finite tolerances required')
    if (unit_energy,unit_power,unit_time)!=('J','W','s'):raise ValueError('This equation requires explicit SI J/W/s; convert before use')
    s=storage.get(snapshot_id);r=next((r for r in s['runs'] if r['id']==run_id),None)
    if not r:raise ValueError('Unknown run')
    columns=[r['series'].get(k) for k in (energy_metric,power_metric,time_metric)]
    if any(c is None for c in columns) or len({len(c) for c in columns})!=1 or len(columns[0])<2 or any(v is None for c in columns for v in c):raise ValueError('Aligned complete energy/power/time series required')
    energy,power,t=[np.asarray(c,dtype=float) for c in columns]
    if not all(np.isfinite(c).all() for c in (energy,power,t)) or np.any(np.diff(t)<=0):raise ValueError('Finite observations and strictly increasing time required')
    integral=np.r_[0,np.cumsum(.5*(power[1:]+power[:-1])*np.diff(t))];residual=energy-energy[0]-integral;bound=atol+rtol*max(abs(energy[0]),float(np.max(np.abs(integral))))
    return persist({'method':'energy-balance-trapezoidal-v1','inputs':{'snapshot_id':snapshot_id,'run_id':run_id,'energy_metric':energy_metric,'power_metric':power_metric,'time_metric':time_metric,'units':['J','W','s'],'atol':atol,'rtol':rtol},'result':{'status':'PASS' if np.max(np.abs(residual))<=bound else 'FAIL','residual_J':residual.tolist(),'integrated_net_power_J':integral.tolist(),'max_absolute_residual_J':float(np.max(np.abs(residual))),'tolerance_J':float(bound)},'sources':[{'reference':{'snapshot_id':snapshot_id,'run_id':run_id},'evidence':r['sources']}],'unit':'J','equation':'E(t)-E(0)-integral(P_net dt)=0','assumptions':'P_net includes all signed boundary work, heat, sources and sinks; trapezoidal quadrature; equation/input completeness is caller responsibility'})
