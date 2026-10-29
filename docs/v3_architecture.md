# ResearchAudit 3.0 development architecture

Updated 2026-10-29. This is a verified development increment, not certification of the entire 3.0 roadmap.

## Repository audit and decisions

The starting checkout was the committed 2.0 baseline `65a9466`. Its 55 backend tests and TypeScript/Vite production build passed before changes. It already contained the nine-page React workbench, SQLite snapshots and history index, Parquet/DuckDB metrics, the watchfiles/polling collector, shell-free process execution, statistical contracts, dataset versions, scientific checks, PDF/figure export and evidence ZIP verification. Those modules remain authoritative; v3 adds adapters rather than replacing them.

Retained technical debt: imported snapshot JSON holds whole series; changed live logs rehash their committed prefixes; the original collector hashes small model artifacts; executor resource controls are soft; plots load a large lazy Plotly bundle; some controls are bilingual rather than fully localized. No unsupported performance or full-environment claim was added.

## Modules and data flow

| Module | Responsibility | Reused foundation |
|---|---|---|
| `backend/v3/environment.py` | Bounded entry-code text/hash, Git patch and runner/target executable evidence | Git, existing explicit executor |
| `backend/v3/reproduction.py` | Versioned replay manifest, explicit replay, tolerance report, independent-run distribution comparison | Executions, snapshots, asset versions, SciPy |
| `backend/v3/workflows.py` | Validated versioned DAG, dependencies, conditions, retries, owned cancellation, exports | Shared executor, collector, statistics, audits, figures, PDF |
| `backend/v3/data_studio.py` | Asset-contained directory/table/image/array preview | Asset registry, Polars, NumPy, h5py, Pillow |
| `backend/v3/suites.py` | Training history, convention-aware pose errors, equation-based energy balance and source-column trends | Scientific checks, persisted analyses |
| `backend/v3/intelligence.py` | Inspectable training heuristics, finite natural-language query grammar | Metric contracts, immutable source snapshots |
| `backend/v3/knowledge.py` | Revisioned notes/designs/claims, support/conflict refs | Immutable analyses, figures, snapshots |
| `backend/v3/notebooks.py` | Stored Notebook v4 code/output evidence; no execution or HTML rendering | Registered assets, persisted analyses |

Data flow: explicit execution → managed output and execution evidence → existing collector → immutable snapshot → numerical analysis/audit → report/figure → versioned claim. Replay points to two immutable snapshots. A workflow pins its definition revision and content hash; every command node stores its own execution IDs. Importing a file or saving a workflow never starts a process.

## Persistence and additive migration

The existing `.researchaudit/audit.sqlite` remains the metadata database; WAL and busy timeout are retained. V3 lazily adds:

```sql
CREATE TABLE research_documents(
  kind TEXT, id TEXT, revision INTEGER, created REAL,
  payload TEXT, sha256 TEXT, PRIMARY KEY(kind,id,revision)
);
CREATE INDEX document_kind ON research_documents(kind,created);
CREATE TABLE workflow_runs(
  id TEXT PRIMARY KEY, workflow_id TEXT, revision INTEGER,
  state TEXT, created REAL, finished REAL, payload TEXT
);
```

Kinds are `workflow`, `reproduction`, `reproduction_report`, and `knowledge`. Revision writes use `BEGIN IMMEDIATE` plus an expected revision, refusing stale updates. SHA-256 identifies canonical JSON content. Schema migration marker 3 is additive. No imported snapshot payload, original parameter or metric is rewritten. Tests start with a pre-fingerprint legacy snapshot table and verify its stored JSON remains equal after v3 writes. `execution/executions.sqlite` and `tracking.sqlite` retain their existing schemas. Managed workflow files live in `.researchaudit/workflows/<workflow-run-id>/`.

Backup procedure: stop the one local server before copying the entire configured `RESEARCHAUDIT_HOME`, including execution output, workflow exports and SQLite sidecars. Dataset/model references remain external and need separate user-managed backups. The live collector's existing backup only covers its own SQLite database; it is not a whole-project backup API. Do not downgrade or delete tables as a migration step. A 2.0 application will not understand v3 records, but existing snapshots are preserved.

## Execution and recovery semantics

Use **one uvicorn process**. The shared executor bounds active commands to two; at most four DAG coordinators can run. Ready command nodes may run concurrently; built-in analysis/export nodes are serial within each DAG. They share the existing PDF lock. Command nodes accept the same timeout, dependency, soft memory and log limit fields as ordinary executions. There is no cluster scheduler or OS-enforced CPU quota.

Replay startup reserves a Pending execution in the durable manifest before enqueueing. A failure before enqueue leaves `Prepared`, so an explicitly authorized retry reuses that execution. A failure after enqueue can leave `Prepared` with a non-Pending execution: it must be inspected and cannot create another process through the same manifest. A new manifest is needed for another replay. Entry-source/Git checks and explicit input hashes run before launch; the override is recorded. Declared assets are references, not automatic command input binding.

Workflow command IDs are persisted before enqueue. Invalid references count as failed attempts; bounded retries cannot loop indefinitely on configuration errors. Failed/skipped dependencies block downstream nodes. False conditions skip their node; a workflow with only successful/skipped nodes succeeds. Cancellation marks the workflow terminal before terminating only executions recorded as owned by that workflow. Late workers cannot overwrite terminal workflow state.

On service restart, incomplete DAGs and Queued/Running executions become Interrupted. No command is silently retried, adopted through a stale PID, or re-executed from an imported notebook. For a service crash, previously spawned OS children are not proven dead; inspect them before an explicit rerun. Restart recovery is conservative bookkeeping, not process checkpoint restoration.

## Numerical and evidence contracts

Replay compares Run-directory names and final metrics with `abs(replay-original) <= atol + rtol*abs(original)`. A comparison requires an explicit metric tolerance plus matching dataset/version/split/protocol and metric direction/unit/method. Missing information is UNKNOWN. Zero original values have no relative-error value. The five scorecard dimensions remain separate, and scientific correctness is always UNKNOWN in this checker.

Distribution replay uses distinct run identities and at least three explicitly independent Run final values per group, KS, Wasserstein distance and a seeded bootstrap CI. Non-rejection is not equivalence; no automatic PASS is assigned without an equivalence design. Epochs never become independent replicates.

Training diagnoses expose window length, relative threshold, observed window means/differences, rule version and source evidence. PASS means a defined rule did not trigger, not that training is scientifically sound. Trend rules assume a minimizing loss and aligned observations. Causal diagnosis, automatic intervention and cross-domain causal explanations remain outside scope.

Pose evaluation requires xyzw/wxyz, active/passive convention, coordinate frame and translation unit. Both poses must already share that frame/convention and row order. Nonzero quaternions are normalized, geodesic angle is invariant to q/−q, translation uses Euclidean norm; optional caller thresholds select failure row indices. These are not automatically SPEED/ADD/ADD-S scores.

Energy balance integrates signed net power by the trapezoidal rule and checks `E(t)-E(0)-integral(P_net dt)=0`. Inputs must be aligned, finite, strictly increasing time and explicit J/W/s. Tolerance is `atol + rtol*max(abs(E0), max(abs(integral)))`. The caller must include all power/work/flux terms. Existing convergence uses reference-error log regression; sensitivity uses sorted adjacent secants. Source-column variants persist units and exact source refs. A trend check does not establish asymptotic convergence or a global sensitivity result.

## Bounded data access

Only registered assets are browsed; resolved paths must stay inside the asset. HDF5 slices use dataset indexing, no full-field reads, and reject external/virtual storage and soft/external links. NPY uses mmap. NPZ header-only inspection avoids reading all arrays; a selected numeric member may decompress at most 64 MiB. Previews allow at most eight dimensions, 100,000 elements and 8 MiB raw values. Object arrays are rejected and weights are never unpickled. Preview statistics describe only the requested slice.

CSV/Parquet use lazy bounded pages (up to 500 rows); high CSV offsets still require scanning. JSON lists/records are limited to 10 MiB. Images cap at 20 MP and thumbnails at 1024 px. These bounds control returned data, not a guarantee that malformed third-party file parsers have zero overhead. Previews are of the current referenced file; use version capture and verification for integrity evidence.

## Knowledge and graph

Claims carry supporting evidence, conflicting evidence, conditions and a human-declared validation state. Default is unverified. Reviewed requires support and a review reason; it remains a human statement. References validate existence; links to knowledge documents pin a revision. The v3 graph extends the v2 graph with support/conflict links and reproduction reports. The overview graph uses latest document display, labels pinned evidence revisions, and limits discovery to 500 documents per kind; historical content is available through revision APIs. Search is local substring search over versioned JSON, not an external model or unrestricted SQL.
