"""Portable typed evidence graph, with explicit declaration vs observation."""
import hashlib,json

def graph(snapshot):
    nodes=[];edges=[]
    for e in snapshot['evidence']:
        nodes.append({'id':e['sha256'],'type':'file','attributes':e})
    for r in snapshot['runs']:
        nodes.append({'id':r['id'],'type':'imported_run','attributes':{'name':r['name'],'parameters':r['params']}})
        for metric,sources in r.get('metric_sources',{}).items():
            mid=r['id']+':'+metric
            nodes.append({'id':mid,'type':'metric','attributes':{'name':metric,'definition':r.get('metric_definitions',{}).get(metric)}})
            edges.append({'from':r['id'],'to':mid,'type':'contains','basis':'observed_import'})
            for source in sources: edges.append({'from':source['sha256'],'to':mid,'type':'derived_from','basis':'observed_import'})
    return {'nodes':nodes,'edges':edges,'scope':'Import provenance; not an execution dependency graph'}
