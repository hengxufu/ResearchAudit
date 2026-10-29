# ResearchAudit 2.0 added API contracts

Legacy APIs remain unchanged. /docs provides complete request schemas.

| Endpoint | Contract |
|---|---|
| GET /api/v2/overview | Local snapshot/asset counts and latest-500 execution-state counts |
| GET /api/v2/resources | Owned process-tree RSS/cumulative CPU, system memory, optional device-wide NVIDIA sample; hard_limits=false |
| GET /api/v2/executions/{id}/events | SSE state/stdout/stderr, bounded event count; reconnect starts a new log stream |
| PUT /api/v2/executions/{id}/dependencies | Pending-only DAG edits, rejects cycles/unknown dependencies |
| POST /api/v2/execution-batches/random | {spec,choices,count,seed}, creates up to 100 Pending drafts |
| POST/GET /api/v2/experiments | Register an experiment under a previously registered tracking project |
| POST /api/v2/associations | {snapshot_id,run_id,experiment_id}; append-only correction |
| GET /api/v2/snapshots/{id}/associations | Newest-first association history |
| POST/GET /api/v2/assets | {label,kind,path}; local reference registry |
| POST/GET /api/v2/assets/{id}/versions | Optional hash_content=true for explicit full read; no copying |
| POST /api/v2/asset-versions/{id}/verify | Independent current-reference/content check |
| GET /api/v2/asset-versions/compare?left=&right= | Added/removed/changed and metadata_changed |
| POST /api/v2/analyses/batch | {refs:[{snapshot_id,run_id}],group_by,seed}; common metrics and grouped final summaries |
| POST /api/v2/analyses/independent | {left,right,independent_runs,seed}; metric source refs; at least three runs each |
| POST /api/v2/analyses/holm | {ids}; explicit family of persisted inferential records |
| POST /api/v2/analyses/correlation | {reference,other_metric}; descriptive aligned Spearman coefficient |
| POST /api/v2/analyses/time-series | Metric reference; descriptive slope/change/lag correlation |
| POST /api/v2/analyses/pareto | {refs,metrics}; explicit metric directions required |
| GET /api/v2/analyses?limit=&offset= | Stored analysis pagination |
| POST /api/v2/snapshots/{id}/audits | {full_hash,bounds:[{metric,minimum,maximum,unit}]} |
| GET /api/v2/snapshots/{id}/audits | Persistent audit history |
| GET /api/v2/snapshots/{id}/graph | Imported/declared/computed/published provenance nodes and edges |
| POST /api/v2/plugins/{deep_learning,pose,simulation}/parse | {path,definitions}; bounded real-format parse, persisted analysis ID |
| POST /api/v2/integrations/{dvc,ro-crate}/inspect | Local metadata file structural intake, no fetching/execution |
| GET /api/v2/snapshots/{id}/ro-crate-metadata.json | Reference-only JSON-LD metadata; not a certified full profile archive |
| GET /api/v2/snapshots/{id}/report.pdf | Deterministic PDF containing values/methods/source IDs and persisted analyses |
| PUT /api/v2/tracking/settings | Persisted soft scan/read/verification bounds |
| GET /api/v2/tracking/diagnostics?limit=&offset= | Paginated source diagnostics and known-byte backlog |
| GET /api/v2/tracking/sources/{id}/history | Source generation cursor/hash history |

Metric source reference: {snapshot_id:int,run_id:string,metric:string}. Numerical bodies reject nonfinite values. Metadata agreement and statistical assumptions are not independent verification. Hash checks can be I/O intensive and are explicit actions. Missing links return 404; invalid scientific contracts return 422; illegal lifecycle transitions return 409. Job/runtime dictionaries are local data and must not be exposed to untrusted network clients.
