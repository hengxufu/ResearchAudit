# Local Experiment Tracking Engine — implemented increment

## Architecture

Existing snapshot collector, reports and analysis remain intact. backend/tracking is a separate live journal. Engine owns a serialized write lock and batched SQLite transactions; WAL and synchronous FULL are enabled on tracking.sqlite. Every batch atomically commits raw records, normalized metrics and its byte cursor. Parser failure rolls back the batch to a savepoint and preserves an error diagnostic. This is an in-process serialized writer, not yet a unified write queue across the legacy snapshot modules.

Projects register one resolved root each; multiple registrations provide multiple monitored directories. Run identity hashes project ID and relative parent directory. Directory association is inferred and pending confirmation. Source identity hashes project/path; overwrite/truncation creates a generation, preserving old observations. Records and metrics have compound uniqueness constraints (source,generation,ordinal[,metric]). No source project files are modified. Model and unsupported file types are stat-only artifacts and never deserialized, copied or content-hashed by this engine.

## Reconciliation and protocol

watchfiles triggers scans and periodic timeout scans reconcile missed events; WATCHFILES_FORCE_POLLING can force watchfiles polling on unreliable filesystems. Startup immediately scans registered roots. CSV and JSONL parse only newline-terminated records; incomplete tails remain pending and cursor does not advance. CSV multiline quoted records are intentionally unsupported and marked errors. UTF-8 is required. Full committed prefixes are rehashed to reliably detect same-size/middle overwrites; only suffixes are parsed. This improves integrity but is O(committed bytes) I/O per reconciliation, not a completed large-log optimization. Per-source suffix reads are bounded to 4 MiB. Records longer than this cap remain pending and need diagnosis; no automatic skipping.

Optional Python SDK: backend.tracking.sdk.RunLogger(path,run_id).log(metrics,step,state,units,definitions). C++ can append identical newline-delimited JSON objects. Raw fields are retained. The current engine partitions runs by directory, not SDK run_id; use one directory per run. SDK state is retained as raw evidence but run state currently remains unknown/inferred. It is not yet a completed lifecycle detector.

Renames appear as old-source deletion and new-source import. Historical copies remain associated with their paths: cross-path rotation deduplication is not implemented and no claim is made that both paths represent different experiments. Deleted source records are retained. Recreated identical files preserve the existing cursor. Crash safety follows transaction boundaries; tests reconstruct Engine after normal committed ingestion, not an injected OS process kill.

## API and UI

POST /api/tracking/projects {path,ignores:[glob]} registers/updates a root. GET /api/tracking/health reports projects, runs, source cursors/generations/status/errors and metric count. POST /api/tracking/reconcile forces a scan. GET /api/tracking/runs/{id}/metrics returns journal observations including all generations. The real monitor polls diagnostics every three seconds. Engine starts/stops in FastAPI lifespan; run one uvicorn worker only.

SQLite backup uses Connection.backup under writer lock. Restore is currently offline: stop service, retain old files, replace tracking.sqlite from a validated backup, then restart; no automated restore endpoint. Tracking data is local and no outbound network service is invoked.

## Domain boundary

DeepLearningTracker, PoseEstimationTracker and ScientificSimulationTracker preserve raw fields, supplied metric definitions, units and source. These are initial normalization interfaces, not specialized pose/FEM/physical-imaging analyses. They are not automatically wired into live ingestion yet.

## Verification and benchmark

20 tests pass, 14 pre-existing Matplotlib/Pyparsing warnings. New tests cover append/partial JSONL, partial CSV, restart catch-up, truncation generation, multi-directory identities, invalid records, deletion and backup readability. No source mutation by collector is used. Benchmark script and output are in benchmarks/. Windows build 26300, Python 3.9.13, warm local filesystem, one project, 10,001 metrics, 308,916-byte log, stat-only 128 MiB test model: first reconcile 0.2083 s; append reconcile 0.04093 s; total process CPU 0.140625 s; SQLite files 3,883,008 bytes. This does not measure event-to-UI latency, hardware I/O counters, peak memory or sustained CPU percentage.

## Not complete / next acceptance gates

Live plugin coverage is CSV/JSONL only. Legacy snapshot import still handles JSON/YAML/TensorBoard; live incremental JSON/YAML/TensorBoard/NPZ is pending. Stable Experiment entity, reliable execution lifecycle, Git/environment association for live runs, cross-path rotation deduplication, normalized protocol Run IDs, source-race detection, observer event coalescing, monitoring metric display, persistent retry/backoff, backup restore automation, full project management and long-path/network-filesystem tests remain pending. No CPU/read-rate hard throttling exists; concurrency is a single background worker and reads are capped per source. Snapshot Parquet/DuckDB remain available but live journal Parquet compaction/query has not been integrated. Database polling currently reads broad diagnostics; scaling needs indexed pagination.
