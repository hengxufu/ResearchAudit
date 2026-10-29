import numpy as np
# Registry accepts plugins returning serializable evidence from supplied arrays.
REGISTRY={}
def register(name):
    def wrap(fn): REGISTRY[name]=fn; return fn
    return wrap
@register("conservation")
def conservation(values):
    a=np.asarray(values,dtype=float)
    if a.size<2 or not np.isfinite(a).all(): raise ValueError("At least two finite observations required")
    return {"initial":float(a[0]),"max_absolute_drift":float(np.max(np.abs(a-a[0]))),"relative_drift":float(np.max(np.abs(a-a[0]))/abs(a[0])) if a[0]!=0 else None}
