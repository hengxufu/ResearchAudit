# Implementation plan and acceptance

## Stage 0 — inspection and source review

Completed initial repository inspection and focused GitHub source review. See open_source_research.md for verified mechanisms, licenses and unconfirmed areas. noWorkflow collector and detailed frontend/storage internals remain research work.

## Stage 1 — correctness foundations

Implemented additive snapshot fingerprint migration, deterministic run IDs, YAML configs, explicit metric definitions, final/best distinction, missing-value preservation for CSV, compatibility gate, seed groups and structured audit rule registry. Preserve original UI and routes.

## Stage 2 — usable analysis

Implemented API exact parameter filtering, UI parameter substring filtering, overlaid curves, zoom, display-only trailing five-observation smoothing, SVG export, comparison status, seed summaries and audit recommendations. Report exports analysis plus source evidence. Existing PNG export remains available.

## Stage 3 — acceptance and remaining work

Run pytest and frontend build. Expand controlled tests for YAML, idempotence, changed evidence, minimizing metrics, NaN final observations, differing metric definitions and dataset versions, repeated seeds and report equality. Fixtures must identify themselves as TEST DATA.

Not complete: PDF figure export, error distributions, polished comparison/report tables, browser interaction automation, complete MLflow context import, TensorBoard v2 tensor summary coverage, original execution environment capture, source-race detection, source archiving, robust all-adapter duplicate rejection, dataset digest verification, transactional metric Parquet cache and DuckDB query engine, background scan progress/cancellation.

## Stage 4 — future extension

Separate normalized run/artifact/metric-definition/audit/evidence-edge tables when schema is stable; stream metric batches to Parquet, query with DuckDB; add immutable typed graph and report/figure specification IDs; optional MLflow/DVC/RO-Crate adapters; convergence, sensitivity and uncertainty plugins; explicit opt-in Python execution tracing. Gate each extension on real-format tests and license review.

## Decision log

- Retain snapshot API for compatibility rather than a speculative full database rewrite.
- Suppress unsupported cross-run means instead of presenting unknown comparability as a valid pooled estimate.
- Treat dataset_version as declared until actual file evidence is verified.
- Do not copy third-party implementation code.

## Progress update — figure and evidence pipeline

Implemented backend curves/distributions exported to PDF/SVG/PNG at 300 DPI where applicable, persisted figure specifications with SHA256 identity, imported-evidence graph JSON, Parquet observation cache and DuckDB paginated queries, and human-readable report tables plus embedded evidence. Snapshot remains authoritative; JSON series are retained for compatibility so this is not yet a fully columnar large-scale architecture. Cache writes are direct; interrupted cache repair and lifecycle management need hardening. Exported distributions are distributions of the selected observations, not automatically prediction errors.

Primary and MLflow discovery now share the symlink-pruned path inventory. Source hashes are rechecked after parsing and inconsistent imports are refused. Changes after import completion do not invalidate the historical snapshot. Static verification cannot recover original execution environments.

Validation: 11 passed, including actual TensorBoard Event protobuf generation, MLflow metric files, PDF/PNG/SVG signatures, figure evidence, graph edges and DuckDB pagination. Build passes. Still pending: browser interaction tests, full TensorBoard tensor-summary/restart semantics, complete MLflow metadata, consistent all-format duplicate handling, original execution capture, dataset digest verification, background task cancellation, full evidence claim graph, dependency remediation and performance benchmarks.

## Stage 3 increment — background imports (2026-10-29)

Completed durable import-job lifecycle with a single bounded worker, maximum eight active/queued jobs, progress checkpoints, cooperative cancellation and restart interruption marking. The UI now uses POST /api/import-jobs and polls job state; existing synchronous /api/import remains compatible. Cancellation before the committing state cannot submit a snapshot. Once committing begins the cancel endpoint returns 409. The scan worker checks cancellation during discovery, primary import, MLflow import and source verification.

Acceptance: 16 tests passed in 6.55 seconds. Tests exercise worker completion, cancellation before commit, queued cancellation, failures, recovery and missing-task/commit-state API errors. Frontend build verified. Cancellation is cooperative between file operations; parsing a file is not forcibly terminated. Progress counts are phase-local (discovery/import/MLflow/verification), not an overall percentage. Jobs are designed for one local uvicorn process; multi-worker execution and distributed queues are out of scope.

Next Stage 3 increments: unified duplicate metric handling, TensorBoard tensor/restart coverage, verified dataset manifests, browser interaction acceptance and cache corruption recovery. Stage 4 remains pending; do not interpret this increment as completing all Stage 3 requirements.

## Scientific extensions increment

Implemented API-first energy drift, reference-error convergence, local secant sensitivity, exact linear covariance propagation; classification sample quality from SHA256-verified CSV/Parquet; append-only multi-level declared evidence for figure/table/claim/experiment. 18 tests pass. See scientific_extensions.md for input contracts and scientific limitations.

Still pending: scientific UI, persisted analysis records, artifact bytes/claim expression binding, report evidence integration, bidirectional standards adapters, remote compute, truly large-file importer, nonlinear/Monte Carlo propagation and physical flux models. This increment does not complete Stage 4.

## Local tracking increment

Implemented a separate WAL tracking journal, transactional CSV/JSONL cursor/record/metric batches, registered roots/ignores, watchfiles plus periodic reconciliation, stat-only artifacts, monitor diagnostics, SDK JSONL emitter, initial domain adapter interfaces and SQLite backup. See local_tracking_engine.md for exact scope and remaining P0/P1/P2 gates. 20 tests pass. Do not mark the complete Local Experiment Tracking Engine upgrade accepted: live parser coverage, rotation deduplication, actual crash injection, lifecycle detection and resource limits remain incomplete.
