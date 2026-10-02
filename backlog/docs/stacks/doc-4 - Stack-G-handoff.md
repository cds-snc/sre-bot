---
id: doc-4
title: Stack G handoff
type: guide
created_date: '2026-10-02 17:11'
updated_date: '2026-10-02 18:02'
---
# Stack G handoff

Current state only. History is in git and in the task comments.

## Stack

- Name: Stack G, incident scribe (TASK-135). Trunk: `main` (stack cut from 8bcbf373).
- doc-2 line: Wave 4, "Incident reshape": TASK-135.1 -> TASK-135.2 -> TASK-135.3 -> TASK-135.4 -> TASK-135.5. TASK-135.4 was split after implementation for review size (human, 2026-10-02); doc-2 and the TASK-135 notes record it.
- Every layer is a behaviour-preserving refactor pinned by the TASK-36 legacy_surface suite, green with no assertion change before and after each layer.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-135.1 | `stack-g/task-135.1-incident-core-transcript-reader` | none | ready | d74e3290 (stack records) and 0724af46 (the layer) |
| 2 | TASK-135.2 | `stack-g/task-135.2-incident-summary-onto-core` | none | ready | 5cee060e (records) and 9f57c514 (the layer) |
| 3 | TASK-135.3 | `stack-g/task-135.3-incident-draft-onto-core` | none | ready | fda4d45d (records) and d902d38c (the layer) |
| 4 | TASK-135.4 | `stack-g/task-135.4-incident-scribe-subdomain` | none | ready | 6178aa7e: packages/incident/scribe added, not registered; about 7,500 added lines because a copy cannot be shown as a rename |
| 5 | TASK-135.5 | `stack-g/task-135.5-incident-scribe-switch` | none | ready | 5c5bcd37: hookimpls added, the two packages deleted; the records commit is still to make (Next actions 1) |

All five tasks and the parent TASK-135 are In Progress with every AC checked. No PR exists yet and no branch is on the remote.

## Position

- Branch checked out: `stack-g/task-135.5-incident-scribe-switch`, at 5c5bcd37.
- Uncommitted work, records only: `backlog/tasks/task-135*` (TASK-135 status, ACs and notes; TASK-135.4 rescoped; TASK-135.5 created), `backlog/tasks/task-25.10*` and `backlog/tasks/task-134*` (paths brought up to date), doc-2 (the Stack G line names five layers) and this doc. No code is uncommitted.
- Background agents: none.
- Gates at 5c5bcd37: ruff clean; mypy 65 errors, none in touched files; lint-imports 9 contracts kept; legacy_surface 17 passed; full single-process pytest 6 failed, 3678 passed, the 6 being the known TASK-90 order leaks (`test_webhooks_aws_sns.py` x3, `directory/test_google.py` x3) that pass in isolation and under `make test`. Gates on an export of 6178aa7e (layer 4 alone): the same, with 3973 passed.

## Next actions

1. **human**: commit the records on the top layer:

   ```shell
   git add backlog
   git commit -m "plan: record the TASK-135.4 / TASK-135.5 split and TASK-135 progress"
   ```

2. **human**: `gh stack submit`, review, and merge bottom-up one layer at a time with a re-approval per rebased layer (doc-2). Move TASK-135.1 to TASK-135.5 and the parent TASK-135 to Done as they merge.
3. **agent** (only if asked): address review comments on the layer they belong to (`gh stack checkout <branch>`, fix, then `gh stack rebase` by the human), never from a higher layer.

## Open decisions

For the reviewer; each is recorded in the task notes and can be reversed in a few lines.

1. TASK-135.5: one i18n resource registration instead of two. The registry deduplicates on path and would drop a second spec for the shared `locales/` directory with a warning at every boot; one registration loads both catalogues. Its logged `domain` field is `incident_scribe`.
2. TASK-135.4: three registration unit tests differ in body from their originals, because the merged `register_commands` makes two `register_command` calls.
3. TASK-135.5: hits for `incident_draft|incident_summary` kept in `app/` beyond i18n domains, settings aliases, log event names and locale file names: the settings getters, the Google Docs named-range prefix `incident_draft::` with the log context value `command="incident_draft"`, and test function names.
4. TASK-135.4: its commit labels the wrong task in three lines (the scribe `__init__.py` docstring and two pyproject comments say TASK-135.4 switches registration and deletes the originals; that is TASK-135.5). Layer 5 replaces all three, so nothing wrong reaches main; fix on layer 4 only if the PR text matters.

## Planning queue

Empty. Stack G has no further layer. The next critical-path task is TASK-110 (entry-point plugin loading), a standalone single PR from main per doc-2; it has no plan yet and should be planned against main after this stack merges, because it declares one entry point per plugin module and the scribe subdomain's is `incident.scribe`.
