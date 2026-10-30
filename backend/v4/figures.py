"""Saved multipanel recipes referencing immutable data. Render without code execution."""
from io import BytesIO
import hashlib
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from ..figures import LOCK
from .. import statistics_engine as registry
from ..v3 import documents

def save(panels,title):
    for panel in panels:
        if panel.get('xlim') is not None and (len(panel['xlim'])!=2 or not np.isfinite(panel['xlim']).all() or panel['xlim'][0]>=panel['xlim'][1]):raise ValueError('Increasing finite two-value xlim required')
        for ref in panel['refs']:registry.source(ref)
    return documents.save('figure_recipe',{'panels':panels,'title':title,'renderer':'matplotlib-multipanel-v1','scope':'Raw data plus explicitly declared display transforms; raw metrics unchanged'})

def render(id,format):
    recipe=documents.get('figure_recipe',id)
    with LOCK:
        figure=Figure(figsize=(8,3*len(recipe['panels'])),layout='constrained');FigureCanvasAgg(figure);axes=np.atleast_1d(figure.subplots(len(recipe['panels']),1))
        for ax,panel in zip(axes,recipe['panels']):
            for ref in panel['refs']:
                _,run=registry.source(ref);raw=run['series'].get(ref['metric'])
                if not raw:raise ValueError('Source curve required')
                y=np.array([np.nan if v is None else v for v in raw]);x=np.asarray(run['series'].get(ref['metric']+'/step',range(len(y))))
                if panel['scale']=='log' and np.any(y[np.isfinite(y)]<=0):raise ValueError('Log scale requires positive observations')
                ax.plot(x,y,alpha=.35 if panel['smooth']>1 else 1,label=run['name']+' raw')
                if panel['smooth']>1:
                    w=panel['smooth'];smoothed=[np.mean(y[max(0,i-w+1):i+1]) for i in range(len(y))];ax.plot(x,smoothed,label=run['name']+' trailing mean w='+str(w))
            ax.set_yscale(panel['scale']);ax.set_title(panel['label']);ax.set_xlabel('Recorded step / observation');ax.legend();ax.grid(alpha=.2)
            if panel.get('xlim'):ax.set_xlim(*panel['xlim'])
        figure.suptitle(recipe['title']);out=BytesIO();figure.savefig(out,format=format,dpi=200);data=out.getvalue()
    return data,hashlib.sha256(data).hexdigest()
