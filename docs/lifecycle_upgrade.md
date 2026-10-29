# Lifecycle workbench upgrade — implementation and acceptance record

## Repository audit and minimal-change path

Before this increment the app had immutable snapshots, basic comparison, rule-based audit, history annotations, import jobs, a partial CSV/JSONL live tracker, limited science checks and evidence references. It did not have process execution, a statistical workbench, or portable analysis records. Existing tracking Issue1 changes were retained. Existing endpoints and databases are preserved; no experiment source files are removed. New execution storage and additive analysis tables avoid destructive migration.

## Stage 1: foundations — partial

New execution_runs table lives in .researchaudit/execution/executions.sqlite with WAL, immutable creation specifications, timestamps, exit code, pid and snapshot reference. Existing snapshots/curation/tracking storage are reused rather than migrated speculatively into one universal schema. Tests verify an old snapshots table without fingerprint is upgraded without changing existing payload. Audit results now include rule_version, condition and layer. Five-layer audit is not complete: physical plugins and evidence records are separate APIs.

Live tracking limitations documented in local_tracking_engine.md still apply. This stage is not fully accepted.

## Stage 2: executable closed loop — functional increment

Create stores Pending only. Explicit POST start queues the command; a single scheduler dispatches up to two processes, sorted by priority and creation time. Dependencies must refer to previously created runs and only Succeeded dependencies unblock execution. Failed/cancelled/interrupted dependencies interrupt dependents. States: Pending -> Queued -> Running -> Succeeded/Failed; Pending/Queued/Running -> Cancelled; stale Queued/Running -> Interrupted on restart. Restart does not auto-execute queued commands or signal stale PIDs. Explicit rerun creates a new Pending record.

argv is a structured list; shell=False. Python/C++ binaries can be launched by absolute path. cwd must exist. Env overrides are passed only to explicitly started processes; output metadata records override key names (not values). Output directory and execution identity are supplied as RESEARCHAUDIT_OUTPUT_DIR and RESEARCHAUDIT_RUN_ID. Output roots register with live tracker at start. Processes should write results there; arbitrary outputs elsewhere are not auto-imported. Completion imports that output folder and links its immutable snapshot. Collecting results can fail independently and currently marks execution Failed with its exit code retained.

stdout and stderr are streamed by the OS to separate files; API reads bounded byte ranges. Process timeout is configurable. Cancellation targets the owned process group on POSIX and taskkill /T on Windows. Pause is unsupported and returns 409. Shutdown requests cancellation of active owned tasks. Hard CPU/memory limits, log rotation, Windows Job Objects, detached-child recovery and production process-tree guarantees remain pending. Execution specs may contain user-provided sensitive command arguments; avoid putting secrets there. This local service is not multi-user or sandboxed execution.

API: POST/GET /api/executions; GET /api/executions/{id}; POST /api/executions/{id}/start|cancel|rerun|pause; GET /logs?stream=stdout|stderr&offset=0&limit=65536. POST /api/execution-grid {spec,grid} creates up to 100 Pending combinations; {key} placeholders in argv are replaced; explicit starts remain required. Grid creation is not an all-or-nothing transaction on validation failure.

## Stage 3: analysis and audit — functional increment

/api/analyses/describe summarizes one source run series (count, missing/nonfinite, mean, median, range, sample SD and IQR outlier count). IQR flags are descriptive, not automatic data deletion. /api/analyses/paired accepts explicit left/right source references, requires >=3 distinct seed pairs and compatible dataset/split/protocol/metric contracts. Reused Run IDs across snapshots are rejected. Caller must explicitly attest independent pairs and approximately normal differences. Computes paired t, two-sided p, Cohen dz, t-based CI95, percentile bootstrap CI95 (2000 resamples, recorded RNG seed). No auto-selected tests, normality certification, epoch-as-replicate or causal claims. Constant differences are rejected because the t statistic is undefined. Multiple-comparison correction, correlation, learning-rate/checkpoint analysis and broad time-series inference remain pending.

Analysis payloads are immutable content-addressed SQLite records; GET /api/analyses/{id} returns methods, parameters and source evidence. Frontend exposes descriptive analysis; paired inference is API-only. Existing comparison and audit UI remains available.

## Stage 4: domain plugins — pending

Existing adapters preserve raw fields and definitions but are not complete PyTorch/SPEED/FEM integrations. HDF5/NPZ live import, GPU sampling, domain-specific protocols and extensive plugin validation remain pending. No dataset benchmark definition is hardcoded globally.

## Stage 5: report/export — functional increment

Existing Markdown reports and PDF/SVG/PNG figures remain. /report-export supports escaped HTML (readable preformatted report) and JSON. /package exports ZIP with snapshot, report, connected evidence records, relevant persisted analyses, curation, figure specifications, a standalone Matplotlib replot script and a SHA256 byte manifest. Raw datasets/weights are not copied. The package is a ResearchAudit reference archive, not a claimed RO-Crate implementation. It does not currently include execution stdout/stderr or a full dependency environment lock; offline regeneration requires Matplotlib/NumPy. Full PDF reports, rich HTML typesetting and curated selected-analysis report composition remain pending.

## UI and verification

Added a real execution control panel, bounded log viewer, result snapshot opening and descriptive-analysis panel; preserved existing registry and monitoring. Mobile sidebar is hidden to avoid squeezing content; form controls wrap. Nine separate pages, dark theme and full bilingual coverage are not yet implemented.

Automated API lifecycle test launches a controlled Python process, writes real CSV, captures output/exit, imports results, reads audit/report and matches source hashes. Other tests cover failures, dependency blocking, rerun identity, cancellation state, restart interruption, grid bounds, real three-task concurrency <=2, legacy schema migration, known paired mean, repeated-run rejection, archive hashes and HTML/JSON exports. Not yet tested: OS kill-in-flight, Linux process trees, C++ executable run, browser automated replay, SSE/WebSocket, very large live tracking histories.

Browser-assisted acceptance on localhost:8011 created a TEST DATA task, confirmed Pending before Start, then Succeeded/exit 0/stdout, live tracker two observations, opened result and computed mean 2 and sample SD 1.4142135623730951. Missing seed/evaluation metadata remained UNKNOWN. This was a one-time UI verification, not an automated cross-browser suite.

## Performance measurement

benchmarks/lifecycle_benchmark.py generated explicitly marked TEST DATA: 1000 historical runs, 100000 observations and three actual subprocess tasks with concurrency limit 2. On Windows build 26300, Intel64 Family 6 Model 183 Stepping 1, 24 logical CPUs, Python 3.9.13: snapshot import 0.2293 s, DuckDB full query 0.3713 s, three tasks 1.6499 s, parent process CPU 1.03125 s, peak tracemalloc allocation 51,814,895 bytes, total stored files 761,628 bytes. Warm temporary local directory. These memory/CPU figures exclude native/child allocations and are not total RSS or system CPU. Full output is lifecycle_result.json.

## Next gates

Finish live parser reliability/rotation/crash injection before claiming Stage 1 complete; harden executor termination/recovery and limits; add statistical design UI and corrections; normalized indexed registry; specialized plugin tests; report composition/PDF; complete browser replay and Linux CI. No full-stage completion claim is made for this increment.
