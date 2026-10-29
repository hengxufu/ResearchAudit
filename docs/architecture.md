# Architecture and decision record

Historical initial architecture. Current additive v3 architecture and migration contracts are in [v3_architecture.md](v3_architecture.md); v2_architecture.md preserves the 2.0 decision record.

## Current system and migration

Keep React/TypeScript/Tailwind/Plotly, FastAPI, Polars and SQLite. The initial repository had one integration test, JSON snapshot storage, synchronous directory scans, scalar metrics and unstructured audit text. This change adds YAML parsing, deterministic run IDs, snapshot deduplication, metric contracts and registered audit rules without deleting old snapshots.

Modules: collect.py discovers evidence and normalizes observations; storage.py is the registry; analysis.py implements metric summaries, compatibility and rule registration; validation.py hosts physical validation plugins; main.py exposes APIs/report generation; frontend/src.tsx renders imported state. Visualization smoothing is display-only. Report exports source snapshots and the same analysis functions used by APIs.

## Contracts

One parent directory is currently one run. config.json/config.yaml/params.json stores seed, dataset, dataset_version, split, evaluation_protocol, model_version and arbitrary parameters. metric_definitions maps metric names to {direction: minimize|maximize, unit: string, method: string}. Unit '1' denotes dimensionless quantities. Metadata is author-declared, not proof of execution provenance.

Final means last observation, including missing final values; last_finite is explicitly separate. Best is computed only with an explicit direction. Repeated seeds suppress aggregate statistics. Seed grouping excludes only seed and otherwise requires identical parameters. Sample SD uses ddof=1. No inferential claims are made.

## Persistence

SQLite snapshots(id INTEGER PRIMARY KEY, created TEXT, root TEXT, payload TEXT, fingerprint TEXT). Existing tables migrate additively with PRAGMA column inspection. A unique SHA-256 fingerprint identifies canonical JSON payloads. Runs carry deterministic IDs based on resolved root and relative run path. Snapshots include source SHA256/size/path, parameters, observations, source mappings, Git state and collection environment. Metric-source CSV entries include column and observation count. No input weights are deserialized.

Parquet input works through Polars. Large-scale Parquet metric storage and DuckDB query pushdown are planned, not implemented. Snapshot JSON retains series for backward compatibility; this limits scale.

## HTTP

- GET /api/projects: snapshot index.
- POST /api/import {path}: scan and return id plus snapshot; unchanged canonical payload reuses id.
- GET /api/projects/{id}: immutable imported state.
- GET /api/projects/{id}/compare?metric=...&filters={...}: final/best, compatibility and seed groups. Filters are exact parameter equality.
- GET /api/projects/{id}/audit: rule/status/reason/evidence/suggestion records.
- GET /api/projects/{id}/report: Markdown with snapshot, comparisons and findings.
- POST /api/projects/{id}/validate/{plugin}?run=...&metric=...: physical plugin with source evidence.

PASS denotes rule-specific evidence satisfaction only. WARN is an actionable concern, FAIL an observed violation, UNKNOWN absent evidence. Static checks never establish reproducibility or scientific correctness. Version evidence is explicitly collection-time.

## Provenance and security

Current chain: snapshot -> run -> metric/summary -> source file SHA256 + column. Reports retain this chain. A future typed graph will distinguish used/generated/derived/declared edges and persist figure specifications, transformations and claim IDs. No causal execution graph is fabricated from scans.

Loopback only, no cloud uploads or imported-code execution. Symlink files/directories are skipped by the primary walker. Project files are not copied or archived. Existing MLflow secondary discovery and scan-time source changes need hardening. A production desktop service also needs host/origin controls, cancellation, import limits, and task isolation.

## New endpoints and persistence

GET /api/projects/{id}/figure?metric=...&kind=curve|distribution&format=pdf|svg|png exports original observations with no smoothing. X-Evidence-ID identifies the persisted figure specification. GET /api/projects/{id}/figures lists these specifications. GET /api/projects/{id}/graph returns observed import-derived edges, not inferred execution dependencies.

GET /api/projects/{id}/observations?metric=...&run_id=...&limit=10000&offset=0 queries the Parquet cache through DuckDB using bound parameters. Page limits are bounded to 100000. Each snapshot stores .researchaudit/metrics/{id}.parquet; SQLite JSON remains authoritative. Table figures(snapshot_id,evidence_id,spec) uses a composite primary key. Reports include exported figure specs.

## Durable local import jobs

backend/jobs.py owns import_jobs(id,path,status,processed,total,current_file,snapshot_id,error,created,updated). One ThreadPoolExecutor worker executes scans; a process-local lock protects cancellation/commit boundaries. Eight unfinished jobs is the submission limit. SQLite stores task state and startup marks stale queued/running/cancelling/committing jobs interrupted; it never silently resumes them. Successful jobs reference immutable snapshots. Raw files and credentials are never uploaded.

API: POST /api/import-jobs {path} returns 202; GET /api/import-jobs lists recent 50 tasks; GET /api/import-jobs/{id} retrieves state; POST /api/import-jobs/{id}/cancel requests cancellation. Queue full returns 429, unknown task 404, cancellation after commit begins 409. Statuses: queued, running, cancelling, committing, completed, cancelled, failed, interrupted. Progress is phase-local. Single uvicorn process required. Synchronous import remains available for integrations/tests.

## Current 2.0 design

See v2_architecture.md for the authoritative current modules, additive migrations, indexed registry, execution/tracking boundaries, immutable assets/analyses/reports, security scope and unresolved operational limits. The above sections are historical design records and contain superseded planned/implemented status statements.
