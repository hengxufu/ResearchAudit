# ResearchAudit 2.0 acceptance and remaining work — 2026-10-29

This records actual development-version verification, not production certification. Version: 2.0.0-dev.0. Existing uncommitted lifecycle work and the prior per-file exception fix were preserved.

## Completed and verified in this iteration

| Area | Delivered capability | Evidence |
|---|---|---|
| Execution | Persistent state, priority/concurrency/dependency scheduling, explicit start/cancel/rerun, grid/random Pending batches, cycle checks | Real Python and locally compiled C++ tests; three-task concurrency tests |
| Control | Confirmed process-tree termination, timeout and soft memory/log watchdogs, failure diagnostics, restart interruption, UTF8 log pages and SSE | Running-process cancellation, soft-memory failure and Unicode boundary tests |
| Tracking | CSV/JSONL/CRC-checked TensorBoard incremental batches, partial-record deferral, identity/prefix-checked rotation, generation hash history, persisted settings | Real TFRecord, continuous half-line append, rotation and recycled-identity tests |
| Recovery | Atomic cursor/record/generation updates; SQLite authority and corrupt Parquet repair | Child process os._exit during normalization and after cursor UPDATE; restart exactly-once tests |
| Registry | Additive run index, SQL pagination, Project/Experiment/Run association history | Old schema preservation, indexed history and correction tests |
| Assets | Dataset/model/checkpoint reference registry, immutable versions, explicit SHA256, current verification, version comparison | Metadata UNKNOWN, hash PASS/FAIL and changed-source tests |
| Analysis | Run-level batch grouping, Welch/paired inference, seeded Bootstrap, effects, Holm, descriptive correlation/time trends, Pareto | Known numerical expectations, contract/duplicate rejection, persisted analysis tests |
| Audit | Persistent versioned integrity/reproducibility/comparability/numerical/evidence checks, unit-aware bounds, history/filter UI | Hash mutation and physical-unit mismatch tests; no false reproduction PASS |
| Domain parsing | CSV/JSON/YAML/Parquet/TensorBoard and bounded NPZ/HDF5 field summaries, original definitions and source hashes | Real CSV, NPZ/HDF5, persisted parser results and missing-value tests |
| Reports | Markdown/HTML/JSON plus deterministic PDF with analyses/source IDs; ZIP manifest, independent verifier, replot script | Regeneration checksum equality, archive tampering rejection and browser downloads |
| Frontend | Nine real pages, shared context, two themes, bilingual navigation, historical data search, paginated history, graph view, lazy Plotly | Browser lifecycle regression and TypeScript/production build |
| Resource/security | Process-tree RSS/cumulative CPU; cached read-only NVIDIA device telemetry; local host/origin boundaries | Actual RTX 4060 Laptop GPU read; API boundary tests |

## Actual automated results

- Final Python suite: **55 passed**, 26.64 seconds. The run used a fresh `.test-runs-<uuid>` workspace base directory because the agent sandbox restricts renaming inside its redirected Windows temp directory.
- Existing warning count: 14 Matplotlib/Pyparsing deprecation warnings, not test failures.
- Playwright Edge suite: **1 passed**, 10.6 seconds. The single test covers navigation across nine pages, Pending before explicit Start, actual CSV-producing command, completion/logs, statistics, figure rendering, audit, PDF download, offline ZIP checksum verification and theme change. Screenshots are in frontend/test-results/.
- Edge initially failed inside the restricted sandbox before navigation due to named-pipe/browser-launch isolation. The same isolated local test passed outside that restriction. This is documented as an environment issue, not a passing initial attempt.
- Production build: TypeScript and Vite 8.3.5 pass. Main application chunk ~182 kB; Plotly ~4.50 MB is lazy-loaded. A large Plotly chunk warning remains.
- npm audit after upgrading Vite: **0 vulnerabilities** at verification time. This is a point-in-time dependency audit, not a guarantee of future vulnerability absence.
- ReportLab 5 rejected Python 3.9 despite package installation; runtime requirements now constrain ReportLab >=4,<5 and validated 4.5.1.
- PDF visual QA: generated explicitly labeled TEST DATA report, rendered with Poppler, inspected PNG; fixed CJK/Latin spacing by embedding an available Windows Unicode font. Linux fallback visual QA remains pending.
- Windows local compiler execution is verified. GitHub Actions Windows/Linux matrix and Chromium E2E workflow are supplied but have not run remotely in this session.

## Reproducible measured scale

Script: benchmarks/v2_benchmark.py. Raw output: benchmarks/v2_result.json. Synthetic TEST DATA only. Warm local workspace temporary directory; Windows 10 build 26300, Intel64 Family 6 Model 183 Stepping 1, 24 logical CPUs, Python 3.9.13, concurrency limit 2.

| Measurement | Result |
|---|---:|
| Historical runs | 1,100 |
| Stored metric observations | 110,000 |
| Snapshot + Parquet + run-index ingestion | 0.162353 s |
| History page of 25 at offset 1,000 | 0.019923 s |
| DuckDB query of 100,000 observations | 0.191154 s |
| Three actual test commands | 1.811909 s; all Succeeded |
| Parent CPU time | 0.828125 s |
| Parent RSS | 139,116,544 bytes |
| Parent peak working set | 144,834,560 bytes |
| Parent I/O read/write counters | 3,737,698 / 2,422,548 bytes |
| Stored files | 1,004,565 bytes |

CPU/memory/I/O are parent-process counters, excluding child processes and other applications. File counters are OS-reported process I/O and not physical disk throughput. This is not an end-to-end UI latency benchmark, a cold-cache guarantee or a soak test. GPU sampling was separately observed and is not included in this benchmark.

## Not yet accepted / known limitations

1. Continuously growing logs still rehash their committed prefix in strict mode. Unchanged-file skipping helps idle scans, but append-only chunk-tree optimization and comprehensive I/O quotas remain unfinished.
2. Reliable identity-based rename is verified on this Windows filesystem. Cross-device moves, inode-less/network filesystems, ambiguous hard links and all rotation schemes are not certified; no forced merge is performed when identity/prefix does not agree.
3. Live JSON/YAML/NPZ/HDF5 are not streaming parsers. They use explicit snapshot/domain operations. Single-record batch bounds and multiline CSV restrictions remain. Multi-hour soak and full sustained-ingestion telemetry are pending.
4. There is no unified durable writer queue across all three stores, no cross-store atomic transaction, and no multiple-uvicorn-worker guarantee. Keep one local application process.
5. Memory/log watchdogs are soft sampling controls. OS-enforced CPU/memory/GPU quotas, Windows Job Objects, full orphan recovery, pause/resume and SSH/HPC scheduling remain pending. Restart never claims a stale process has been killed.
6. GPU telemetry is device-wide NVIDIA availability; per-run GPU attribution and non-NVIDIA implementations are not delivered.
7. Domain plugins perform useful bounded parsing/summaries, not full framework autologging, checkpoint weight introspection, SPEED/SPEED+ certification, mesh readers or physical imaging models. Models remain references by default.
8. Statistical assumptions are researcher-declared; methods are not auto-certified. Full multivariate/longitudinal/causal modeling, nonlinear uncertainty propagation and domain-specific ablation interpretation remain pending.
9. Nine pages are functional, but not every advanced API has a dedicated form. Navigation is localized; some content remains bilingual. Graph display caps at 100 nodes; figure editing is limited. Backend format exports use raw curves, not every interactive style. Full graph virtualization and scientific report composition remain pending.
10. DVC/RO-Crate operations are metadata-only. MLflow local metrics remain supported; complete bidirectional certified standard compatibility is not claimed.
11. Evidence packages verify internal checksums, not publisher authenticity or external dataset availability. Referenced raw files and complete target execution environments are not embedded; source paths can be present in exported metadata.
12. Deterministic PDF byte comparison is verified on the same environment. Different fonts/platforms may change bytes. HTML export is readable escaped report text rather than a rich page-composition engine.
13. Remote CI, Linux process-tree behavior, non-Windows font rendering and cross-platform E2E are configured or planned, not locally verified.

## Next production gates

Chunked prefix verification with documented mutation semantics; normalized cross-store task recovery; indexed paginated tracking queries throughout UI; cgroups/Job Objects; durable resource sampling; longer soak/kill/restart cases; full domain evaluation contracts; standard-library interoperability test suites; richer figure/report specifications; Linux CI results and complete localization. No production-complete label is applied before these gates pass.
