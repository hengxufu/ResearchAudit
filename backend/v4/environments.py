"""Environment declarations vs observed runner. Never installs or executes imports."""
import hashlib,importlib.metadata,platform,re,sys
from pathlib import Path
import yaml
from ..core import documents

def runner():
    packages={}
    for d in importlib.metadata.distributions():
        name=d.metadata.get('Name')
        if name:packages[re.sub('[-_.]+','-',name).lower()]=d.version
    return {'python':platform.python_version(),'executable':sys.executable,'platform':platform.platform(),'python_compiler':platform.python_compiler(),'packages':packages,'cuda_driver_gpu_status':'UNKNOWN','scope':'Observed service process, not a certificate for a different target executable'}

def declaration(path,kind):
    p=Path(path).resolve()
    if not p.is_file() or p.stat().st_size>1024*1024:raise ValueError('Declaration file must be <=1 MiB')
    raw=p.read_bytes();text=raw.decode('utf-8-sig');items=[];unresolved=[]
    if kind=='conda':
        obj=yaml.safe_load(text)
        if not isinstance(obj,dict) or not isinstance(obj.get('dependencies'),list):raise ValueError('Conda dependencies list required')
        for dep in obj['dependencies']:
            if isinstance(dep,dict):items.extend(dep.get('pip',[]))
            elif isinstance(dep,str):
                match=re.fullmatch(r'([\w.-]+)=([^=<>! ]+)(?:=.+)?',dep)
                if match and match[1]!='python':items.append(match[1]+'=='+match[2])
                else:unresolved.append(dep)
    else:items=text.splitlines()
    packages={}
    for item in items:
        if not isinstance(item,str):raise ValueError('Dependency entries must be strings')
        item=item.strip()
        if not item or item.startswith('#'):continue
        m=re.fullmatch(r'([A-Za-z0-9_.-]+)==([^ ;]+)(?:\s+#.*)?',item)
        if not m:unresolved.append(item);continue
        key=re.sub('[-_.]+','-',m[1]).lower()
        if key in packages and packages[key]!=m[2]:raise ValueError('Conflicting exact dependency pins')
        packages[key]=m[2]
    return documents.save('environment_declaration',{'path':str(p),'kind':kind,'source_sha256':hashlib.sha256(raw).hexdigest(),'packages':packages,'unresolved':unresolved,'status':'DECLARED','scope':'Parsed declaration only; conda binaries/build/channel compatibility not verified'})

def compare(id):
    expected=documents.get('environment_declaration',id);actual=runner();differences=[]
    for name,version in expected['packages'].items():
        observed=actual['packages'].get(name);differences.append({'package':name,'declared':version,'observed_runner':observed,'status':'PASS' if observed==version else 'FAIL'})
    return documents.save('environment_comparison',{'declaration_id':id,'declaration_revision':expected['revision'],'runner':actual,'differences':differences,'declaration_match':'FAIL' if any(r['status']=='FAIL' for r in differences) else 'UNKNOWN' if expected['unresolved'] or not differences else 'PASS','target_environment_consistency':'UNKNOWN','scientific_reproduction':'UNKNOWN'})

def reproduction_diff(id):
    manifest=documents.get('reproduction',id);context=manifest.get('environment') or {};recorded=context.get('runner',{});before=recorded.get('distributions') or recorded.get('selected_distributions') or {};after=runner()
    differences=[{'package':k,'recorded_runner':v,'current_runner':after['packages'].get(k)} for k,v in before.items() if v!=after['packages'].get(k)]
    return documents.save('environment_comparison',{'manifest_id':id,'manifest_revision':manifest['revision'],'source_execution':manifest['source_execution'],'differences':differences,'recorded_package_count':len(before),'runner_package_match':'FAIL' if differences else 'PASS' if before else 'UNKNOWN','target_environment_consistency':'UNKNOWN','scientific_reproduction':'UNKNOWN','scope':'Observed service package comparison only; missing native dependencies, drivers and target closure are not certified'})

def target_manifest(id,executable):
    source=documents.get('reproduction',id);path=Path(executable)
    if not path.is_absolute() or not path.is_file():raise ValueError('Existing absolute target executable required')
    payload={k:v for k,v in source.items() if k not in ('id','revision','created','sha256')}
    payload['spec']={**source['spec'],'argv':[str(path.resolve()),*source['spec']['argv'][1:]]}
    payload.update(execution=None,status='Draft',parent_manifest_id=id,parent_manifest_revision=source['revision'],target_override={'executable':str(path.resolve()),'scope':'Caller-selected executable; explicit launch plus code-change override required. Target dependencies not certified.'})
    return documents.save('reproduction',payload)
