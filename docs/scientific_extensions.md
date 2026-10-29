# Scientific extension API and scope

## Evidence-backed scientific checks

POST /api/projects/{id}/science/energy body {run_id,metric,atol,rtol}: finite imported series; residual E(t)-E(0), threshold atol+rtol*abs(E(0)). Assumes closed-system total energy; caller must incorporate boundary work/flux. PASS only means numerical residual is within supplied tolerance.

POST same path with /convergence and body {run_id,metric,x}: x is user-supplied positive grid spacing; imported metric is positive reference error. Requires at least three distinct spacings. Fits log(error)=p log(h)+b, returns observed p and R². Empirical trend is not proof of an asymptotic regime.

POST /sensitivity: x is explicit user-supplied parameter values aligned to imported responses; returns sorted adjacent secants. No causal claim or global sensitivity claim. Other conditions must be independently controlled. x is not automatically extracted from separate experiments.

POST /api/science/linear-propagation body {coefficients,covariance,product_units}: exact linear variance cᵀΣc, symmetric positive-semidefinite covariance required; output standard uncertainty k=1, no claimed coverage probability. product_units represent coefficient-times-input units and must all agree; no unit conversion or nonlinear propagation implemented. Inputs are explicitly labeled user_supplied, not imported measurements.

## Classification quality

GET /api/projects/{id}/samples?path=samples.csv (or Parquet). Requires sample_id,target,prediction. Returns row/unique-ID/missing-ID/missing-label/failure counts, class counts and first 100 classification mismatches. Processing uses lazy Polars streaming aggregates; file must match imported SHA256. No model execution, image-quality inference or private media upload. Current collector's 256 MiB per-file import cap still applies.

## Multi-level evidence

POST /api/evidence {kind:figure|table|claim|experiment,label,sources:[{snapshot_id,run_id,metric?}|{evidence_id}]} appends a record. References must already exist, preventing forward references/cycles. GET /api/evidence lists records; GET /api/evidence/{id}/trace recursively resolves the record chain. Original snapshots retain hashes and metric-source evidence. Dependency links are user_declared and do not assert execution capture or correctness. Stored labels can describe a figure/table/claim; rendered artifact bytes and claim numerical expressions are not yet bound to these records.

## Remaining work and standards

This increment is API-first; a scientific-analysis UI has not been added. Existing figure exports and graph APIs remain unchanged. Evidence records are not yet merged into report exports. Standard compatibility remains limited to the existing MLflow local metrics reader. No full bidirectional MLflow/DVC/RO-Crate adapter has been delivered. Remote SSH/HPC execution, credential management, dataset transfer, scheduler submission and remote environment capture are not implemented. No network connection to user compute environments is made.

Specification sources reviewed: https://doc.dvc.org/user-guide/project-structure/dvc-files ; https://www.researchobject.org/ro-crate/specification/1.1/ ; https://mlflow.org/docs/latest/api_reference/rest-api.html . Future adapters should target these documented contracts and undergo round-trip tests; do not label custom JSON exports as standard compliance.

Validation: 18 tests passed in 7.58 seconds. New controlled TEST DATA checks drift, known second-order convergence, secant slopes, correlated propagation, invalid covariance, duplicate spacing, missing observations, classification mismatches, source mutation rejection and multi-level evidence references.
