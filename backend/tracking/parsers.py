"""Incremental record parsers. A record is official only after its newline."""
import csv,io,json,math
PARSERS={}
def parser(extension):
    def wrap(fn):PARSERS[extension]=fn;return fn
    return wrap
@parser('.jsonl')
def jsonl(data,header):
    records=[]
    for line in data.decode('utf-8').splitlines():
        if not line.strip():continue
        value=json.loads(line)
        if not isinstance(value,dict):raise ValueError('JSONL records must be objects')
        records.append(value)
    return records,header
@parser('.csv')
def csv_records(data,header):
    # Each record must occupy one physical line; multiline quoted fields are rejected.
    lines=data.decode('utf-8').splitlines();records=[]
    for line in lines:
        row=next(csv.reader([line],strict=True))
        if header is None:
            if not row or len(set(row))!=len(row):raise ValueError('Invalid CSV header')
            header=row;continue
        if len(row)!=len(header):raise ValueError('CSV column count mismatch')
        record={}
        for key,value in zip(header,row):
            try:record[key]=float(value)
            except ValueError:record[key]=value
        records.append(record)
    return records,header

def normalize(record):
    metrics=record.get('metrics',record)
    if not isinstance(metrics,dict):raise ValueError('metrics must be an object')
    return {str(k):float(v) for k,v in metrics.items() if k not in ('step','timestamp','seed') and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)}
