"""Evidence-backed, explicitly bounded scientific checks."""
import numpy as np

def vector(values,name):
    a=np.asarray(values,dtype=float)
    if a.ndim!=1 or len(a)<2 or not np.isfinite(a).all(): raise ValueError(name+': at least two finite observations required')
    return a

def energy(values,atol,rtol):
    a=vector(values,'energy')
    if atol<0 or rtol<0 or not np.isfinite([atol,rtol]).all(): raise ValueError('Finite nonnegative tolerances required')
    residual=a-a[0];bound=atol+rtol*abs(a[0])
    return {'status':'PASS' if np.max(np.abs(residual))<=bound else 'FAIL','max_absolute_residual':float(np.max(np.abs(residual))),'tolerance':float(bound),'residuals':residual.tolist(),'method':'E(t)-E(0); closed-system assumption supplied by caller','scope':'Numerical drift only; external work/flux must be accounted for before use'}

def convergence(spacing,errors):
    h=vector(spacing,'spacing');e=vector(errors,'error')
    if len(h)!=len(e) or len(h)<3 or np.any(h<=0) or np.any(e<=0) or len(set(h))!=len(h): raise ValueError('At least three distinct positive resolutions and aligned positive reference errors required')
    order=np.argsort(h);h=h[order];e=e[order]
    slope,intercept=np.polyfit(np.log(h),np.log(e),1)
    prediction=slope*np.log(h)+intercept;total=np.sum((np.log(e)-np.mean(np.log(e)))**2)
    return {'status':'PASS' if np.all(np.diff(e)>0) and slope>0 else 'WARN','observed_order':float(slope),'r_squared':float(1-np.sum((np.log(e)-prediction)**2)/total) if total>0 else None,'method':'OLS log(reference error) vs log(grid spacing)','scope':'Empirical reference-error trend; asymptotic regime not established'}

def sensitivity(x,y):
    x=vector(x,'parameter');y=vector(y,'response')
    if len(x)!=len(y) or len(set(x))!=len(x): raise ValueError('Distinct aligned parameter values required')
    order=np.argsort(x);x=x[order];y=y[order]
    return {'status':'UNKNOWN','parameter':x.tolist(),'response':y.tolist(),'secant_slopes':(np.diff(y)/np.diff(x)).tolist(),'method':'Adjacent secants, one parameter varied','scope':'No causal or global sensitivity claim; other conditions must be controlled'}

def propagation(coefficients,covariance,units):
    c=np.asarray(coefficients,dtype=float);cov=np.asarray(covariance,dtype=float)
    if c.ndim!=1 or not len(c) or cov.shape!=(len(c),len(c)) or len(units)!=len(c) or any(not u.strip() for u in units): raise ValueError('Coefficient/covariance dimensions and explicit coefficient-product units required')
    if len(set(units))!=1: raise ValueError('All coefficient-times-input units must agree; convert before submitting')
    if not np.isfinite(c).all() or not np.isfinite(cov).all() or not np.allclose(cov,cov.T,rtol=1e-12,atol=1e-15): raise ValueError('Finite symmetric covariance required')
    eigen=np.linalg.eigvalsh(cov)
    if eigen.min() < -1e-12*max(1,float(np.max(np.abs(eigen)))): raise ValueError('Covariance must be positive semidefinite')
    variance=float(c@cov@c)
    return {'status':'PASS','standard_uncertainty':float(np.sqrt(max(0,variance))),'unit':units[0],'method':'Exact linear model variance c^T covariance c','scope':'Standard uncertainty, k=1; no coverage probability or nonlinear adequacy claim'}
