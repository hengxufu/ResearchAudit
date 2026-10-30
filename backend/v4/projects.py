"""Bounded, reference-only project discovery with reviewable inferred associations."""
import ast,fnmatch,hashlib,json,os
from pathlib import Path
import yaml
from ..collect import git,scan,SKIP
from .. import storage
from ..core import documents

def inspect(root,ignores=None,max_files=20000):
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Existing project directory required')
    entries=[];issues=[];experiments={};structures=set();truncated=False
    for directory,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in SKIP and not d.startswith('.test-runs-') and not (Path(directory)/d).is_symlink() and not any(fnmatch.fnmatch(str((Path(directory)/d).relative_to(root)),p) for p in ignores or []))
        for name in sorted(names):
            p=Path(directory)/name;rel=p.relative_to(root).as_posix()
            if p.is_symlink() or any(fnmatch.fnmatch(rel,pat) for pat in ignores or []):continue
            if len(entries)>=max_files:truncated=True;break
            try:
                stat=p.stat();suffix=p.suffix.lower();kind='other';facts={}
                if suffix in ('.py','.cpp','.cc','.c','.h','.hpp'):kind='code';structures.add('Python' if suffix=='.py' else 'C++')
                if name=='CMakeLists.txt':kind='build';structures.add('CMake')
                if suffix=='.ipynb':kind='notebook';structures.add('Jupyter')
                if suffix in ('.pt','.pth','.ckpt','.onnx','.safetensors'):kind='model'
                if suffix in ('.csv','.parquet','.jsonl') or name.startswith('events.out.tfevents'):kind='record'
                if suffix in ('.npz','.npy','.h5','.hdf5','.png','.tif','.jpg','.ply','.obj'):kind='data'
                if suffix in ('.json','.yaml','.yml') and any(w in p.stem.lower() for w in ('config','param')):kind='config'
                entry={'path':rel,'kind':kind,'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns}
                if kind in ('code','config','build') and stat.st_size<=512*1024:
                    raw=p.read_bytes();entry['sha256']=hashlib.sha256(raw).hexdigest();text=raw.decode('utf-8-sig',errors='replace')
                    if suffix=='.py':
                        tree=ast.parse(text);imports=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]+[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
                        facts={'imports':imports,'entry_candidate':any(isinstance(n,ast.If) and '__name__' in (ast.get_source_segment(text,n.test) or '') for n in tree.body)}
                        if any(i.split('.')[0]=='torch' for i in imports):structures.add('PyTorch')
                    if kind=='config':
                        obj=json.loads(text) if suffix=='.json' else yaml.safe_load(text)
                        if isinstance(obj,dict):facts={'parameters':obj,'evaluation_protocol':obj.get('evaluation_protocol'),'metric_definitions':obj.get('metric_definitions',{})}
                entry['facts']=facts;entries.append(entry)
                if kind in ('record','config','model'):
                    parent=p.parent.relative_to(root).as_posix();candidate=experiments.setdefault(parent,{'directory':parent,'files':[],'parameters':{},'basis':'Co-location in one directory; not execution provenance','status':'PENDING_CONFIRMATION'})
                    candidate['files'].append(rel)
                    if kind=='config':candidate['parameters'].update(facts.get('parameters',{}))
            except Exception as e:issues.append({'path':rel,'error':str(e)});entries.append({'path':rel,'kind':'unreadable_or_invalid'})
        if truncated:break
    payload={'root':str(root),'structures':sorted(structures),'files':entries,'candidates':list(experiments.values()),'issues':issues,'truncated':truncated,'git':{'commit':git(root,'rev-parse','HEAD'),'status':git(root,'status','--porcelain'),'recent_history':git(root,'log','-10','--format=%H %aI %s')},'policy':'Read-only bounded discovery. Model/data contents not hashed. Candidates are inferred, not verified.'}
    return documents.save('project_intelligence',payload)

def associate(id,directory,experiment_label,reason,revision):
    doc=documents.get('project_intelligence',id)
    if not any(c['directory']==directory for c in doc['candidates']):raise ValueError('Unknown candidate directory')
    payload={k:v for k,v in doc.items() if k not in ('id','revision','created','sha256')}
    payload.setdefault('curation',[]).append({'directory':directory,'experiment_label':experiment_label,'reason':reason,'basis':'user_declared'})
    return documents.save('project_intelligence',payload,id,revision)

def backfill(id,directories):
    doc=documents.get('project_intelligence',id);root=Path(doc['root']).resolve();results=[]
    known={c['directory'] for c in doc['candidates']}
    for relative in dict.fromkeys(directories):
        if relative not in known:raise ValueError('Choose discovered candidate directories')
        path=(root/relative).resolve()
        if not path.is_relative_to(root):raise ValueError('Directory outside project')
        s=scan(path);results.append({'directory':relative,'snapshot_id':storage.save(s['root'],s),'issues':s['issues']})
    return documents.save('project_backfill',{'project_id':id,'project_revision':doc['revision'],'results':results})
