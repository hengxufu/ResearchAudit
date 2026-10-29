"""Standalone no-extraction verifier for a ResearchAudit reference archive."""
import argparse,hashlib,json,zipfile

def verify(path):
    with zipfile.ZipFile(path) as z:
        if len(z.infolist())>10000 or sum(e.file_size for e in z.infolist())>512*1024*1024:raise ValueError('Archive exceeds verification bounds')
        manifest=json.loads(z.read('manifest.json'))
        if set(z.namelist())!=set(manifest)|{'manifest.json'}:raise ValueError('Unexpected archive entries')
        for name,expected in manifest.items():
            data=z.read(name)
            if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:raise ValueError('Checksum mismatch: '+name)
    return {'status':'PASS','files':len(manifest),'scope':'Internal integrity only; no publisher authentication or external dataset verification'}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive');args=parser.parse_args();print(json.dumps(verify(args.archive),indent=2))
