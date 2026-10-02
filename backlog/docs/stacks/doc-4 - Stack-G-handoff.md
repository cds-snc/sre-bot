---
id: doc-4
title: Stack G handoff
type: guide
created_date: '2026-10-02 17:11'
updated_date: '2026-10-02 17:37'
---
# Stack G handoff

Current state only. History is in git and in the task comments.

## Stack

- Name: Stack G, incident scribe (TASK-135). Trunk: `main` (stack cut from 8bcbf373).
- doc-2 line: Wave 4, "Incident reshape": TASK-135.1 -> TASK-135.2 -> TASK-135.3 -> TASK-135.4. doc-2 names Stack G on that line; the decision is also in the TASK-135 plan.
- Every layer is a behaviour-preserving refactor pinned by the TASK-36 legacy_surface suite, which must be green with no assertion change before and after each layer.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-135.1 | `stack-g/task-135.1-incident-core-transcript-reader` | none | ready | committed as d74e3290 (stack records) and 0724af46 (the layer); not submitted |
| 2 | TASK-135.2 | `stack-g/task-135.2-incident-summary-onto-core` | none | ready | committed as 5cee060e (records) and 9f57c514 (the layer); not submitted |
| 3 | TASK-135.3 | `stack-g/task-135.3-incident-draft-onto-core` | none | in progress | implemented, gates green, ACs 1 to 6 checked, notes on the task; not committed yet. Becomes `ready` once the human commits it |
| 4 | TASK-135.4 | `stack-g/task-135.4-incident-scribe-subdomain` | none | plan approved | merge into packages/incident/scribe; re-run its step 0 on top of layers 1 to 3 |

## Position

- Branch checked out: `stack-g/task-135.3-incident-draft-onto-core`, at 9f57c514 (same commit as layer 2's branch; layer 3 has no commit yet).
- Uncommitted work:
  - layer 3 (TASK-135.3): `app/packages/incident_draft/` (service, platforms/slack, adapters/slack, providers, domain, `__init__`, README), `app/contracts/operations/codes.py` (one line, `NO_DOCUMENT`), `app/pyproject.toml` (one temporary feature-independence ignore entry), `app/tests/unit/packages/incident_draft/` (new `test_incident_draft_conversation_draft.py`; slack, service, adapter-lookup and providers-document-store tests edited), `app/tests/integration/legacy_surface/` (conftest patches, the registration test's import and two setattr targets, INVENTORY line 115);
  - records: `backlog/tasks/task-135.3*` (status, notes, ACs) and this doc.
- Background agents: none.
- Baseline carried by every layer: legacy_surface 17 passed before and after; lint-imports 9 contracts kept; mypy 65 errors, none in touched files; the full single-process pytest run has 6 known order-leak failures (TASK-90: `test_webhooks_aws_sns.py` x3, `directory/test_google.py` x3) that pass in isolation and under `make test`. After layer 3 the full run is 6 failed, 3675 passed.
- After layer 3: `rg get_incident_channel_port app` and the `Port` rg over incident_draft and its unit tests both find nothing. The feature-independence contract carries two temporary ignore entries (incident_summary.service and incident_draft.service -> packages.incident.core.api); layer 4 removes both.
- For layer 4's step 0, two things layer 3 added beyond its plan: `NO_DOCUMENT` in the `ErrorCode` registry (`app/contracts/operations/codes.py`, required by `test_error_code_registry`), and a new unit test file `test_incident_draft_conversation_draft.py` that moves with the package's tests. Structlog `capture_logs` is order-dependent in the single-process run (TASK-90); assert log calls on a mocked module logger instead.

## Next actions

1. **human**: commit layer 3 and open layer 4's branch:

   ```shell
   git add backlog
   git commit -m "plan: record TASK-135.3 progress"
   git add -A app
   git commit -m "refactor: move incident_draft onto packages/incident/core (TASK-135.3)"
   gh stack add stack-g/task-135.4-incident-scribe-subdomain
   ```

2. **agent**: layer 4 (TASK-135.4) on `stack-g/task-135.4-incident-scribe-subdomain`: set In Progress, run its step 0 re-verification on top of layers 1 to 3, tests first, implement, gates (ruff, mypy with 0 errors in touched files, lint-imports, pytest tests --ignore=tests/smoke, legacy_surface before and after), the slice's rg checks, notes and ACs. It removes both temporary feature-independence ignore entries. Then hand over the commit.
3. **human**: `gh stack submit` (any time from now), review, and merge bottom-up one layer at a time with a re-approval per rebased layer (doc-2). Move each task to Done.

## Open decisions

None.

## Planning queue

Empty. All four layers have approved plans (human, 2026-10-02).
