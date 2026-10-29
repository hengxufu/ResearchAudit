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

def tensorboard_records(data):
    """Parse complete TFRecord frames and verify both masked CRC32C checksums."""
    import struct
    from tensorboard.compat.tensorflow_stub.pywrap_tensorflow import masked_crc32c
    from tensorboard.compat.proto.event_pb2 import Event
    from tensorboard.util.tensor_util import make_ndarray
    records=[];offset=0
    while len(data)-offset>=12:
        header=data[offset:offset+8];length=struct.unpack('<Q',header)[0]
        if struct.unpack('<I',data[offset+8:offset+12])[0]!=masked_crc32c(header):raise ValueError('TensorBoard header CRC mismatch')
        if length>64*1024*1024:raise ValueError('TensorBoard event exceeds 64 MiB safety limit')
        end=offset+12+length+4
        if len(data)<end:break
        payload=data[offset+12:end-4]
        if struct.unpack('<I',data[end-4:end])[0]!=masked_crc32c(payload):raise ValueError('TensorBoard payload CRC mismatch')
        event=Event.FromString(payload);metrics={}
        for value in event.summary.value:
            if value.HasField('simple_value'):number=float(value.simple_value)
            elif value.HasField('tensor'):
                a=make_ndarray(value.tensor)
                if a.size!=1:continue
                number=float(a.item())
            else:continue
            metrics[value.tag]=number if math.isfinite(number) else None
        records.append({'step':event.step,'timestamp':event.wall_time,'metrics':metrics,'session_status':int(event.session_log.status) if event.HasField('session_log') else None})
        offset=end
    return records,offset
