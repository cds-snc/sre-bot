---
id: doc-4
title: Stack G handoff
type: guide
created_date: '2026-10-02 17:11'
updated_date: '2026-10-02 17:28'
---
# Stack G handoff

Current state only. History is in git and in the task comments.

## Stack

- Name: Stack G, incident scribe (TASK-135). Trunk: `main` (stack cut from 8bcbf373).
- doc-2 line: Wave 4, "Incident reshape": TASK-135.1 -> TASK-135.2 -> TASK-135.3 -> TASK-135.4. doc-2 names Stack G on that line (updated 2026-10-02); the decision is also in the TASK-135 plan.
- Every layer is a behaviour-preserving refactor pinned by the TASK-36 legacy_surface suite, which must be green with no assertion change before and after each layer.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-135.1 | `stack-g/task-135.1-incident-core-transcript-reader` | none | ready | committed as d74e3290 (stack records) and 0724af46 (the layer); not submitted |
| 2 | TASK-135.2 | `stack-g/task-135.2-incident-summary-onto-core` | none | in progress | implemented, gates green, ACs 1 to 5 checked, notes on the task; not committed yet. Becomes `ready` once the human commits it |
| 3 | TASK-135.3 | `stack-g/task-135.3-incident-draft-onto-core` | none | plan approved | incident_draft onto core |
| 4 | TASK-135.4 | `stack-g/task-135.4-incident-scribe-subdomain` | none | plan approved | merge into packages/incident/scribe; re-run its step 0 on top of layers 1 to 3 |

## Position

- Branch checked out: `stack-g/task-135.2-incident-summary-onto-core`, at 0724af46 (same commit as layer 1's branch; layer 2 has no commit yet).
- Uncommitted work:
  - layer 2 (TASK-135.2): `app/packages/incident_summary/` (service, handler, README, `__init__`; `providers.py` and `adapters/` deleted), `app/tests/unit/packages/incident_summary/`, `app/tests/integration/legacy_surface/` (conftest, the registration test's import and two setattr targets, INVENTORY line 116), `app/pyproject.toml` (one temporary feature-independence ignore entry);
  - records: doc-2 (the TASK-135 line names Stack G), `backlog/tasks/task-135.2*` (notes, ACs, status) and this doc.
- Background agents: none.
- Baseline carried by every layer: legacy_surface 17 passed before and after; lint-imports 9 contracts kept; mypy 65 errors, none in touched files; the full single-process pytest run has 6 known order-leak failures (TASK-90: `test_webhooks_aws_sns.py` x3, `directory/test_google.py` x3) that pass in isolation and under `make test`.
- After layer 2, `rg get_incident_channel_port app` finds incident_draft only; layer 3 removes those.

## Next actions

1. **human**: commit layer 2 and open layer 3's branch:

   ```shell
   git add backlog
   git commit -m "plan: name Stack G in doc-2 and record TASK-135.2 progress"
   git add -A app
   git commit -m "refactor: move incident_summary onto packages/incident/core (TASK-135.2)"
   gh stack add stack-g/task-135.3-incident-draft-onto-core
   ```

2. **agent**: layer 3 (TASK-135.3) on `stack-g/task-135.3-incident-draft-onto-core`: set In Progress, tests from its TEST MATRIX first, implement, gates (ruff, mypy with 0 errors in touched files, lint-imports, pytest tests --ignore=tests/smoke, legacy_surface before and after), the slice's rg checks, notes and ACs. Then hand over the commit and `gh stack add stack-g/task-135.4-incident-scribe-subdomain`.
3. **agent**: layer 4 (TASK-135.4), starting with its step 0 re-verification on top of layers 1 to 3. It removes both temporary feature-independence ignore entries.
4. **human**: `gh stack submit` (any time from now), review, and merge bottom-up one layer at a time with a re-approval per rebased layer (doc-2). Move each task to Done.

## Open decisions

None.

## Planning queue

Empty. All four layers have approved plans (human, 2026-10-02).
