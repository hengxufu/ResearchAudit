# Verification record — 2026-10-29

- Command: .\.venv\Scripts\python -m pytest -q
- Result: 6 passed in 2.74s.
- Controlled fixtures are explicitly TEST DATA and generated in temporary directories.
- Coverage: CSV/YAML import, content hash, unchanged reimport identity, changed evidence new snapshot, old snapshot immutability, minimizing best metric, final vs last-finite, seed mean/sample SD, exact filters, differing dataset/evaluator definitions, missing metadata UNKNOWN, duplicate seed suppression, NaN audit FAIL, duplicate metric rejection, report snapshot/value consistency, missing directory/id error paths, conservation endpoint.
- Command: npm run build --prefix frontend
- Result: TypeScript checks passed, Vite built 32 modules. Plotly bundle ~4.83 MB uncompressed; code splitting still pending.
- Not verified: browser interaction, production packaging, large datasets, complete TensorBoard/MLflow variants, concurrent imports, PDF export.
- Prior dependency audit reported moderate/high issues in frontend tooling; remediation has not been verified in this change.

Latest verification: 11 passed in 6.42s, including real-format TensorBoard/MLflow and all three export formats. Matplotlib/Pyparsing emitted 14 deprecation warnings; no test failures. Frontend production build passes with the known large Plotly chunk warning. No browser interaction verification has been performed.

Historical registry update: 13 tests passed in 6.21s. Added revision persistence, stale-update conflict rejection, exact filters, snapshot linkage, report curation section and immutable-facts tests. 14 existing Matplotlib/Pyparsing warnings remain.

Background import increment: 16 tests passed in 6.55s. Includes success, queued/running cancellation without snapshots, restart interruption, failure persistence and API error statuses. Frontend production build passes. Browser interactions remain unverified.

Lifecycle upgrade verification: full suite 28 passed in 15.14s; subsequent execution metadata change passed four orchestrator tests in 6.14s. 14 pre-existing Matplotlib/Pyparsing warnings remain. Frontend TypeScript/Vite build passed (36 modules); large Plotly chunk warning remains. A browser-assisted run confirmed explicit Start, exit 0, stdout, live metric ingestion, result/audit opening and actual descriptive statistics. This is not an automated browser regression suite. Scale benchmark: benchmarks/lifecycle_result.json (1000 runs, 100000 observations, three real subprocess tasks). See docs/lifecycle_upgrade.md for limits and uncompleted stages.

## 2.0 verification (supersedes earlier counts)

Final suite: 55 passed in 26.64s, with 14 existing Matplotlib/Pyparsing deprecation warnings. Edge Playwright: 1 passed in 10.6s, including all nine pages, explicit command execution, source-backed results, audit, PDF and ZIP offline verification. TypeScript/Vite 8.3.5 build passes; lazy Plotly chunk warning remains. npm audit: zero reported vulnerabilities at verification time. Cross-platform CI is supplied but not claimed executed. Full scope and measured benchmark conditions are recorded in docs/v2_acceptance.md and benchmarks/v2_result.json.
