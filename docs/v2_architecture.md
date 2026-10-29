# ResearchAudit 2.0 architecture and migration record

## Decisions

Retain the working FastAPI/React/SQLite stack and all legacy routes. Add /api/v2 as a versioned application router with separate registry, assets, analysis, audit, plugins, reporting, integrations and telemetry modules. Split the old stacked frontend into nine page components with shared context, design tokens and lazy Plotly loading. No services or distributed database are introduced.

The execution database, tracking journal and snapshot registry remain separate local SQLite stores; cross-store references are explicit IDs, not cross-database atomic transactions. This limits migration risk but is not a fully normalized unified authority. SQLite WAL, busy timeouts, bounded execution concurrency and deterministic connection closing improve long-run reliability.

## Actual entities

Tracking projects own directory roots and persistent ignore rules. Experiments reference registered projects. Snapshot Run identity references source directory identity; execution Run IDs identify explicit command invocations and connect through output metadata/snapshot references. run_associations records append-only user-confirmed corrections. Automatic ambiguous directory associations remain UNKNOWN.

Assets identify local dataset/model/checkpoint/result paths. asset_versions contain immutable path/size/mtime manifests and optional full SHA256. asset_checks independently record integrity outcomes. Metadata-only equality is UNKNOWN; full hash comparisons can PASS for content integrity only. Source files are never copied by registration.

run_index(snapshot_id,run_id,name,params,metrics) provides SQL history pagination and filtering. indexed_snapshots supports lazy backfill of old JSON snapshots. Legacy runs without IDs receive deterministic derived IDs on read, with an identity-basis marker; original stored JSON remains unchanged. experiment_revisions preserves annotations separately.

analyses are content-addressed method/input/result/source records. figures retain original source mappings and specs. report_records identifies deterministic PDF output bytes, snapshot ID and included analysis IDs. research_evidence supports explicit figure/table/claim references. Provenance includes project -> experiment -> run, file -> metric -> analysis/figure -> report edges where records exist. Declared associations are labeled; no execution causality is fabricated.

## Persistent source transactions

Tracking source migrations add file_key, format and checked fields plus source_generations and tracking_settings tables. File identity carries cursor through unambiguous rename. Unsupported/ambiguous filesystem identity is not forced into a merge. Generation records retain initial path and committed-prefix checksum/byte length through truncation and overwrite. Records, metrics, cursor and generation hashes commit together. Fault injection exits the process both during normalization and after cursor UPDATE before transaction commit; restart tests verify no committed duplication or loss.

Unchanged completed files can skip reads for the configurable verification interval. Changed files strictly rehash committed prefixes and parse bounded suffix batches. This preserves strong overwrite detection but still costs O(history bytes) for continuously appended logs. Full chunk-tree/append-only mode optimization is future work. TensorBoard frames validate length and data CRC32C and keep partial frames pending. Scalars and scalar tensor summaries are handled; session/restart metadata is preserved without pretending repeated steps are independent runs.

Watcher events and timeout scans trigger reconciliation. API soft settings persist scan delay, verification interval, batch bytes and period. These are not OS CPU/I/O quotas. All reading is local, and normal collection never executes imported scripts. Model files are metadata-only in live tracking. CSV multiline records and oversized single records are rejected/flagged, not silently skipped.

## Execution and process control

Pending creation is separate from explicit enqueue. Priority queue dispatches at most two processes. Existing and edited dependencies are checked for cycles; random/grid batches remain Pending. Runtime uses shell=False, owned process handles, process-group/tree cancellation, timeouts, soft memory/log watchdogs and restart interruption. Watchdog failures transition directly to Failed after process exit confirmation, avoiding transient Cancelled states. Nonzero Windows DLL failures have explicit diagnostics. Python UTF8/unbuffered output defaults improve streaming; raw logs remain available and byte pagination preserves incomplete UTF8 sequences.

Execution metadata is nested under researchaudit_execution and imported into run.execution, separate from research parameters. This prevents unique execution IDs/timestamps from breaking seed grouping. Runner environment is not mislabeled as a full target dependency lock. Complete environment/container recreation remains unverified.

## Scientific methods

Source snapshots underpin all calculations. Descriptive analysis treats within-run observations as dependent history. Batch final metrics require compatible contracts before reporting pooled descriptive means. Independent inference uses explicit independent-run declaration, Welch t, effect size and seeded percentile bootstrap. Paired inference requires distinct recorded seed pairs and declared difference assumptions. Holm corrects an explicit selected family. Spearman and time trends are descriptive without epoch p-values. Pareto uses finite final values and explicit directions under compatible contracts. No method claims causality or scientific validity.

Audit evaluations persist rule version/layer/condition/evidence and configuration. Missing information yields UNKNOWN. Optional source hash verification is distinct from reproducibility. Physical ranges require matching units; missing observations never manufacture PASS. Numeric conservation/convergence/sensitivity/linear covariance checks remain separate bounded scientific APIs.

## Platform and operational limits

Default loopback only; trusted hosts and browser-origin checks protect against remote-origin execution requests. No authentication for hostile local clients is claimed. Keep one application process; multi-worker coordination is unverified. Soft resource watchdogs do not replace cgroups/Windows Job Objects. NVIDIA device telemetry is optional/cached/read-only and is not per-run GPU attribution.

Windows Python 3.9/Node 24 tests and Edge E2E were run locally. Linux CI is defined but not claimed executed. Full SSH/HPC scheduling, long soak testing, OS hard quotas, all-format streaming, signed archives, certified standard round trips, and full localization remain future gates.
