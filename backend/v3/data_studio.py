"""Bounded/lazy local asset browsing. Never unpickles model weights."""
import io,json,math,zipfile,warnings
import os
from pathlib import Path
import numpy as np
import polars as pl
from PIL import Image
from ..v2 import assets

def files(asset_id,relative='',limit=100):
    root=Path(assets.asset(asset_id)['root']).resolve();folder=(root/relative).resolve() if root.is_dir() else root
    if not root.is_dir():return [{'path':root.name,'bytes':root.stat().st_size,'directory':False}]
    if not folder.is_relative_to(root) or not folder.is_dir():raise ValueError('Registered directory required')
    result=[]
    with os.scandir(folder) as entries:
        for entry in entries:
            if entry.is_symlink():continue
            result.append({'path':str(Path(entry.path).relative_to(root)),'bytes':entry.stat().st_size if entry.is_file() else None,'directory':entry.is_dir()})
            if len(result)>=limit:break
    return result

def resolve(asset_id,relative=''):
    root=Path(assets.asset(asset_id)['root']).resolve()
    p=(root/relative).resolve() if root.is_dir() else root
    if (root.is_dir() and not p.is_relative_to(root)) or (root.is_file() and relative not in ('',root.name)):raise ValueError('Path must stay within registered asset')
    if not p.is_file():raise ValueError('File reference is unavailable')
    return p

def clean(value):
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if value is None or isinstance(value,(str,int,float,bool)):return value
    return str(value)

def npz_headers(path):
    result=[]
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist())>10000:raise ValueError('Too many array members')
        for member in archive.infolist():
            if not member.filename.endswith('.npy'):continue
            with archive.open(member) as f:
                version=np.lib.format.read_magic(f)
                if version==(1,0):shape,fortran,dtype=np.lib.format.read_array_header_1_0(f)
                elif version==(2,0):shape,fortran,dtype=np.lib.format.read_array_header_2_0(f)
                else:raise ValueError('Unsupported NPY header version')
            result.append({'key':member.filename[:-4],'shape':list(shape),'dtype':str(dtype),'expanded_bytes':member.file_size,'object_dtype':dtype.hasobject})
    return result

def inspect(asset_id,relative=''):
    p=resolve(asset_id,relative);info={'path':relative or p.name,'bytes':p.stat().st_size,'fields':[],'source_scope':'Registered local asset, current version; not an automatic integrity certificate'}
    if p.suffix.lower() in ('.h5','.hdf5'):
        import h5py
        with h5py.File(p,'r') as f:
            def visit(name,obj):
                if isinstance(obj,h5py.Dataset):info['fields'].append({'key':name,'shape':list(obj.shape),'dtype':str(obj.dtype),'chunks':obj.chunks})
                if len(info['fields'])>10000:raise ValueError('Dataset count exceeds metadata bound')
            f.visititems(visit)
    elif p.suffix=='.npz':info['fields']=npz_headers(p)
    elif p.suffix=='.npy':
        a=np.load(p,mmap_mode='r',allow_pickle=False);info['fields']=[{'key':'array','shape':list(a.shape),'dtype':str(a.dtype)}]
    elif p.suffix.lower() in ('.png','.jpg','.jpeg','.tif','.tiff','.bmp'):
        with Image.open(p) as image:info['image']={'size':list(image.size),'mode':image.mode,'format':image.format}
    elif p.suffix.lower() in ('.csv','.parquet'):
        frame=pl.scan_csv(p) if p.suffix=='.csv' else pl.scan_parquet(p);info['columns']={k:str(v) for k,v in frame.collect_schema().items()}
    elif p.suffix.lower() in ('.pt','.pth','.ckpt','.onnx'):info['weights']='Metadata only; deserialization is not performed'
    return clean(info)

def array_slice(asset_id,relative,key,slices):
    p=resolve(asset_id,relative)
    def read(a):
        if len(a.shape)>8 or len(slices)!=len(a.shape):raise ValueError('Supply one [start,stop,step] per dimension (max 8)')
        indices=[];count=1
        for shape,selection in zip(a.shape,slices):
            start,stop,step=selection
            if step<1 or start<0 or stop<start or stop>shape:raise ValueError('Invalid bounded slice')
            count*=len(range(start,stop,step));indices.append(slice(start,stop,step))
        if count>100000:raise ValueError('Preview capped at 100000 elements')
        if count*np.dtype(a.dtype).itemsize>8*1024*1024:raise ValueError('Preview capped at 8 MiB of array values')
        if np.dtype(a.dtype).hasobject:raise ValueError('Object arrays are not supported')
        values=np.asarray(a[tuple(indices)])
        finite=values[np.isfinite(values)] if np.issubdtype(values.dtype,np.number) and not np.iscomplexobj(values) else np.array([])
        return {'shape':list(values.shape),'dtype':str(values.dtype),'values':clean(values),'finite_count':int(finite.size),'mean':float(finite.mean()) if finite.size else None,'method':'Selected slice only, not a full-field statistic'}
    if p.suffix.lower() in ('.h5','.hdf5'):
        import h5py
        with h5py.File(p,'r') as f:
            current=f
            for part in key.strip('/').split('/'):
                if not isinstance(current,h5py.Group) or not isinstance(current.get(part,getlink=True),h5py.HardLink):raise ValueError('Only internal HDF5 hard links may be previewed')
                current=current[part]
            if key not in f or not isinstance(f[key],h5py.Dataset):raise ValueError('Unknown HDF5 dataset')
            if f[key].is_virtual or f[key].external:raise ValueError('External/virtual HDF5 storage is not previewed')
            return read(f[key])
    if p.suffix=='.npz':
        header=next((a for a in npz_headers(p) if a['key']==key),None)
        if not header or header['object_dtype'] or header['expanded_bytes']>64*1024*1024 or math.prod(header['shape'])*np.dtype(header['dtype']).itemsize>64*1024*1024:raise ValueError('NPZ member unavailable/object/>64 MiB; use chunked HDF5 for large lazy access')
        with np.load(p,allow_pickle=False) as a:return read(a[key])
    if p.suffix=='.npy':return read(np.load(p,mmap_mode='r',allow_pickle=False))
    raise ValueError('Array preview supports HDF5/NPY and bounded NPZ')

def table(asset_id,relative,offset=0,limit=50):
    p=resolve(asset_id,relative)
    if p.suffix.lower() in ('.csv','.parquet'):
        frame=(pl.scan_csv(p) if p.suffix=='.csv' else pl.scan_parquet(p)).slice(offset,limit).collect(engine='streaming')
        return {'rows':clean(frame.to_dicts()),'columns':frame.columns,'offset':offset,'returned':frame.height,'method':'Lazy bounded table page; CSV high offsets still require scanning'}
    if p.suffix=='.json':
        if p.stat().st_size>10*1024*1024:raise ValueError('JSON table capped at 10 MiB; use JSONL/Parquet for large tables')
        data=json.loads(p.read_text(encoding='utf-8'));rows=data if isinstance(data,list) else data.get('records',[]) if isinstance(data,dict) else []
        if not all(isinstance(r,dict) for r in rows):raise ValueError('JSON table requires records as objects')
        return {'rows':clean(rows[offset:offset+limit]),'offset':offset,'returned':len(rows[offset:offset+limit])}
    raise ValueError('Table pages support CSV/Parquet/JSON')

def image_preview(asset_id,relative,size=768):
    p=resolve(asset_id,relative)
    if p.suffix.lower() not in ('.png','.jpg','.jpeg','.tif','.tiff','.bmp'):raise ValueError('Unsupported image format')
    with warnings.catch_warnings():
        warnings.simplefilter('error',Image.DecompressionBombWarning)
        with Image.open(p) as image:
            if image.width*image.height>20000000:raise ValueError('Image exceeds 20 megapixel preview bound')
            image.thumbnail((size,size));out=io.BytesIO();image.convert('RGB').save(out,format='JPEG',quality=85);return out.getvalue()
