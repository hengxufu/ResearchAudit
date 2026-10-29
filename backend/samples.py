"""Streaming classification sample quality; never loads model weights."""
import hashlib
import polars as pl

def analyze(snapshot,relative_path):
    from pathlib import Path
    root=Path(snapshot['root']).resolve();path=(root/relative_path).resolve()
    if not path.is_relative_to(root) or path.is_symlink(): raise ValueError('Path must stay within project')
    evidence=next((e for e in snapshot['evidence'] if e['path']==relative_path),None)
    if not evidence: raise ValueError('Sample file must be part of imported evidence')
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    if h.hexdigest()!=evidence['sha256']: raise ValueError('Source changed; import a new snapshot')
    df=pl.scan_parquet(path) if path.suffix=='.parquet' else pl.scan_csv(path,infer_schema=False)
    required={'sample_id','target','prediction'}
    if not required.issubset(df.collect_schema().names()): raise ValueError('Requires sample_id,target,prediction columns')
    df=df.select(pl.col(k).cast(pl.String) for k in sorted(required))
    valid=pl.col('target').is_not_null()&pl.col('prediction').is_not_null()
    summary=df.select(pl.len().alias('rows'),pl.col('sample_id').n_unique().alias('unique_ids'),pl.col('sample_id').null_count().alias('missing_ids'),(~valid).sum().alias('missing_labels'),(valid&(pl.col('target')!=pl.col('prediction'))).sum().alias('failures')).collect(engine='streaming').to_dicts()[0]
    failures=df.filter(valid&(pl.col('target')!=pl.col('prediction'))).limit(100).collect(engine='streaming').to_dicts()
    classes=df.group_by('target').len().collect(engine='streaming').to_dicts()
    return {'summary':summary,'failure_samples':failures,'class_counts':classes,'source':evidence,'scope':'Classification label mismatch only; failure list capped at 100; no semantic image quality inference'}
