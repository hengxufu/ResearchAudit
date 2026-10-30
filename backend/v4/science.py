"""Equation-driven thermal audit. Numerical agreement is not model validation."""
import numpy as np
from .. import storage,statistics_engine
SIGMA=5.670374419e-8
def radiation(snapshot_id,run_id,temperature,ambient,power,area_m2,emissivity,atol,rtol):
    s=storage.get(snapshot_id);r=next((r for r in s['runs'] if r['id']==run_id),None)
    if not r:raise ValueError('Unknown run')
    fields=(temperature,ambient,power);units=('K','K','W');columns=[]
    for key,unit in zip(fields,units):
        if r.get('metric_definitions',{}).get(key,{}).get('unit')!=unit:raise ValueError('Explicit matching K/K/W definitions required')
        values=r['series'].get(key)
        if not values or any(v is None for v in values):raise ValueError('Complete finite source columns required')
        columns.append(np.asarray(values,dtype=float))
    if len({len(a) for a in columns})!=1 or not all(np.isfinite(a).all() for a in columns):raise ValueError('Aligned finite arrays required')
    t,a,p=columns
    if np.any(t<0) or np.any(a<0):raise ValueError('Absolute Kelvin temperatures must be nonnegative')
    with np.errstate(over='raise',invalid='raise'):
        try:predicted=emissivity*SIGMA*area_m2*(t**4-a**4);residual=p-predicted
        except FloatingPointError:raise ValueError('Radiation arithmetic overflow; check source values')
    tolerance=atol+rtol*np.abs(predicted)
    return statistics_engine.persist({'method':'stefan-boltzmann-gray-surface-v1','inputs':{'snapshot_id':snapshot_id,'run_id':run_id,'temperature':temperature,'ambient':ambient,'power':power,'area_m2':area_m2,'emissivity':emissivity,'atol_W':atol,'rtol':rtol},'result':{'status':'PASS' if np.all(np.abs(residual)<=tolerance) else 'FAIL','predicted_W':predicted.tolist(),'residual_W':residual.tolist(),'max_absolute_residual_W':float(np.max(np.abs(residual)))},'sources':[{'reference':{'snapshot_id':snapshot_id,'run_id':run_id},'evidence':r['sources']}],'unit':'W','equation':'P=emissivity*sigma*area*(T^4-T_ambient^4)','assumptions':'Diffuse gray surface, prescribed environment, view factor 1, no omitted exchange terms; caller supplied','scientific_model_validity':'UNKNOWN'})
