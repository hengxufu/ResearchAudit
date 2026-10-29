"""Capture bounded runner and entry-code evidence without executing extra project code."""
import hashlib,importlib.metadata,json,os,platform,sys,shutil
from pathlib import Path
from ..collect import git

def capture(cwd,argv,declared_files=None):
    root=Path(cwd).resolve();files=list(declared_files or [])
    if len(argv)>1 and argv[1].endswith(('.py','.cpp','.c')):files.append(argv[1])
    evidence=[]
    for value in dict.fromkeys(files):
        p=(root/value).resolve()
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size>1024*1024:continue
        data=p.read_bytes();evidence.append({'path':str(p.relative_to(root)),'sha256':hashlib.sha256(data).hexdigest(),'text':data.decode('utf-8',errors='replace')})
    versions={}
    for name in ('numpy','scipy','torch','tensorboard','h5py'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    patch=git(root,'diff','--no-ext-diff','--no-textconv','HEAD','--',*(e['path'] for e in evidence)) if evidence else None
    target=Path(argv[0])
    if not target.is_absolute():target=(root/target) if (root/target).is_file() else Path(shutil.which(str(target)) or str(target))
    executable={'requested':argv[0],'resolved':str(target.resolve()) if target.is_file() else None,'sha256':None}
    if target.is_file():
        executable['bytes']=target.stat().st_size
        if executable['bytes']<=16*1024*1024:executable['sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    return {'schema':'reproduction-environment-v1','runner':{'python':sys.version,'python_compiler':platform.python_compiler(),'executable':sys.executable,'platform':platform.platform(),'machine':platform.machine(),'logical_cpus':os.cpu_count(),'selected_distributions':versions},'target_executable':executable,'git':{'commit':git(root,'rev-parse','HEAD'),'branch':git(root,'rev-parse','--abbrev-ref','HEAD'),'status':git(root,'status','--porcelain'),'entry_patch':patch[:1048576] if patch else patch,'patch_truncated':bool(patch and len(patch)>1048576)},'entry_code':evidence,'code_scope':'Explicit/entry files only; imports and toolchain not exhaustively captured','target_environment_status':'UNKNOWN','target_environment_reason':'Runner package versions do not certify another executable or full target dependency closure'}
