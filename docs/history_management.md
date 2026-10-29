# Historical experiments, conditions and variables

## Workflow

The Historical experiment registry panel lists runs across imported snapshots. Search matches imported parameters and curated title, conditions, variables and notes. Tag and review-state filters are exact matches. Select Manage to edit a historical record, or Results to open its source snapshot. After a new import, use Search / refresh to refresh the registry.

Each field records a name, value, unit and source. A condition describes the experiment setting (for example temperature, hardware, solver tolerance). A variable additionally declares its role: independent, dependent, controlled or confounder. Roles are research declarations and do not establish causality. Unit strings are stored literally; no conversion or dimensional-equivalence claim is made.

Title, tags, review state and notes are also versioned. reviewed is a user workflow state, not a scientific validation result. archived hides nothing by default; use the review-state filter to select archived or active review states.

## Evidence boundaries

Original snapshot parameters, metrics and hashes are immutable. Curated metadata is stored separately, keyed by snapshot and run ID. New snapshots do not inherit declarations automatically: conditions from one historical version must not silently apply to another. Same-run history links stable run IDs within the same resolved project path. Moving/renaming a directory currently creates a different identity.

Every save appends a revision with server UTC timestamp. Optimistic concurrency requires expected_revision; stale saves return 409. Use a previous revision as a draft and save to append a new revision instead of deleting history. Revisions currently have no user identity because the app is a local single-user service.

Reports include the complete curation revision history in a separate user-declared section. Curation does not change comparison contracts or audit outcomes. A source field documents the user's stated evidence reference; it does not hash or independently validate a referenced notebook or external URL.

## Storage and API

SQLite table experiment_revisions(snapshot_id,run_id,revision,created,payload), composite primary key. Existing databases migrate lazily and retain all snapshots.

- GET /api/history?q=&tag=&status=&limit=100&offset=0 returns total and page items.
- GET /api/history/{run_id} returns this run across snapshots.
- GET /api/projects/{id}/runs/{run_id}/revisions returns newest-first curation revisions.
- PUT /api/projects/{id}/runs/{run_id}/annotation accepts expected_revision, title, tags, status, conditions, variables, notes.

Condition fields: name, value, unit, source. Variable adds role. Conditions/variables require nonempty unique names and a source; roles and review states are validated. API rejects unexpected fields and bounds collection/text lengths. Empty sources are rejected; narrative accuracy remains the author's responsibility.

## Limits

Historical search currently reads JSON snapshots and supports server pagination after filtering. It is intended for MVP-sized registries; normalized SQL indexes, typed numeric/range queries, cross-run condition matrices, reusable condition templates, bulk curation and explicit cross-project identity merging remain follow-up work. UI value fields are textual; API can retain finite numeric and boolean values. Unsaved editor content is not persisted; save before switching records.

## Verification

13 tests passed (6.21 seconds), including revision append/retrieval, conflict rejection, search filters, immutable imported facts, report inclusion, historical snapshot linking, no automatic declaration inheritance and invalid role/duplicate-field rejection. Frontend TypeScript and production build pass. Browser interaction has not been automated.
