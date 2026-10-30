import hashlib, json, math, subprocess, platform
from pathlib import Path
import polars as pl
import yaml
import os
SKIP = {".artifacts", ".git", ".venv", "node_modules", ".researchaudit", "dist", "__pycache__", ".pytest_cache", "test-results", "playwright-report"}
def git(root, *args):
    try: return subprocess.check_output(["git","-C",str(root),*args],stderr=subprocess.DEVNULL,timeout=10).decode().strip()
    except Exception: return None
def scan(root, checkpoint=None):
    root = Path(root).resolve()
    if not root.is_dir(): raise ValueError("Project directory does not exist")
    runs, evidence, issues = {}, [], []
    paths=[]
    for directory, dirs, names in os.walk(root, followlinks=False):
        if checkpoint: checkpoint(0,0,"Discovering: "+str(Path(directory).relative_to(root)))
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith(".test-runs-") and not (Path(directory)/d).is_symlink())
        paths.extend(Path(directory)/name for name in sorted(names))
    for position,p in enumerate(sorted(paths)):
        if checkpoint: checkpoint(position,len(paths),str(p.relative_to(root)))
        rel = p.relative_to(root)
        if any(s in SKIP for s in rel.parts) or not p.is_file() or p.is_symlink(): continue
        if p.suffix.lower() not in {".csv",".json",".yaml",".yml",".toml",".pt",".pth",".ckpt",".npz",".parquet"} and not p.name.startswith("events.out.tfevents"): continue
        if p.stat().st_size > 256*1024*1024:
            issues.append({"file":str(rel),"message":"Skipped file larger than 256 MiB"}); continue
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        ev = {"path":str(rel),"sha256":h.hexdigest(),"bytes":p.stat().st_size}
        evidence.append(ev)
        key = str(rel.parent)
        run = runs.setdefault(key, {"name":key,"params":{},"metrics":{},"series":{},"sources":[]})
        run["sources"].append(ev)
        try:
            if p.suffix in {".json", ".yaml", ".yml"}:
                obj = json.loads(p.read_text(encoding="utf-8")) if p.suffix == ".json" else yaml.safe_load(p.read_text(encoding="utf-8"))
                if isinstance(obj,dict):
                    if "config" in p.stem or "param" in p.stem:
                        run["params"].update({k:v for k,v in obj.items() if k!='researchaudit_execution'})
                        if 'researchaudit_execution' in obj:run.setdefault('execution',{}).update(obj['researchaudit_execution'])
                        run.setdefault("config_sources",[]).append(ev)
                        run.setdefault("metric_definitions",{}).update(obj.get("metric_definitions",{}))
                    else:
                        run["params"].update(obj.get("params",{}))
                        for k,v in obj.get("metrics",obj).items():
                            if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v): run["metrics"][k]=float(v)
            elif p.suffix in {".csv",".parquet"}:
                df = pl.read_csv(p) if p.suffix == ".csv" else pl.read_parquet(p)
                for col in df.columns:
                    if df[col].dtype.is_numeric():
                        vals = [float(v) if v is not None and math.isfinite(float(v)) else None for v in df[col].to_list()]
                        if col in run["series"]:
                            issues.append({"file":str(rel),"message":"Duplicate metric rejected: "+col}); continue
                        run["series"][col]=vals
                        run.setdefault("metric_sources",{})[col]=[{**ev,"column":col,"rows":len(vals)}]
                        finite=[v for v in vals if v is not None]
                        if vals: run["metrics"][col]=vals[-1]
            elif p.name.startswith("events.out.tfevents"):
                from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
                ea=EventAccumulator(str(p),size_guidance={"scalars":0}); ea.Reload()
                for tag in ea.Tags()["scalars"]:
                    events=ea.Scalars(tag); vals=[float(e.value) if math.isfinite(e.value) else None for e in events]
                    run["series"][tag]=vals
                    run["series"][tag+"/step"]=[e.step for e in events]
                    if vals and vals[-1] is not None: run["metrics"][tag]=vals[-1]
        except Exception as e: issues.append({"file":str(rel),"message":str(e)})
    # MLflow local file-store metrics: timestamp value step
    for position,p in enumerate(paths):
        if checkpoint: checkpoint(position,len(paths),"MLflow: "+str(p.relative_to(root)))
        if p.parent.name != "metrics": continue
        if not p.is_file() or p.is_symlink() or p.stat().st_size>256*1024*1024 or any(s in SKIP for s in p.relative_to(root).parts): continue
        try:
            rows=[line.split() for line in p.read_text().splitlines()]; vals=[float(r[1]) for r in rows]
            if not all(math.isfinite(v) for v in vals): raise ValueError("Nonfinite MLflow metric")
            key=str(p.parent.parent.relative_to(root)); run=runs.setdefault(key,{"name":key,"params":{},"metrics":{},"series":{},"sources":[]})
            ev={"path":str(p.relative_to(root)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size}; evidence.append(ev); run["sources"].append(ev)
            run["series"][p.name]=vals
            if vals: run["metrics"][p.name]=vals[-1]
        except Exception as e: issues.append({"file":str(p),"message":str(e)})
    # Refuse a mixed snapshot if imported evidence changed while being parsed.
    for position,ev in enumerate(evidence):
        if checkpoint: checkpoint(position,len(evidence),"Verify: "+ev["path"])
        source=root/ev["path"]
        h=hashlib.sha256()
        try:
            with source.open("rb") as f:
                for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        except OSError as error: raise ValueError("Source disappeared during import: "+ev["path"]) from error
        if h.hexdigest()!=ev["sha256"]: raise ValueError("Source changed during import; retry: "+ev["path"])
    if checkpoint: checkpoint(len(paths),len(paths),"Ready to commit")
    for run in runs.values():
        run["id"]=hashlib.sha256((str(root)+"/"+run["name"]).encode()).hexdigest()[:24]
        for metric in run["metrics"]:
            run.setdefault("metric_sources",{}).setdefault(metric,run["sources"])
    return {"schema_version":2,"root":str(root),"git":{"commit":git(root,"rev-parse","HEAD"),"status":git(root,"status","--porcelain")},"environment":{"python":platform.python_version(),"platform":platform.platform()},"runs":list(runs.values()),"evidence":evidence,"issues":issues,"metric_policy":"Final is last observation, including missing values. Best requires explicit direction. Units and evaluation contracts are author-declared."}
