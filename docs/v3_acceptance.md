# ResearchAudit 3.0 development acceptance — 2026-10-29

## Delivery status

This delivery is `3.0.0-dev.0`, a running, tested increment over commit `65a9466`. It does not claim all requested 3.0 capabilities are complete. No research data were uploaded, no remote Git push was performed, and tests use isolated `.test-runs-*` state rather than the user's existing experiment database. Source changes remain in the local working tree for review.

Core additions are actual backend functions connected to the existing nine pages: explicit reproduction and its independent scorecard, executable revisioned DAGs, bounded registered-asset browsing, training diagnosis/history, pose and driven-energy analysis, local structured queries/summaries, revisioned Claim–Evidence, and stored Notebook output intake. See [changed files](v3_changed_files.md), [architecture](v3_architecture.md), [API](v3_api.md), [user guide](v3_user_guide.md) and [phased plan](v3_implementation_plan.md).

## Automated verification

Local environment: Windows `10.0.26300`, Python 3.9.13, Node 24, NumPy 2.0.2, h5py 3.14.0, Polars 1.36.1. Tests run through the repository virtual environment. g++ was available; PyTorch was not installed. Browser tests use installed headless Microsoft Edge with temporary isolated profiles and a localhost server with its own temporary database.

| Check | Observed result |
|---|---|
| Baseline before implementation | 55 tests passed; TypeScript/Vite build passed |
| Full regression after v3 backend changes | **68 passed**, 14 Matplotlib/Pyparsing deprecation warnings, 46.65 s |
| Production frontend build | `tsc --noEmit` + Vite passed; main JS ~204.8 kB, gzip ~65.4 kB; lazy Plotly ~4.5 MB warning remains |
| Browser regression | **2 passed**, 18.3 s in the final run: prior nine-page lifecycle plus v3 replay/workflow/data/query/claim flow |
| Dependency audit | `npm audit --omit=dev`: 0 reported production dependency vulnerabilities at this run; not a security certification |
| Benchmark | Real dense HDF5/CSV and four executed DAG commands; raw measurements in v3_benchmark_result.json |
| Patch whitespace | `git diff --check` passed; Git emits ordinary LF/CRLF conversion notices |

Exact repeat commands:

```powershell
.\.venv\Scripts\python -m pytest -q --basetemp=.test-runs-v3-your-fresh-id
npm run build --prefix frontend
cd frontend
$env:PW_BROWSER_CHANNEL='msedge'
$env:PW_PORT='8028' # choose a free local port
npm run test:e2e
```

The benchmark is `python benchmarks/v3_benchmark.py`. Do not reuse a pytest basetemp containing personal files; pytest owns its test directory. Browser fixtures use `.test-runs-<UUID>` and never read personal project paths. Screenshots are ignored test artifacts under `frontend/test-results/`; no generated metrics are inserted into the normal user database.

## Four end-to-end acceptance scenarios

| Scenario | Actual computation and evidence | Boundary |
|---|---|---|
| A Reproduction | Execute a two-layer tanh network using NumPy, update weights for 40 iterations, collect actual MSE/checkpoint, capture entry source/Git/runner evidence, generate manifest, explicitly replay, compare final MSE, persist/download scorecard | Validates numerical training and replay; **not an actual PyTorch/CUDA run**. Full environment/data closure stays UNKNOWN |
| B Multi-model | Import six controlled CSV/config directories, identify model/seed/evaluation contracts, perform Welch/seed grouping, compare original numerical values, generate SVG/PDF, rank only compatible metrics; distribution comparison avoids a false equivalence PASS | Fixtures are explicitly TEST DATA, not claimed trained real-world models or causal evidence |
| C Scientific simulation | Execute Python and compile/run the supplied C++ program, collect time/energy/net-power, verify integral energy balance, source-column convergence of order 2 and adjacent-secant sensitivity | Exact controlled examples; no general FEM solver, PDE validation, or automatic boundary-condition proof |
| D Automation | Save and pin DAG revision, execute real command, resolve its snapshot/Run refs into descriptive statistics, audit, SVG and PDF; UI config independently executes import/audit/figure/report | Config/card editor and dependency multiselect, not a drag-and-drop graph editor. Restart does not checkpoint-resume computation |

## Additional tested boundaries

- Unauthorized replay/workflow start is refused. Same manifest cannot create duplicate replays. Entry-source changes are refused by default. An injected pre-enqueue failure leaves one durable Prepared reservation; an explicitly confirmed retry uses the same Pending execution.
- Workflow cycles, bounded retry failure, false conditions, invalid output references and blocked downstream tasks terminate correctly. Invalid references cannot retry forever. Parallel nodes have distinct execution IDs; cancellation terminates only their owned executions, leaving an unrelated Pending execution alone.
- Unfinished workflow records become Interrupted in recovery tests. Existing executor restart tests remain passing. This does not prove orphaned OS processes are dead after a whole-service crash.
- Legacy snapshot JSON is byte-meaning-preserved through additive v3 migration. Knowledge revisions reject stale writes; missing evidence is refused; support edges and prior revisions are queryable.
- Large-shape HDF5 metadata/slices work without allocating the logical full field. Path traversal, object NPZ, oversized previews, and HDF5 external links are rejected. Actual image thumbnails and bounded table offsets return real data.
- Pose q/−q equivalence, 90° geodesic rotation, translation norm 5 and explicit failure-index threshold are tested. Missing frame metadata is rejected.
- Stored Notebook code containing an intentional exception is imported without running it. HTML MIME output is omitted. Notebook field/source hashes and original execution counts are retained as unverified evidence.
- A generated one-page workflow PDF was additionally text-extracted with bundled pypdf and rendered with Poppler for visual inspection. Final loss 1.0, descriptive mean 2.0, method and source hashes were checked; table, wrapping and footer were legible. Poppler emitted a Symbol display-font notice, with no observed missing glyphs in this report. This manual artifact check is separate from the 68 automated tests.
- Existing continuous-append, partial-record, cursor rollback, restart catch-up, rotation, source identity, metric contract, numerical statistics, exports, offline package verification, scan exception isolation and cancellation tests remain passing in the full suite.

## Measured performance

One warm local desktop run; 24 logical CPUs, 34,124,718,080 physical-memory bytes. Workload: dense HDF5 with 4,000×1,000 float64 values (32,000,000 logical bytes; 32,022,328 on disk), a 100,000-row CSV, 30 separate 10×10 slices and a four-command DAG at executor concurrency two. Data generation is excluded. These are measurements, not guaranteed limits or endurance results.

| Operation | Measured |
|---|---:|
| HDF5 metadata | 18.07 ms |
| 100-element HDF5 slice, median / p95 | 4.66 / 5.58 ms |
| CSV offset 90,000, 50 returned rows | 22.87 ms |
| Four real commands via DAG | 2.320 s, Succeeded |
| Parent CPU during measured workload | 2.453 s |
| Sampled parent RSS growth, whole workload | 34,734,080 bytes (~33.1 MiB) |
| Parent I/O read / write counters | 14,351,410 / 710,345 bytes |
| Persisted metadata state | 108,544 bytes |

10 ms RSS sampling may miss peaks. Parent counters exclude children and do not represent physical disk traffic. Normal desktop/background load and warm caches are not isolated. The dense test file is 32 MB, not a multi-terabyte stress claim. The separate large-shape fixture is sparsely allocated and is **not** reported as dense-data throughput. Raw JSON and benchmark script preserve exact conditions; reruns will differ.

## Remaining work and known problems

1. Full target environment locking/reconstruction, PyTorch/CUDA/compiler self-report, container/venv preparation, complete dependency code snapshots, automatic immutable input binding, and checkpoint continuation are not complete. Entry files/executable hashes and runner metadata are bounded evidence only. Replay uses current cwd and referenced assets.
2. No Linux execution was observed in this local session. Existing Windows/Linux CI definitions are included but remote CI was not run. No long-duration endurance, power-loss certification, remote/HPC scheduling or hard OS CPU/memory enforcement was performed.
3. Actual framework-native best-checkpoint mapping, pose sample-ID/domain alignment, synchronized image/label review, advanced dataset semantic quality, automatic hyperparameter intervention, causal training diagnosis and per-model GPU bottleneck attribution remain partial/deferred. Device-level GPU telemetry is retained from v2; the test host did not validate PyTorch/CUDA training.
4. DAGs use built-in nodes and configuration/dependency cards. Runtime matrix expansion, plug-in node registration, drag/edge editing, distributed execution and safe process adoption across service crashes remain future work. A successful built-in audit node means the audit completed, not that every finding passed; use explicit result conditions when gating later work.
5. HDF5/NPY/NPZ bounds and lazy table pages are implemented; unlimited NPZ member decompression, object tensors, external HDF5/VDS access, automatic 3D mesh viewing and huge whole-array figures are not. Existing import materializes metric series in snapshot JSON and large append histories still incur prefix-hash I/O.
6. Natural-language queries use a small explicit grammar and current-snapshot scope. No general research chatbot or local/external LLM integration is claimed. Summaries are evidence-bounded descriptive records, not new statistical/causal conclusions. Knowledge search is substring-based and not yet project-scoped FTS.
7. Existing MLflow local metrics, TensorBoard, DVC metadata and RO-Crate reference adapters are retained. Full live-server/round-trip conformance remains unverified. Notebook import is a bounded v4 reader, not a full schema validator/kernel runner.
8. Reproduction reports currently export JSON and show a scorecard; the general experiment report still exports PDF/Markdown/HTML/JSON. A specialized reproduction PDF editor is not implemented. Bilingual advanced controls and large Plotly bundle are known UI/package limits.
9. A single-user local service is required. It can execute explicitly authorized programs with the user's permissions; it is not a sandbox. Program behavior outside managed output remains the responsibility of the configured command. Restarts do not silently execute commands or automatically install packages.

No untested feature above is presented as complete. Follow-up priorities are tracked in v3_implementation_plan.md.
