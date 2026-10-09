---
id: doc-10
title: Stack J handoff
type: guide
created_date: '2026-10-09 18:23'
updated_date: '2026-10-09 19:52'
---
# Stack J handoff

## Stack

- Name: Stack J, incident rebuild group A: the umbrella moves to `features/incident/` and the status-update code is cleaned and carved out as `comms`. Trunk: `main` (7cb97921 since #1577 merged). gh stack #1578.
- doc-2 line: Wave 5, "Legacy rebuild by surface": Stack J is TASK-145.1 -> TASK-145.2 -> TASK-145.3 -> TASK-145.4. The stack implements group A of coordinator TASK-145; backlog doc-9 holds the whole chain.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase. Layer 4 is the last layer of this stack; groups B to E are later stacks (Planning queue).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | TASK-145 plans (docs only) | `stack-j/plan` | #1576 | merged | Plans for TASK-145.1 to 145.13 (1-6 grounded in code; 7-13 outlines to re-ground at pickup). |
| 1 | TASK-145.1 move packages/incident to features/incident with the first-mover wiring | `stack-j/task-145.1-move-incident-to-features` | #1577 | merged | Squash 7cb97921 on `main` (2026-10-09). Task Done. |
| 2 | TASK-145.2 wording and prompt text out of the views module; translator through core.api | `stack-j/task-145.2-status-update-wording` | #1579 | in review | dd779db, PR base `main`, review required. Task In Progress, ACs checked. After merge: `backlog task edit 145.2 --status Done` (human). |
| 3 | TASK-145.3 one service call per status-update handler | `stack-j/task-145.3-status-update-handlers` | #1580 | in review | 376b7b1 (the layer) plus ea2ad8f (docs-only severity 0-4 update across the incident docs, tasks and `decisions/incident-management.md`, committed on this branch). PR base layer 2, review required; the PR title is the default branch name (Next action 1 renames it). Task In Progress, ACs checked. |
| 4 | TASK-145.4 carve `comms` out of scribe as plugin `incident.comms` | `stack-j/task-145.4-comms-subdomain` | - | ready | Implemented 2026-10-09, gates green, all five ACs checked, notes written (deviations listed there), task In Progress. Uncommitted until Next action 1. Ids are now `incident.comms.status_update.*`: deploy in a quiet window, open modals stop responding. |

## Position

- Checked out: `stack-j/task-145.4-comms-subdomain` (on ea2ad8f, layer 3).
- Uncommitted, all for layer 4: new `app/features/incident/comms/` (whole files moved with `git mv` from scribe and staged as renames; the split modules are new untracked files), trimmed `app/features/incident/scribe/`, `app/features/incident/README.md`, `app/pyproject.toml` (entry point, layers contract), tests moved to `app/tests/{unit,integration}/features/incident/comms/` (the integration scribe directory is gone), `app/tests/integration/{server/test_lifespan_plugin_loading.py,legacy_surface/conftest.py,legacy_surface/INVENTORY.md}`, `decisions/incident-management.md`, `backlog/tasks/task-145.4*` (status, ACs, notes), `backlog/tasks/task-140.11*` (re-ground note: status-update paths moved to comms), this doc.
- Never stage: `backlog/docs/doc-6*`, `backlog/docs/doc-8*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md` (working files, not kept in the repo).
- Gates on layer 4 (from `app/`): ruff check and format clean; lint-imports 10 kept, 0 broken; mypy 48 errors in 19 files, 0 in touched files; pytest `tests --ignore=tests/smoke` 4607 passed.
- No background agents.

## Next actions

1. **human**: commit layer 4, submit the stack, and give layer 3's PR a real title:
   ```
   git add -A app backlog/tasks backlog/docs/stacks decisions
   git commit -m "Carve incident comms out of scribe"
   gh stack submit
   gh pr edit 1580 --title "One service call per status-update handler"
   gh stack view
   ```
2. **human**, as each PR merges (bottom-up, with re-approvals): `gh stack sync`, `gh stack submit`, then `backlog task edit <id> --status Done` (145.2 when #1579 merges, 145.3 and 145.4 after theirs). The task-file edit goes in the next layer's commit, or a small follow-up commit once the stack is merged. Stack J has no further layer to add.
3. **agent** (next session): reconcile merges (`gh pr view 1579 1580 <layer-4 PR> --json state`), fix anything a review asks for on the layer it belongs to (`gh stack checkout <branch>`, then `gh stack rebase`), and print the Done commands for merged layers.
4. **human**: Stack K (TASK-145.5, TASK-145.6) can start from `main` now, in parallel with this stack; approve the TASK-145.6 split first (Open decisions).

## Open decisions

- TASK-145.6 exceeds the size gate as one task: the plan proposes TASK-145.6.1 (IncidentReport, merging the three Google adapters) and TASK-145.6.2 (IncidentConversation, ProductCatalog, reference-taking reader). Approve the split before Stack K.
- TASK-145.7, 145.8 and 145.9 each propose a split in their plans (declare in two halves; status/update versus roles/archive/metadata; the summarize move separated from the timeline rebuild because doc-2 forbids mixing a move with a behaviour change). Approve before Stack L.
- TASK-145.12 needs the spreadsheets capability (TASK-121) for its projection writer, or the legacy writer stays until then: confirm and add the dependency.
- Severity scale decided 2026-10-09: levels 0 to 4, wide because teams use different scales; revisit if the organisation standardises.
- Whether user-facing "retro" labels become "postmortem" with TASK-145.10.

## Planning queue

- Stack K (group B): TASK-145.5 (read path of the record, plan written), TASK-145.6 (plan written with the proposed split). Unblocked since TASK-145.1 merged; can start from `main` in parallel with this stack.
- Stack L (group C): TASK-145.7, 145.8, 145.9 (outline plans with proposed splits). Waits for TASK-36.1 and TASK-36.3 (pinning) and Stack K.
- Stack M (group D): TASK-145.10, 145.11 (outline plans). Waits for TASK-138 (calendar capability), TASK-36.1 and Stack L's TASK-145.9.
- Standalone: TASK-145.12 (cutover; waits for TASK-145.9 and the TASK-121 decision), TASK-145.13 (contract; waits for TASK-145.11, 145.12 and TASK-118).
- Every outline plan (7 to 13) says "re-ground at pickup": the umbrella lives in `features/incident/` since layer 1, the views reach the translator through `core.api` since layer 2, and status updates live in `features/incident/comms/` (plugin `incident.comms`) since layer 4; scribe holds only draft and summarize.
