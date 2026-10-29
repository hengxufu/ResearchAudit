"""Human-readable report with embedded machine-readable evidence."""
import json
from .analysis import audit,compare

def render(snapshot,id,figures):
    comparisons={m:compare(snapshot,m) for m in sorted({m for r in snapshot['runs'] for m in r['metrics']})}
    findings=audit(snapshot)
    def cell(value): return str(value).replace('|','\\|').replace('\n',' ')
    lines=['# ResearchAudit experiment and audit report','',f'Snapshot: {id}','',f'Project: {cell(snapshot["root"])}','',f'Collection Git commit: {snapshot["git"]["commit"] or "UNKNOWN"}','','Execution reproducibility and scientific correctness: UNKNOWN. This report audits imported evidence.','','## Metrics','','| Metric | Run | Final | Best | Direction | Unit | Compatibility |','|---|---|---:|---:|---|---|---|']
    for metric,result in comparisons.items():
        for row in result['values']:
            d=row['definition'];lines.append('| '+' | '.join(map(cell,[metric,row['run'],row['value'],row['best'],d.get('direction','UNKNOWN'),d.get('unit','UNKNOWN'),result['compatibility']['status']]))+' |')
    lines+=['','## Audit findings','','| Rule | Run | Status | Reason | Recommendation |','|---|---|---|---|---|']
    for f in findings: lines.append('| '+' | '.join(map(cell,[f['rule'],f.get('run','project'),f['status'],f.get('reason',f.get('message')),f.get('suggestion')]))+' |')
    lines+=['','## Evidence and reproducibility','','Original execution environment and dataset content must be independently verified. Source paths, hashes, parameters, summary methods and missing metadata follow.','','```json',json.dumps({'snapshot':snapshot,'audit':findings,'comparisons':comparisons,'figures':figures},ensure_ascii=False,indent=2),'```','']
    return '\n'.join(lines)
