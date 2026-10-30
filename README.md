# ResearchAudit 4.0 development workbench

Repository organization: [source layout, compatibility and generated-file conventions](docs/repository_structure.md). Documentation navigation: [docs index](docs/README.md). Run `.\scripts\check.ps1` for backend tests and frontend build; generated verification state is centralized under `.artifacts/`.

Current incremental release: **4.0.0-dev.0**. See [v4 architecture and API](docs/v4_architecture_api.md), [v4 user guide](docs/v4_user_guide.md) and [v4 acceptance/remaining work](docs/v4_acceptance.md). Project Intelligence, historical-data optimization, registered bootstrap, multipanel recipes, environment comparisons and local allowlisted Copilot tools extend the existing platform. The sections below preserve the 3.0 foundation and its operational constraints.

ResearchAudit is a local-first scientific experiment workbench. Its preserved 3.0 foundation provides explicit experiment replay, executable workflows, bounded scientific data browsing and versioned research knowledge. The current 4.0 development increment extends those functions without claiming every roadmap gate is complete. It runs real commands, imports real files and stores auditable results. It does not upload research data automatically.

Start with [the v3 user guide](docs/v3_user_guide.md), [architecture](docs/v3_architecture.md), [API contracts](docs/v3_api.md), [phased plan](docs/v3_implementation_plan.md) and [acceptance/remaining work](docs/v3_acceptance.md). The nine existing pages and older API contracts remain available.

## Install and start

Validated locally on Windows, Python 3.9.13 and Node 24. Python 3.9+ and Node 24 are recommended for this source tree. Linux/Windows CI definitions are included, but remote CI results have not been observed.

```powershell
cd D:\ResearchAudit
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm ci --prefix frontend
npm run build --prefix frontend
.\start.ps1
```

Open http://127.0.0.1:8000 ; API documentation is at /docs. Use one uvicorn process. For frontend development run `npm run dev --prefix frontend` while the backend listens on 8000. Linux uses `.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.

## Nine connected pages

Dashboard shows real execution and resource counters. Project Explorer imports projects and manages datasets/model references and experimental associations. Experiment Center creates Pending commands and starts them only on explicit action. Run Explorer searches/paginates historical records and versions curation. Analysis Studio computes source-backed descriptions, batch summaries and declared paired/independent comparisons. Figure Studio overlays real series with box/violin/heatmap views. Provenance Explorer shows source/experiment/analysis/figure/report links. Audit Center stores versioned checks and source verification. Report Center exports Markdown/HTML/JSON/PDF and evidence ZIPs.

Navigation supports Chinese/English page names, light/dark themes, shared snapshot context and search across historical run metadata. Some explanatory text and advanced controls are still bilingual rather than fully localized.

## Execute a research program

Enter an existing working directory and a JSON argument array, for example `["D:\\tools\\python.exe", "train.py"]`. Create only saves Pending configuration; Start is required to execute. Python and C++ executables use the same shell-free process interface. Program outputs intended for automatic ingestion should be written to the `RESEARCHAUDIT_OUTPUT_DIR` environment directory. `RESEARCHAUDIT_RUN_ID` is also provided. Standard output/error stream to bounded-read APIs; a configurable soft log watchdog limits growth. Pause is unsupported and rejected.

API execution specs support priority, dependencies, timeout, optional soft memory limit and parameters. Grid and seeded random searches create Pending drafts. Dependency updates detect cycles. Restarts mark stale active/queued records Interrupted and never silently relaunch commands. Process-tree termination is tested locally; Windows Job Objects, OS-enforced CPU/memory quotas and remote scheduling are not implemented. The app is a local single-user execution service, not a security sandbox.

## Data and numerical contracts

CSV/Parquet numeric columns and JSON metrics feed immutable snapshots. TensorBoard and MLflow local metrics have existing import adapters. Live tracking supports CSV, JSONL and CRC-checked TensorBoard frames, persistent cursors, source generations, identity-based rename/rotation handling, periodic validation and ignored directories. Models are stat-only in live tracking. Unchanged logs skip content reads until periodic verification; changed logs still rehash committed prefixes for strict integrity. Very large append histories therefore still have an I/O scaling limit.

Each run config can declare:

```yaml
seed: 42
dataset: experiment-dataset
dataset_version: v1
split: validation
evaluation_protocol: evaluation-v1
model_version: baseline
metric_definitions:
  loss:
    direction: minimize
    unit: "1"
    method: mean squared error
```

Final is the last observation, including missing values; last_finite is separate. Best requires a direction. Missing evaluation contracts yield UNKNOWN. Statistics operate on run-level final results for inference; Epoch observations are descriptive only. Independence/normality assumptions are explicit and never certified automatically. Physical bounds require matching units. Successful execution does not establish scientific correctness.

Assets use metadata-only versions by default; explicit full hashes and integrity checks do not copy datasets or weights. Historical curation and experiment association corrections are stored separately from imported facts.

## Persistence and exports

State lives under .researchaudit (override with RESEARCHAUDIT_HOME). SQLite stores metadata, analyses, audits and source cursors; Parquet caches metrics for DuckDB. SQLite snapshots remain authoritative and corrupted metric caches are rebuilt. Existing schemas migrate additively. Reports preserve source references and methods. PDF regeneration is deterministic for unchanged inputs on the same environment. Evidence ZIPs include checksums and a replot script; external datasets/weights are referenced.

Independently verify an archive without extracting or executing its contents:

```powershell
python backend/v2/verify_package.py path\to\researchaudit.zip
```

DVC metadata intake and RO-Crate reference-metadata export/intake are provided. These do not implement DVC remote fetching or complete certified RO-Crate/MLflow round-trip compatibility.

## Verification

```powershell
.\.venv\Scripts\python -m pytest -q
npm run build --prefix frontend
cd frontend
$env:PW_BROWSER_CHANNEL="msedge"
npm run test:e2e
```

For Chromium instead, run `npx playwright install chromium` and omit PW_BROWSER_CHANNEL. E2E creates an isolated database, starts localhost, launches a controlled TEST DATA program and verifies navigation, execution, statistics, figures, audit, PDF download and ZIP integrity. Pytest automatically selects a fresh workspace directory under `.artifacts/test-runs/`; browser data, traces and screenshots use `.artifacts/` too.

Benchmarks: `benchmarks/v3_benchmark.py` and `docs/v3_benchmark_result.json`; the v2 benchmark is also retained. All benchmark/fixture data are explicitly TEST DATA. See docs/v3_acceptance.md for measured results and remaining limits.

## Engineering documentation

- docs/v2_architecture.md: architecture, data model, migrations and operational boundaries.
- docs/v2_api.md: added endpoint contracts.
- docs/v2_acceptance.md: coverage, benchmark conditions and uncompleted requirements.
- docs/open_source_research.md: source research and license notes.
- docs/local_tracking_engine.md and docs/lifecycle_upgrade.md: historical implementation records; newer v2 documents supersede their status statements.
- docs/v3_architecture.md: current modules, data model, additive migration and recovery semantics.
- docs/v3_api.md: reproduction, workflow, data, suites, diagnostics and knowledge contracts.
- docs/v3_user_guide.md: operations, controlled examples and workflow templates.
- docs/v3_acceptance.md: measured tests, benchmarks and explicit limitations.
- docs/v3_implementation_plan.md: phased progress and remaining priorities.
