---
id: doc-4
title: Stack G handoff
type: guide
created_date: '2026-10-02 17:11'
updated_date: '2026-10-02 17:18'
---
# Stack G handoff

Current state only. History is in git and in the task comments.

## Stack

- Name: Stack G, incident scribe (TASK-135). Trunk: `main` (stack cut from 8bcbf373).
- doc-2 line: Wave 4, "Incident reshape": TASK-135.1 -> TASK-135.2 -> TASK-135.3 -> TASK-135.4. That line still says "standalone single PRs from main, no stack"; the human changed the delivery to this stack on 2026-10-02 (recorded in the TASK-135 plan). See Open decisions.
- Every layer is a behaviour-preserving refactor pinned by the TASK-36 legacy_surface suite, which must be green with no assertion change before and after each layer.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-135.1 | `stack-g/task-135.1-incident-core-transcript-reader` | none | in progress | implemented, gates green, ACs 1 to 5 checked, notes on the task; not committed yet. Becomes `ready` once the human commits it |
| 2 | TASK-135.2 | `stack-g/task-135.2-incident-summary-onto-core` | none | plan approved | incident_summary onto core |
| 3 | TASK-135.3 | `stack-g/task-135.3-incident-draft-onto-core` | none | plan approved | incident_draft onto core |
| 4 | TASK-135.4 | `stack-g/task-135.4-incident-scribe-subdomain` | none | plan approved | merge into packages/incident/scribe; re-run its step 0 on top of layers 1 to 3 |

## Position

- Branch checked out: `main` at 8bcbf373. No stack branch exists yet.
- Uncommitted work, all of it layer 1 or stack records:
  - layer 1 (TASK-135.1): `app/packages/incident/core/` (new), `app/tests/unit/packages/incident/core/` (new), `app/pyproject.toml` (the incident-umbrella contract);
  - records: `backlog/tasks/task-135*` (the TASK-135 delivery line, a re-verification comment on each slice, TASK-135.1 notes and ACs) and `backlog/docs/stacks/` (this doc).
- Background agents: none.
- Baseline for the stack: legacy_surface 17 passed before and after layer 1; lint-imports 9 contracts kept; the full single-process pytest run has 6 known order-leak failures (TASK-90) that pass in isolation and under `make test`.

## Next actions

1. **human**: create the stack and commit layer 1, then open layer 2's branch:

   ```shell
   gh stack init stack-g/task-135.1-incident-core-transcript-reader
   git add backlog
   git commit -m "plan: record Stack G for TASK-135"
   git add app/packages/incident/core app/tests/unit/packages/incident/core app/pyproject.toml
   git commit -m "feat: add packages/incident/core with IncidentTranscriptReader (TASK-135.1)"
   gh stack add stack-g/task-135.2-incident-summary-onto-core
   ```

   `gh stack submit` can run now (layer 1 goes to review while the rest is built) or once all four layers are committed.
2. **agent**: layer 2 (TASK-135.2) on `stack-g/task-135.2-incident-summary-onto-core`: set In Progress, tests from its TEST MATRIX first, implement, gates, the slice's rg checks, notes and ACs. Then hand over the commit and `gh stack add stack-g/task-135.3-incident-draft-onto-core`.
3. **agent**: layer 3 (TASK-135.3), same routine; then `gh stack add stack-g/task-135.4-incident-scribe-subdomain`.
4. **agent**: layer 4 (TASK-135.4), starting with its step 0 re-verification on top of layers 1 to 3.
5. **human**: `gh stack submit`, review, and merge bottom-up one layer at a time with a re-approval per rebased layer (doc-2). Move each task to Done.

## Open decisions

- doc-2's Wave 4 line for TASK-135 still says "Standalone single PRs from main, no stack". Should the agent update it (backlog doc update doc-2) to name Stack G?
- The stack letter G and the `stack-g/` branch prefix were chosen by the agent as the next free letter after doc-2's stacks A to F. Rename if another name is wanted.

## Planning queue

Empty. All four layers have approved plans (human, 2026-10-02).
