"""Independent real-format domain parsers; original fields and definitions preserved."""
import json,hashlib,zipfile
from .assets import digest
from pathlib import Path
import numpy as np
import polars as pl
import yaml

def parse(kind,path,definitions=None):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>256*1024*1024:raise ValueError('Existing file <=256 MiB required')
    suffix=path.suffix.lower();result={'plugin':kind,'version':'1.0','definitions':definitions or {},'source':{'path':str(path.resolve()),'sha256':digest(path)},'warnings':[]}
    if suffix in ('.csv','.parquet'):
        frame=(pl.scan_csv(path) if suffix=='.csv' else pl.scan_parquet(path)).limit(100001).collect(engine='streaming')
        if frame.height>100000:
            frame=frame.head(100000);result['warnings'].append('Only first 100000 rows parsed; total row count unknown')
        result['rows']=frame.height;result['columns']=frame.columns;result['raw_preview']=frame.head(30).to_dicts()
        result['series']={c:[float(v) if v is not None and np.isfinite(v) else None for v in frame[c].to_list()] for c in frame.columns if frame[c].dtype.is_numeric()}
    elif suffix in ('.json','.yaml','.yml'):
        result['raw']=json.loads(path.read_text(encoding='utf-8')) if suffix=='.json' else yaml.safe_load(path.read_text(encoding='utf-8'))
    elif suffix in ('.npz','.h5','.hdf5'):
        arrays={}
        def summary(name,array):
            if np.prod(array.shape)>10000000:arrays[name]={'shape':list(array.shape),'status':'UNKNOWN','reason':'Array exceeds 10M element analysis bound'};return
            values=np.asarray(array)
            if not np.issubdtype(values.dtype,np.number):return
            finite=values[np.isfinite(values)];arrays[name]={'shape':list(values.shape),'dtype':str(values.dtype),'finite_count':int(finite.size),'nonfinite':int(values.size-finite.size),'minimum':float(finite.min()) if finite.size else None,'maximum':float(finite.max()) if finite.size else None,'mean':float(finite.mean()) if finite.size else None}
        if suffix=='.npz':
            with zipfile.ZipFile(path) as archive:
                if sum(e.file_size for e in archive.infolist())>128*1024*1024:raise ValueError('NPZ expanded data exceeds 128 MiB bound')
            with np.load(path,allow_pickle=False) as data:
                for name in data.files:summary(name,data[name])
        else:
            import h5py
            with h5py.File(path,'r') as data:
                def visit(name,obj):
                    if isinstance(obj,h5py.Dataset):summary(name,obj)
                data.visititems(visit)
        result['fields']=arrays
    elif path.name.startswith('events.out.tfevents'):
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
        ea=EventAccumulator(str(path),size_guidance={'scalars':0});ea.Reload();result['series']={tag:[{'step':e.step,'value':e.value if np.isfinite(e.value) else None} for e in ea.Scalars(tag)] for tag in ea.Tags()['scalars']}
    else:raise ValueError('Unsupported plugin file format')
    if kind=='pose':result['warnings'].append('Rotation/translation units and evaluation protocol must be supplied; no SPEED-specific definition assumed')
    if kind=='simulation':result['warnings'].append('Field summaries are descriptive; physical correctness requires boundary/mesh/unit contracts')
    if kind=='deep_learning':result['warnings'].append('Epoch observations are not independent replicates; checkpoint selection requires an explicit metric direction')
    def serializable(value):
        if isinstance(value,float) and not np.isfinite(value):return None
        if isinstance(value,dict):return {str(k):serializable(v) for k,v in value.items()}
        if isinstance(value,list):return [serializable(v) for v in value]
        if value is None or isinstance(value,(str,int,float,bool)):return value
        return str(value)
    return serializable(result)
