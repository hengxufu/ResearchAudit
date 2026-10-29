"""Publication exports from immutable snapshots; no smoothing of stored values."""
from io import BytesIO
import hashlib,json,threading
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
LOCK=threading.Lock()
def export(snapshot,metric,kind='curve',format='pdf'):
    if format not in ('pdf','png','svg') or kind not in ('curve','distribution'): raise ValueError('Unsupported plot format or kind')
    runs=[r for r in snapshot['runs'] if metric in r['series']]
    if not runs: raise ValueError('No source observations for metric')
    spec={'metric':metric,'kind':kind,'transform':'none','sources':[{'run_id':r['id'],'evidence':r.get('metric_sources',{}).get(metric,r['sources'])} for r in runs]}
    spec['id']=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    with LOCK:
        fig=Figure(figsize=(7.2,4.5),layout='constrained');FigureCanvasAgg(fig);ax=fig.subplots()
        for r in runs:
            values=np.array([np.nan if v is None else v for v in r['series'][metric]],dtype=float)
            if kind=='curve': ax.plot(r['series'].get(metric+'/step',range(len(values))),values,label=r['name'],linewidth=1.5)
            else:
                finite=values[np.isfinite(values)]
                if len(finite): ax.hist(finite,bins='auto',alpha=.45,label=r['name'])
        ax.set_xlabel('Observation / step' if kind=='curve' else metric)
        ax.set_ylabel(metric if kind=='curve' else 'Count')
        ax.set_title(metric+' | '+kind);ax.grid(alpha=.2);ax.legend()
        out=BytesIO();fig.savefig(out,format=format,dpi=300);fig.clear()
    return out.getvalue(),spec
