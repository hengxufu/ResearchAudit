# ResearchAudit 4.0 development acceptance — 2026-10-30

## Release scope

`4.0.0-dev.0` is an additive, verified stage over committed baseline `2560306`. It preserves the nine-page 3.0 platform, old APIs and existing scientific data. No remote push, research upload, automatic dependency installation or imported-code execution was performed. Changes remain local and uncommitted for review. This increment prioritizes project takeover, registered analysis, environment/replay evidence and historical-data optimization; the complete 4.0 roadmap is not declared finished.

Architecture, migration, API contracts and internal implementation phases: [v4_architecture_api.md](v4_architecture_api.md). Operations and exact limitations: [v4_user_guide.md](v4_user_guide.md). All modified paths: [v4_changed_files.md](v4_changed_files.md).

## Validation environment and results

Windows 10.0.26300, 24 logical CPUs, Python 3.9.13, local repository virtual environment, Node 24, existing NumPy/SciPy/Matplotlib/Polars stack. Installed headless Microsoft Edge uses isolated browser profiles and temporary localhost databases. Existing C++ tests use available g++ and the previously established static-link test configuration. No Linux/remote CI or PyTorch/CUDA acceptance was observed.

- Before development: 68 backend tests passed, 46.43 s. Starting Git tree was clean.
- **Final full regression: 76 passed, 14 existing Matplotlib/Pyparsing deprecation warnings, 49.71 s.** This includes the original 68 tests plus eight new v4 tests. The v4-specific suite including alternate interpreter also passed independently (8 passed, 12.03 s).
- Frontend `tsc --noEmit` and production Vite build passed. Main JS 214.29 kB, gzip 67.86 kB. Existing lazy Plotly bundle remains approximately 4.5 MB and emits the existing chunk-size warning.
- Browser regression: **3 passed in 20.0 s**, covering old lifecycle, v3 replay/workflows/data/evidence, and v4 project discovery/backfill → GP suggestion → explicit authorization → actual program execution/result refresh → saved SVG recipe/export.
- `git diff --check` passed; ordinary Git LF/CRLF notices remain.
- No new runtime dependencies were required.

Repeat:

```powershell
.\.venv\Scripts\python -m pytest -q --basetemp=.test-runs-v4-fresh-name
npm run build --prefix frontend
cd frontend
$env:PW_BROWSER_CHANNEL='msedge'
$env:PW_PORT='8035' # choose a free local port
npm run test:e2e
```

Tests use explicitly marked TEST DATA and isolated state. No real-world accuracy/performance finding is inferred from these controlled fixtures. Test commands execute only supplied test programs; imported project scripts remain unexecuted.

## A–E acceptance evidence

| Workflow | Actual processing and persistence | Evidence/boundary |
|---|---|---|
| A Historical takeover | Real Python/CMake/CSV/config/model formats, static discovery, pending associations, reviewed correction, repeated historical backfill, watcher registration | Entire controlled project's file-content hashes unchanged. Repeated backfill returns same snapshot IDs. Model index has no content hash. Truncation explicitly tested. Actual ResearchAudit source tree also indexed read-only |
| B Multi-model analysis | Six source-format experiments, stratified mean bootstrap and seed-block repeated-measure bootstrap; multipanel raw/smoothed SVG/PDF/PNG recipes; deterministic Copilot summary | Expected condition difference 1 and percentile interval [1,1] verified on controlled equal differences; no causal claim. Exports have correct signatures and content SHA256. Existing Welch/paired/multiseed tests retained |
| C Optimization | Three historical objective observations → constrained GP-EI candidates → explicit command → real squared-error output → results refs → next-round proposal using four observations | Suggestions create no executions. Unconfirmed dispatch refused. Repeated confirmed dispatch uses same execution ID. Per-proposal reserved budget measured; uncontrolled model differences rejected; seeded suggestions deterministic |
| D Reproduction/evidence | Exact dependency declaration intake, unresolved requirements, observed runner differences, full package inventory in new manifests; actual replay and tolerance report; alternate isolated Python interpreter replay | Real standard-library numerical program executed in a fresh pip-free venv after explicit target change authorization. Target sys.prefix differs and result agrees. Environment completeness and scientific correctness remain UNKNOWN; no automatic target dependency installation |
| E Simulation | Real Python gray-surface radiation program writes K/K/W series; equation-based residual validation with source evidence; incorrect emissivity triggers FAIL; analysis included in generated general PDF | Actual output agrees with declared equation under supplied conditions. Physical model validity UNKNOWN. Existing real Python/C++ energy, order-2 convergence, sensitivity and linear propagation tests remain passing |

The actual working-tree inspection reported **147 indexed files**, Python and C++ structures, one candidate directory, no discovery errors and no truncation at measurement time. This is a point-in-time codebase audit, not a representative external ML/FEM corpus. Summary: [v4_repository_inspection.json](v4_repository_inspection.json). Private configurations/source were not uploaded.

## Fault and numerical checks

- Injected failure before execution creation leaves a durable Reserved candidate. Repeat requests are blocked for review instead of starting duplicate work. Reserved budget stays consumed. Prepared/Pending reservations can explicitly retry the same execution ID; a non-Pending execution is never relaunched by duplicate dispatch.
- Bad command specs, degenerate parameter bounds, incomplete contracts, confounded historical controls, duplicate Run identities and arbitrary Copilot tool operations are refused.
- Existing source-hash/partial-write/cursor/rotation recovery, safe process cancellation, DAG retry/conditions, stale-revision protection and package-integrity tests continue in the full suite.
- Package equality pertains only to observed service inventories. Conda ranges/build/channel/Python constraints unsupported by the exact-pin reader remain unresolved. No PASS is synthesized for target environment closure.
- Bootstrap records method version, experimental unit, source IDs, explicit independence assumption, seed, number of resamples and percentile algorithm. It does not pool incompatible domains or treat training observations as independent Run samples.
- GP records historical observations, declared controls/space, linear parameter constraints, candidate pool algorithm, fixed kernel/noise/EI settings, predicted means and conditional posterior standard deviations. No hyperparameter fitting, optimality guarantee or output-feasibility guarantee is claimed.
- Radiation requires explicit K/K/W definitions, positive area, emissivity in [0,1], complete aligned series, nonnegative Kelvin temperatures and finite arithmetic; overflowing fourth powers are refused. Equation assumptions and source references are saved separately from physical validity.

## Measured benchmark

Script: [benchmarks/v4_benchmark.py](../benchmarks/v4_benchmark.py). Raw current measurement: [v4_benchmark_result.json](v4_benchmark_result.json).

| Quantity | Measured |
|---|---:|
| Files indexed | 1001 |
| Included model logical size | 1,073,741,824 bytes, sparse test artifact, stat-only |
| Read-only project discovery | 0.632105 s |
| Historical observations / GP candidate pool | 30 / 512 |
| Generate 5 GP candidates | 0.174246 s |
| Parent CPU, measured operations | 0.5625 s |
| Parent RSS before / after | 94,322,688 / 108,871,680 bytes |
| Parent I/O counters read / write | 1,335,801 / 561,287 bytes |
| Persisted state | 202,515 bytes |

Generation excluded; warm local desktop; one run; parent counters are not physical-device throughput; before/after RSS is not peak memory. The sparse 1 GiB model validates stat-only discovery, not dense-data throughput. Earlier trials differ (about .595 s discovery and .212 s GP); the table uses the saved final measurement. No long-duration endurance or multi-terabyte claim is made.

## Remaining roadmap — explicitly not complete

1. Full automatic cross-machine environment reconstruction, target-native/C++ toolchain and CUDA/driver closure, container build/run, Conda channel/build resolution and target self-report certification. Alternate-interpreter replay is tested on one Windows host with a standard-library numerical task; full framework/GPU portability is unverified.
2. Multi-objective Bayesian acquisition, learned outcome constraints, model/seed-aware noise fitting, global cost budgets, early-stop intervention, calibrated surrogate uncertainty and sensitivity-directed automatic campaigns. Current objective is scalar; constraints apply only to parameters; prior Pareto analysis remains available.
3. Large-scale restored DAG checkpoints, hash-validated reusable node caches, runtime matrix expansion and distributed scheduling. Existing conservative Interrupted semantics and limits remain; revision diff reports no cache reuse. One local backend process is required.
4. General LLM/local-model/cloud provider adapters, unrestricted language planning and autonomous execution. Copilot is a scoped deterministic tool dispatcher with finite query grammar, no model or network connection. It does not directly evaluate code/SQL.
5. New 3D point-cloud/mesh rendering, RGB/IR/channel-aware label synchronization, camera calibration management, pose-frame scene visualization, automatic multi-model prediction joins and semantic image quality. Existing v3 pose/data tools are retained, not presented as new comprehensive multimodal support.
6. Figure confidence bands, full publication template editor, automatic interpolation and robust figure caches. Current multipanel output exposes raw curves plus explicit trailing smoothing, scale and xlim. Data Studio's previous bounded HDF5/NPY/NPZ/table/image access remains; no new distributed lazy engine is claimed.
7. Arbitrary user-defined PDE/control-equation execution or a complete FEM validity system. The new thermal audit implements one declared radiation law, reusing existing energy/convergence/sensitivity/propagation. Model validation requires external scientific evidence.
8. Turnkey backup/restore and installer/service management, OS hard resource quotas, Linux runtime verification, endurance/power-loss testing and remote/HPC environments. Existing stopped-service full-state backup instructions remain applicable.
9. Expanded external scientific project acceptance corpus. Controlled format fixtures and the actual ResearchAudit repository were inspected; no user-supplied external training/FEM dataset was available or uploaded.

These gaps remain in the next phase. Prioritize environment reconstruction with target evidence, campaign-level optimization/budgets and stronger project-specific sample/evaluation identity before adding unrestricted automation.
