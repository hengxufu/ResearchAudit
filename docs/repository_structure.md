# Repository structure and maintenance conventions

## Source layout

```text
ResearchAudit/
  backend/
    main.py                   FastAPI application and legacy routes
    api/common.py             Shared HTTP helpers and request contracts
    core/documents.py         Canonical versioned document persistence
    tracking/                 Incremental collectors, parsers and SDK
    v2/                       Assets, analysis, audit, integrations and reports
    v3/                       Reproduction, workflows, data studio and knowledge
    v4/                       Project intelligence, optimization and newer analysis
    storage.py                Immutable snapshots and metric storage
    ...                       Existing domain engines and execution services
  frontend/
    src/
      main.tsx                Browser bootstrap and stylesheet import
      App.tsx                 Nine-page shell and shared snapshot context
      components/             Execution/history/tracking/basic analysis panels
      pages/                  Workbench feature panels
      shared/api.tsx          Fetch helpers, JSON display and polling hook
      styles/index.css        Global workbench styles and Tailwind layers
      plotly.d.ts             Plotly type declaration
    e2e/                      Browser acceptance tests
    index.html                Vite HTML entry
    *.config.*                Build, CSS and browser-test configuration
  tests/                      Backend tests and shared pytest initialization
  benchmarks/                 Controlled TEST DATA performance/verification scripts
  examples/                   Explicitly labeled numerical test programs
  scripts/check.ps1           Repeatable backend/build/browser verification
  docs/                       Architecture, APIs, guides and historical evidence
  .github/workflows/          CI configuration
  .researchaudit/             Existing local research state: preserved, ignored
  output/                    Existing exported artifacts: preserved
  .artifacts/                 Ignored disposable test/build-verification state
  .venv/                     Local Python environment
```

Version-numbered backend packages retain their current API generations and tested domain services. This cleanup does not change endpoint URLs or relocate all domain modules in one step. Shared contracts and document storage now have neutral homes; new cross-version code should import these directly. Further extraction of legacy main.py routes or domain services should be a separately tested change.

## Migration map

| Earlier location | Current location |
|---|---|
| frontend/src.tsx | frontend/src/App.tsx plus src/main.tsx bootstrap |
| frontend/{Execution,History,Tracking,Analysis}Panel.tsx | frontend/src/components/ |
| frontend/pages/ | frontend/src/pages/ |
| frontend/pages/shared.tsx | frontend/src/shared/api.tsx |
| frontend/style.css | frontend/src/styles/index.css |
| frontend/plotly.d.ts | frontend/src/plotly.d.ts |
| backend.v2.router shared Strict/RunRef/MetricRef/guard/executor definitions | backend.api.common; old router names still import/re-export them |
| backend/v3/documents.py implementation | backend/core/documents.py; v3 module is a compatibility shim |

HTML, TypeScript includes, Tailwind content globs, component imports, shared helpers and frontend bootstrap have been updated together. Existing backend.v3.documents imports refer to exactly the same function objects and database service, avoiding duplicate persistence implementations.

## Generated files and archive policy

- `.artifacts/test-runs/`: pytest UUID runs, browser test databases/data and temporary benchmark workspaces.
- `.artifacts/pytest-cache/`: pytest cache.
- `.artifacts/browser/results/`: Playwright results/traces.
- `.artifacts/browser/screenshots/`: browser acceptance screenshots.
- `.artifacts/archive/`: 55 earlier test/cache directories moved intact during cleanup. `manifest.json` records original and archived absolute paths. No archived content was deleted.

Collectors, asset traversal and Project Intelligence exclude `.artifacts` when scanning a project. Registering a specific test project inside that directory still works because paths are interpreted relative to the registered root. `.artifacts`, local state and environments are not committed. Existing output/ and .researchaudit/ were not moved or deleted.

Pytest now initializes its parent artifact directory before fixtures run. Without --basetemp it chooses a fresh UUID directory; callers supplying their own --basetemp should use a disposable test path. Pytest owns that base and may clear it on reuse. Benchmark scripts share benchmarks.paths.temporary_root(), while browser fixtures use the same workspace artifact convention.

## Verification commands

```powershell
.\scripts\check.ps1
# Browser channel is optional; configure it for the installed browser.
$env:PW_BROWSER_CHANNEL='msedge'
.\scripts\check.ps1 -Browser
```

Individual commands remain available: `.\.venv\Scripts\python -m pytest -q`, `npm run build --prefix frontend`, and `npm run test:e2e` from frontend/. Startup remains `.\start.ps1`; Linux startup and Python module imports remain unchanged.

## Documentation policy

Use [the documentation index](README.md) to distinguish current guides from historical acceptance records. Existing document paths, benchmark measurement JSON and versioned workflow templates remain intact. Do not move recorded research data or rewrite old benchmark numbers as part of folder cleanup.

## Cleanup verification — 2026-10-30

- Backend: **79 passed** in 51.42 seconds, including three new structural compatibility/isolation tests; 14 existing Matplotlib/Pyparsing deprecation warnings.
- Browser: **3 passed** in 21.8 seconds through isolated Edge/localhost, including original lifecycle, v3 replay/workflows and v4 takeover/optimization/export.
- TypeScript/Vite production build and Python compileall passed. Existing large Plotly chunk warning remains.
- Continuous-tracking benchmark smoke test completed with 10,001 records and a 128 MiB metadata-only model, using the new artifact workspace.
- 55 legacy test/cache directories were archived intact; local research state and existing output exports were preserved. New verification artifacts did not repopulate the top-level directory.
