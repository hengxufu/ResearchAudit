# Open-source research evidence — 2026-10-29

## Method and limitations

Public GitHub repository metadata, README and selected source files were retrieved through the connected GitHub tool. This is a focused implementation review, not a complete security or performance audit. Branch links are mutable. Latest push dates indicate repository activity, not release stability. No third-party source was copied into ResearchAudit. Costs below are engineering estimates; adapters must be version-tested before deployment.

## Priority projects

### MLflow — Apache-2.0; pushed 2026-10-29, not archived

[Repository](https://github.com/mlflow/mlflow), [Metric source](https://github.com/mlflow/mlflow/blob/master/mlflow/entities/metric.py), [SQL store](https://github.com/mlflow/mlflow/blob/master/mlflow/store/tracking/sqlalchemy_store.py).

README describes tracking, evaluation, model and artifact management. Source inspection establishes a Metric record with key/value/timestamp/step plus model ID, dataset name and digest. Constructor requires dataset name and digest together. SQLAlchemyStore separates experiment/run/parameter/metric metadata from artifact repositories and includes distinct latest metric entities and batch deduplication machinery. ResearchAudit should preserve metric history and explicit context instead of using a scalar as the entire metric. Prefer public tracking APIs for future remote integration. Local metrics format adapter is cheap but does not replace the complete tracking API. Full platform integration is medium/high cost and brings functionality outside this product's scope. A tracking record alone does not prove evaluation compatibility or numerical correctness.

### Aim — Apache-2.0; pushed 2026-10-28, not archived

[Repository](https://github.com/aimhubio/aim), [Run source](https://github.com/aimhubio/aim/blob/main/aim/sdk/run.py).

README emphasizes run comparison and query APIs. Inspected Run routes tracking to RunTracker; track accepts name, step, epoch and context, with homogeneous sequences. It accesses separate metadata trees, sequence abstractions and local/remote reporters; cleanup waits for queues and records end time. Useful design: context-qualified sequence identity, lifecycle-aware flushing, query/plot separation. SDK coupling and its native storage introduce medium/high integration cost, especially on Windows (README lists Linux/macOS). Do not claim measured performance superiority: storage benchmarks and frontend rendering internals have not been verified. Frontend architecture requires further source review before reuse.

### Sumatra — BSD-2-Clause core, bundled notices; pushed 2025-08-01, not archived

[README](https://github.com/open-research/sumatra/blob/master/README.rst), [records.py](https://github.com/open-research/sumatra/blob/master/sumatra/records.py), [LICENSE](https://github.com/open-research/sumatra/blob/master/LICENSE).

CLI smt, web browser smtweb and Python API target scientific simulation records. Record binds executable, repository, main file, version, parameters, input/output keys, launch mode, diff, duration and platform. register checks working-copy version and discovers dependencies; run records state transitions and finds produced data; RecordDifference compares code, parameters and data digests. Adopt explicit execution-versus-collection provenance and immutable snapshots. Post-hoc directory scanning cannot reconstruct its execution guarantees. Optional launch adapter would be medium cost; embedding its Django UI is unnecessary. README labels beta status and Windows testing limited. License also contains notices for bundled Django tagging/Cab code.

### noWorkflow — MIT; pushed 2026-10-26, not archived

[README](https://github.com/gems-uff/noworkflow/blob/main/README.md).

README describes automatic Python provenance through AST analysis, reflection and profiling without rewriting source, and wrapped non-Python execution records. Useful direction: optional execution tracing adapter, separate from retrospective file discovery. It cannot recover past execution events from absent evidence. Full instrumentation integration is high cost and requires Python compatibility and overhead testing. Two attempted collector paths (capture/noworkflow/now/collection/prov_execution/collector.py and noworkflow/now/collection/prov_execution/collector.py) were inaccessible; implementation details remain UNCONFIRMED. No collector algorithms are adopted based on those failed fetches.

### AiiDA — MIT (LICENSE.txt verified); pushed 2026-10-28, not archived

[Repository](https://github.com/aiidateam/aiida-core), [Node source](https://github.com/aiidateam/aiida-core/blob/main/src/aiida/orm/nodes/node.py), [License](https://github.com/aiidateam/aiida-core/blob/main/LICENSE.txt).

Scientific workflow engine centered on provenance and extensibility. Node has UUID identity and namespaces for attributes, extras, repository, caching and links. Source documents immutable attributes after store, with extras separately mutable; deletion rejects connected nodes. Adopt typed evidence entities, immutable content and explicit dependency edges. Importing the full workflow runtime is high cost relative to local retrospective auditing. Graph edges must represent observed or declared dependencies, never inferred causality from directory proximity. Link type validation and scheduler internals remain follow-up review areas.

## Secondary projects

| Project / verified license / activity | Function and model / inspected source | Reuse proposal, differences and estimated cost |
|---|---|---|
| [DVC](https://github.com/treeverse/dvc) / Apache-2.0 / 2026-10-26 | README.rst: Git-associated data/model versions, pipeline stages and affected-stage reruns; dvc/repo/__init__.py requested | Read .dvc and dvc.lock through isolated adapter; avoid invoking remote push. Medium cost; data versioning is not metric compatibility. Detailed repo implementation still needs review. |
| [ClearML](https://github.com/clearml/clearml) / Apache-2.0 / 2026-10-23 | README: experiment manager, orchestration, data management; clearml/task.py requested | Optional task export/API importer. SDK/service scope and automatic instrumentation increase integration cost (high). No automatic credentials or uploads. Full Task internals not reviewed. |
| [Sacred](https://github.com/IDSIA/sacred) / MIT / 2025-10-22 | README.rst and sacred/run.py inspected: config scopes/injection, observers, automatic seeding; Run stores config, host info, result and lifecycle state | Observer-style plugin boundary and file observer adapter, medium cost. Requires instrumented execution for full capture; retrospective discovery remains needed. |
| [Kedro](https://github.com/kedro-org/kedro) / Apache-2.0 (LICENSE.md verified) / 2026-10-28 | README: production data pipelines; kedro/pipeline/node.py requested | Explicit input/output dependency contracts; optional pipeline catalog adapter, medium cost. Pipeline authoring differs from automatic discovery. Node validation implementation not yet fully reviewed. |
| [Evidently](https://github.com/evidentlyai/evidently) / Apache-2.0 / 2026-09-29 | README and src/evidently/core/report.py: metrics, metric tests, report snapshots, dataset definitions, rendering and serialization separated | Structured rule results and separate report rendering; optional data-quality plugin, medium cost. Drift thresholds require scientific context; ML monitoring is not numerical simulation validation. |
| [signac](https://github.com/glotzerlab/signac) / BSD-3-Clause / 2026-10-29 | README and signac/job.py: statepoint hashing uses sorted JSON and MD5 for deterministic job addressing; separate metadata document | Adopt canonical content identity with SHA-256, not MD5 integrity assumptions. Import statepoint/document, low/medium cost. Parameter identity alone omits source and evaluator identity. |
| [RO-Crate](https://github.com/ResearchObject/ro-crate-py) / Apache-2.0 / 2026-10-14 | README and rocrate/rocrate.py: JSON-LD data/context entities, type dispatch, metadata profile/version detection, packaging | Preferred future portable evidence export via library; medium cost. Metadata packaging does not verify truth of claimed dependencies. Current ResearchAudit report is not a conformant crate. |
| [FiftyOne](https://github.com/voxel51/fiftyone) / Apache-2.0 / 2026-10-28 | README and fiftyone/core/dataset.py: Dataset/Sample/View abstractions, MongoDB-backed metadata and dataset listing/validation | Future sample-level failure-analysis adapter, high cost if embedding runtime. Avoid introducing MongoDB for MVP. Dataset inspection differs from run-level audit. |

All secondary repositories were unarchived at retrieval. Exact source paths in this table are review evidence or explicitly marked pending; requested files are not claimed fully understood. License metadata is repository-level only; distribution requires dependency and bundled-asset review. API/schema compatibility is preferred over source transplantation.

## Decisions

1. Preserve the existing stack and add contracts before adding more visual dashboards.
2. Distinguish imported observations, declared evaluation contracts, and independently verified facts.
3. Compatibility has UNKNOWN as a first-class outcome. Agreement is only declared metadata agreement.
4. Use stable run identities and content-addressed snapshots; retain provenance in reports.
5. Keep remote integrations and execution instrumentation opt-in; current import never uploads project content.

## Source follow-up

The noWorkflow collector was subsequently located and inspected at [src/noworkflow/now/collection/prov_execution/collector.py](https://github.com/gems-uff/noworkflow/blob/main/src/noworkflow/now/collection/prov_execution/collector.py). The earlier two paths failed because the current tree uses src/. Collector is called by transformed AST; it keeps evaluation/activation/dependency/file-access stores, supports partial-save frequency, wraps open calls, stores content_hash_before, and tracks still-open write files for after-state capture. This supports an optional execution-time adapter, not retrospective reconstruction. Instrumentation overhead and complete call semantics remain untested.

Additional retrieved source indexes confirm DVC Repo exposes lock_repo/locked, SCM context, data index and graph checks; Kedro Node exposes input/output properties, run dispatch and input-shape-specific runners; ClearML Task exposes init/create/query_tasks and artifacts/models/logger interfaces. These confirm modular API boundaries, but are not a complete review of their implementations. Prefer these public interfaces over importing internals.

## 3.0 interoperability follow-up — 2026-10-29

Jupyter Notebook format was checked against the [official v4 format description](https://nbformat.readthedocs.io/en/latest/format_description.html) and [v4 implementation](https://github.com/jupyter/nbformat/blob/main/nbformat/v4/nbbase.py). A notebook stores cells, execution counts and MIME-keyed outputs; multiline source/text can be a string or list. ResearchAudit independently reads the stored v4 JSON, records source/code hashes and imports plain text/application-json outputs. It never evaluates cells, trusts execution order as proof, or renders HTML. This is bounded format compatibility, not a complete nbformat schema validator, kernel integration or notebook execution engine. Upstream's [license](https://github.com/jupyter/nbformat/blob/main/LICENSE) is BSD-3-Clause. No upstream source was copied and the nbformat package is not made a dependency. Live documentation/source availability was verified; release cadence/support guarantees were not independently established in this follow-up.

HDF5 slicing was checked against [h5py dataset documentation](https://docs.h5py.org/en/stable/high/dataset.html#reading-writing-data) and the installed-version [3.14.0 Dataset implementation](https://github.com/h5py/h5py/blob/3.14.0/h5py/_hl/dataset.py). Dataset proxy indexing can use HDF5 selection without reading an entire field, unlike converting the whole dataset to an ndarray. The existing h5py dependency is reused with bounded selection; external/virtual storage and object arrays are refused. NPZ is explicitly treated as ZIP-member decompression, not advertised as arbitrary large-array lazy storage. Actual tests use h5py 3.14.0; current online stable documentation may describe a newer version. Performance claims come only from the repository benchmark, not upstream marketing.

The [ro-crate-py license](https://github.com/ResearchObject/ro-crate-py/blob/master/LICENSE) was rechecked as Apache-2.0. Existing independent RO-Crate reference-metadata support remains; neither this license check nor local tests certify full standard conformance or remote interoperability. MLflow local metrics, TensorBoard events, DVC references and Git adapters remain separate from the new Notebook adapter. Full upstream-server integration remains explicitly unverified.
