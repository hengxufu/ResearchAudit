# ResearchAudit 4.0 incremental architecture and API

Date: 2026-10-30. Baseline `2560306` was clean; 68 baseline tests passed in 46.43 seconds before development. Existing v1/v2/v3 routes and snapshots are retained. This is 4.0.0-dev.0, not completion of every requested roadmap item.

## Internal implementation phases

1. Audit the committed 3.0 platform, preserve its collector, executor, DAG, numerical contracts and document history.
2. Add bounded read-only project intelligence and reviewable associations, then historical backfill and opt-in continuous tracking.
3. Introduce versioned statistical methods, multipanel recipes and deterministic local Copilot tools.
4. Add dependency declarations/observed-runner comparisons and record complete service Python distribution inventory in new execution manifests.
5. Add historical-data grid/random/GP candidate generation, parameter constraints, execution budgets, explicit dispatch and result feedback into subsequent proposals.
6. Validate thermal radiation with an explicit equation, units and tolerances; retain existing conservation/convergence/sensitivity and C++ tests.
7. Connect tools to existing pages; run backend/browser regressions, fault injection and measured benchmark; document incomplete capabilities.

## Reused modules and boundaries

`backend/v4/projects.py` statically discovers file structure and imports, reads small configs and code (<=512 KiB), inventories files, and records Git status/history. It never imports project Python or runs build scripts. Models/data are stat-only. Discovery returns facts, inferred co-location candidates, errors and truncation. Corrections append user declarations with optimistic revisions. Backfill delegates to existing immutable snapshots; watch delegates to the existing watcher. Watch updates source/Run metrics; the project structure index is a point-in-time document and requires rescanning for refreshed structure.

`statistics.py` registers method version, assumptions, unit, source refs, seed and resamples. Independent strata are bootstrapped separately; paired conditions resample whole seed-block differences. There is no conversion of epochs into replicates. `figures.py` saves raw snapshot refs and explicit display transform settings and regenerates multipanel SVG/PDF/PNG. No hidden smoothing or interpolation is stored in original metrics.

`optimization.py` uses complete compatible source contracts and finite numeric parameters. It refuses uncontrolled differences outside search parameters and seed. Search supports grid, seeded random, and a fixed-RBF Gaussian-process posterior with expected improvement for one objective. Coordinates are normalized to [0,1]; kernel length scale .25, noise variance 1e-6, standardized EI exploration xi .01. Up to 200 observations, 6 parameters, approximately 512 pool points, 100 candidates/budget. A GP needs three distinct locations and nonconstant objective. Fixed-kernel uncertainty is not fitted/calibrated scientific coverage. Parameter-space constraints are linear upper bounds; outcome constraints are not learned. Multiple suggestions rank one pool, not joint batch EI or fantasy-updated suggestions.

Dispatch validates the ordinary ExecutionSpec, copies declared historical controls/evaluation definitions, rejects conflicting controls, substitutes parameter placeholders only in argv strings and requires confirmed=true. Suggestion never starts code. Budget is per proposal and counts reserved candidates, including failures/cancellations. A durable unique reservation is written before Pending execution creation; execution ID is recorded before enqueue. Duplicate requests reuse the same execution, and a Prepared/Pending retry enqueues that same ID. An interruption between reservation and execution-ID persistence is conservatively blocked for review, never automatically duplicated. The actual command must use supplied parameters and write into RESEARCHAUDIT_OUTPUT_DIR; metadata agreement cannot prove its internal behavior. Result APIs return original snapshot/Run refs, allowing next-round proposals to include the newly observed results.

`environments.py` imports exact pip pins and a bounded Conda subset. Unhandled includes, URLs, markers, ranges, Python/channel/build requirements are unresolved rather than executed. It compares declarations and historical runner distributions against the current service process. A matching service inventory does not establish target native/CUDA/toolchain closure. No environment installation, container build or notebook execution occurs.

`copilot.py` has allowlisted query/summary/audit/analysis_plan operations, scoped to one snapshot <=500 runs. Each operation calls deterministic APIs and persists evidence. No model connection, arbitrary SQL, shell, Python evaluation or network call is provided. A plan is explicitly PLAN_NOT_EXECUTED. Pluggable local/cloud model providers remain future work.

`science.py` implements gray-surface Stefan–Boltzmann power consistency with prescribed ambient temperature, emissivity, area and view factor 1. It checks K/K/W definitions and uses abs(residual)<=atol+rtol*abs(prediction). Physical applicability remains UNKNOWN even when numeric residuals pass. Existing v3 energy/power integration and source-backed convergence/sensitivity remain available.

## Persistence/migration and recovery

The existing research_documents table holds project_intelligence, project_backfill, optimization, environment_declaration, environment_comparison and figure_recipe. First v4 document write adds migration marker 4 and the following table inside the same transaction:

```sql
CREATE TABLE optimization_dispatch(
 proposal_id TEXT, candidate INTEGER, state TEXT,
 execution_id TEXT, spec TEXT, PRIMARY KEY(proposal_id,candidate)
);
```

No old payload is rewritten. Existing WAL, document revisions and snapshot hashes remain. Copy the full RESEARCHAUDIT_HOME only while the single backend is stopped for whole-state backup; external assets require separate backups. Executor/DAG restart remains conservative Interrupted, never automatic execution. Full workflow checkpoint resumption/cache validation is not implemented; v4 revision diff explicitly reports cache_reuse=false.

## API contracts

All routes below use `/api/v4`. `/docs` lists exact schemas. Unknown references return 404; invalid inputs/conditions return 422. Single localhost process and existing origin/host guards apply.

| Route | Contract |
|---|---|
| POST /projects/inspect | `{path,ignores:[],max_files:20000}`; max 100000 entries; creates versioned index |
| GET /projects | Latest bounded indexed project documents |
| POST /projects/{id}/associations | `{directory,experiment_label,reason,revision}`; recorded as user-declared |
| POST /projects/{id}/backfill | `{directories:[discovered directories]}` max100; persists per-directory snapshot IDs; repeat import deduplicates unchanged data |
| POST /projects/{id}/watch | Explicitly registers root with existing continuous tracker; custom discovery ignores do not automatically replace tracker settings |
| GET /environments/runner | Current service Python/package inventory; no target equivalence claim |
| POST /environments/import | `{path,kind:"pip"|"conda"}` file<=1MiB |
| GET /environments | Stored declarations |
| POST /environments/{id}/compare | Declaration vs current service; persists comparison |
| POST /reproductions/{id}/environment-diff | Historical reproduction runner vs current runner; target consistency UNKNOWN |
| POST /reproductions/{id}/target | `{executable:absolute_existing_path}` derives a new unstarted replay manifest, preserves parent ID/revision; existing v3 launch requires confirmed=true and allow_code_change=true for changed target |
| GET /statistics/methods | Versioned stratified-bootstrap and repeated-block-bootstrap definitions |
| POST /statistics/bootstrap | `{refs:[RunRef],metric,group_by:[parameter],paired:false,independent:false,seed:0,resamples:2000}`; explicit independence required; >=3 runs per stratum or >=3 complete seed blocks; max500 refs/10000 resamples |
| POST /optimizations | `{refs,metric,space:{x:[0,1]},algorithm:"bayesian"|"grid"|"random",count:3,budget:10,seed:0,constraints:[{coefficients:{x:1},upper:.8}]}` |
| GET /optimizations | Stored proposals including observations and acquisition provenance |
| POST /optimizations/{id}/dispatch | `{candidate:0,spec:ExecutionSpec,confirmed:false}`; authorization required; repeat IDs deduplicated |
| GET /optimizations/{id}/results | Actual execution states, snapshot/Run metric refs, remaining per-proposal budget |
| POST /figures | `{title,panels:[{label,refs:[MetricRef],smooth:1,scale:"linear"|"log",xlim?:[lo,hi]}]}` max6 panels,20 curves/panel |
| GET /figures/{id}/{svg,pdf,png} | Regenerate from saved immutable sources; response content SHA256 |
| POST /copilot | `{snapshot_id,operation:"query"|"summary"|"audit"|"analysis_plan",text:""}` |
| POST /science/radiation | `{snapshot_id,run_id,temperature,ambient,power,area_m2,emissivity,atol,rtol}` |
| GET /workflows/{id}/diff?left=1&right=2 | Added/removed/changed nodes plus version hashes; no cache reuse |
| GET /records/{kind} | Bounded environment_comparison/project_backfill/figure_recipe/optimization history overview |

RunRef is `{snapshot_id,run_id}`; MetricRef adds `metric`. Existing v3 reproduction, DAG, knowledge, data slicing, pose, energy balance and report contracts remain unchanged. New manifests add runner.distributions; older manifests remain readable, with missing inventory treated as incomplete.
