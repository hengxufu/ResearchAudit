# ResearchAudit 3.0 API contracts

All routes are localhost-only under existing host/origin protections. `/docs` provides Pydantic field details. Bad inputs return 422, unknown references 404. Revision conflicts currently use 422 with `Revision conflict`. No route below uploads data. Existing `/api` and `/api/v2` contracts remain available.

## Reproduction

1. `POST /api/v3/reproductions`: `{source_execution, input_versions:[], tolerances:{loss:{atol:1e-6,rtol:1e-4}}}`. Source must be Succeeded with a snapshot. Saves Draft, no execution.
2. `GET /api/v3/reproductions`: latest 100 manifests.
3. `GET /api/v3/reproductions/{id}/manifest.json`: machine-readable versioned manifest download.
4. `POST /api/v3/reproductions/{id}/start`: `{confirmed:true,allow_code_change:false}`. Requires explicit confirmation; changed source/Git is rejected unless override is explicit and recorded. Prepared/Pending recovery reuses the reserved run.
5. `POST /api/v3/reproductions/{id}/evaluate`: persists a report even when incomplete; separate five-dimension scorecard, tolerance comparisons, source/replay snapshots and source paths/hashes. Does not start a command.
6. `GET /api/v3/reproduction-reports/{report_id}.json`: saved report download.
7. `POST /api/v3/reproductions/distribution`: `{left:[MetricRef...],right:[MetricRef...],independent_runs:true,seed:0}`. At least three per group; compatible protocols and distinct Run identities required. Status UNKNOWN is deliberate without an equivalence margin/design.

`RunRef={snapshot_id:int,run_id:str}`; `MetricRef` adds `metric:str`.

## Data Studio

Start from existing `POST /api/v2/assets` with `{label,kind,path}`. Versions and full hash verification remain in v2.

| Route | Input/result |
|---|---|
| `GET /api/v3/assets/{id}/files` | `path`, `limit=100` (1..500); bounded directory listing |
| `GET /api/v3/assets/{id}/inspect` | `path`; field shapes/dtypes, table schema, image metadata, or weight metadata |
| `POST /api/v3/assets/{id}/slice` | `{path,key,slices:[[start,stop,step],...]}`; values, shape, finite count and slice mean |
| `GET /api/v3/assets/{id}/table` | `path,offset>=0,limit=1..500`; CSV/Parquet/JSON rows |
| `GET /api/v3/assets/{id}/image` | `path,size=32..1024`; JPEG thumbnail |
| `POST /api/v3/assets/{id}/notebook?path=...` | Notebook v4 stored outputs as persisted analysis; no cell execution or HTML |

Array bounds and format limits are in v3_architecture.md. HDF5 dataset keys containing external/soft links are rejected. NPZ supports bounded numeric members, not lazy arbitrary decompression. Images/arrays remain local.

## Scientific suites and diagnostics

- `POST /api/v3/suites/training`: `{snapshot_id,metric}`. Best observation requires direction; checkpoint candidates are listed, best-checkpoint association UNKNOWN unless independently recorded.
- `POST /api/v3/suites/pose`: `RunRef` plus `{columns:{truth_quaternion:[4 names],prediction_quaternion:[4 names],truth_translation:[3 names],prediction_translation:[3 names]},quaternion_order:"xyzw"|"wxyz",convention:"active"|"passive",frame,translation_unit,failure_rotation_degrees?:number,failure_translation?:number}`.
- `POST /api/v3/suites/energy-balance`: `RunRef` plus `{energy_metric,power_metric,time_metric,unit_energy:"J",unit_power:"W",unit_time:"s",atol>=0,rtol>=0}`.
- `POST /api/v3/suites/simulation-trend`: `RunRef` plus `{x_metric,y_metric,kind:"convergence"|"sensitivity"}`. Uses recorded columns and explicit source units.
- `POST /api/v3/intelligence/diagnose`: `{snapshot_id,loss_metric:"loss",validation_metric?:string,window:5,relative_threshold:0.1}`. Window 2..1000; threshold (0,10]. Exposes rules/evidence, persists analysis.
- `POST /api/v3/intelligence/query`: `{snapshot_id,text,metric?:string}`. Supported grammar: missing metadata, or rank/best/lowest/highest/最好/最低/最高/排序 plus an exact metric name. Metric definition direction decides rank order, ambiguous mappings are refused. No cross-project SQL, arbitrary prompt execution or remote LLM.
- `POST /api/v3/intelligence/summary`: `{snapshot_id,run_ids:[...]}` (1..500); persisted parameter differences, metric values/compatibility, missing information and explicitly unverified hypotheses/control suggestions.
- Existing `/api/projects/{id}/samples?path=...` checks classification failure samples from imported SHA-verified source files.
- Existing `/api/science/linear-propagation` retains explicit coefficients/covariance/product-unit contracts.

## Workflows

`POST /api/v3/workflows` saves `{name,description,nodes}`. A node is:

```json
{"id":"report","kind":"report","depends_on":["train"],"retries":0,
 "config":{"snapshot_id":{"$ref":"train.snapshot_id"}},
 "condition":{"node":"train","path":"runs.0.metrics.loss","op":"lt","value":0.2}}
```

Node IDs use ASCII letters/digits/underscore/hyphen; maximum 100 nodes. Kinds: command/import/describe/batch/audit/figure/report/balance/asset_verify. `config` is a plain dict validated by the actual adapter; command configuration uses the existing `ExecutionSpec`. Direct dependencies must include every `$ref` or condition source. `$ref` selects output using dot-separated keys/array indices and never evaluates code. `runs.0` is explicit index selection, not automatic scientific matching.

Node config contracts:

| Kind | Config |
|---|---|
| command | ExecutionSpec: argv, cwd, optional env/params/code_files/limits |
| import | `{path}` |
| describe | `{snapshot_id,run_id,metric}` |
| batch | `{refs:[RunRef],group_by:[parameter names],seed?}` |
| audit | `{snapshot_id,full_hash?:false,bounds?:[]}` |
| figure | `{snapshot_id,metric,kind?:"curve",format?:"svg"}` |
| report | `{snapshot_id}` |
| balance | same as energy-balance API |
| asset_verify | `{version_id}` |

Command/import outputs include snapshot_id and `runs:[{run_id,name,metrics}]`; command also has execution_id/output_dir. Analysis/audit outputs are their original persisted records. Figure/report outputs include managed file path and byte size.

`PUT /workflows/{id}?revision=N` creates a new revision; `GET /workflows` lists definitions; `GET /workflows/{id}/history` lists prior definitions. `POST /workflows/{id}/start` requires `{revision:N,confirmed:true}` and returns an active run. `GET /workflow-runs?limit&offset`, `GET /workflow-runs/{id}` and `POST /workflow-runs/{id}/cancel` manage history/owned cancellation. `GET /workflow-runs/{id}/artifacts/{node}` downloads a generated figure/report from the managed workflow folder.

Maximum two retries beyond the initial attempt. A failed condition/reference is an error; a false condition is Skipped. A failed or skipped upstream node blocks dependencies. No implicit retry after restart. Parameter grids/random drafts remain available through existing execution-batch APIs and can be represented as separate command nodes.

## Knowledge and graph

`POST /knowledge` and `PUT /knowledge/{id}?revision=N` store:

```json
{"kind":"claim","title":"Researcher-authored conclusion","body":"...",
 "conditions":"Dataset/domain/protocol applicability",
 "validation_status":"unverified","review_reason":"",
 "supporting":[{"kind":"snapshot","id":"1","run_id":"optional"}],
 "conflicting":[{"kind":"analysis","id":"persisted-analysis-id"}]}
```

Kinds: note/hypothesis/design/claim/issue/milestone. Reference kinds: snapshot/analysis/figure/knowledge. Figure requires snapshot_id. Knowledge refs pin revision. `reviewed` is a human declaration requiring support and review_reason; no automatic inference promotes a claim. `GET /knowledge?q=&limit=&offset=` searches latest revisions; `GET /knowledge/{id}/history` returns history. `GET /snapshots/{id}/graph` includes v2 provenance, claims/support/conflict and reproduction reports. Graph display caps do not delete evidence.
