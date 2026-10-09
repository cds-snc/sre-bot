---
id: doc-10
title: Stack J handoff
type: guide
created_date: '2026-10-09 18:23'
updated_date: '2026-10-09 18:34'
---
# Stack J handoff

## Stack

- Name: Stack J, incident rebuild group A: the umbrella moves to `features/incident/` and the status-update code is cleaned and carved out as `comms`. Trunk: `main` (d2d973ae, TASK-144 fully merged). gh stack: created; bottom branch `stack-j/plan` is PR #1576.
- doc-2 line: Wave 5, "Legacy rebuild by surface": Stack J is TASK-145.1 -> TASK-145.2 -> TASK-145.3 -> TASK-145.4. The stack implements group A of coordinator TASK-145; backlog doc-9 holds the whole chain.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase. Layer 4 is the last layer of this stack; groups B to E are later stacks (Planning queue).
- Planning layer: `stack-j/plan` carries the thirteen task plans, this doc and the doc-2 line. It is the bottom PR of the stack, or folded into layer 1 by a squash merge if the human prefers (as Stack I did).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | TASK-145 plans (docs only) | `stack-j/plan` | #1576 | in review | Plans for TASK-145.1 to 145.13 (1-6 grounded in code; 7-13 outlines to re-ground at pickup). |
| 1 | TASK-145.1 move packages/incident to features/incident with the first-mover wiring | `stack-j/task-145.1-move-incident-to-features` (not created yet) | - | in progress | Implemented 2026-10-09, all gates green, all five ACs checked, notes written, task In Progress. Uncommitted in the working tree on `stack-j/plan` until Next action 1. 130 renames, 18 modified, 3 added; ignore list 70 entries before and after. |
| 2 | TASK-145.2 wording and prompt text out of the views module; translator through core.api | `stack-j/task-145.2-status-update-wording` | - | planned | Deletes the six EN/FR fallback tables; moves `SLACK_FORMAT_INSTRUCTIONS` to the summary service; adds `core/adapters/i18n.py` so the umbrella keeps one `infrastructure.i18n` import (ignore entry renamed, not added). Re-ground paths on `features.incident` at pickup. |
| 3 | TASK-145.3 one service call per status-update handler | `stack-j/task-145.3-status-update-handlers` | - | planned | Service results carry the form to render; `approve_and_publish`, `read_published`, `set_published_and_render` become service functions; handlers shrink to parse, call, render. Behaviour-preserving. |
| 4 | TASK-145.4 carve `comms` out of scribe as plugin `incident.comms` | `stack-j/task-145.4-comms-subdomain` | - | planned | Mechanical move; ids become `incident.comms.status_update.*`; modals open across the deploy are accepted as broken. |

## Position

- Checked out: `stack-j/plan` (364f0322, PR #1576). The layer-1 branch does not exist yet: the human runs `gh stack add` first (Next action 1) and the uncommitted work carries onto it.
- Uncommitted, all for layer 1: staged renames `app/packages/incident/` -> `app/features/incident/` and the two test trees; worktree edits in `app/` (pyproject, jobs, modules/incident, legacy_surface tests, the four path-based tests, the scribe plugin registration test), `decisions/incident-management.md`, `decisions/feature-packages.md`, `backlog/tasks/task-145.1*.md` (status, ACs, notes) and this doc.
- Never stage: `backlog/docs/doc-6*`, `backlog/docs/doc-8*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md` (working files, not kept in the repo).
- Plan approval for layer 1 was given in the resume prompt of the 2026-10-09 session; no task comment records it. Layers 2 to 4 have no recorded approval yet.
- No background agents.

## Next actions

1. **human**: create the layer-1 branch on top of the stack, commit the layer and submit it:
   ```
   gh stack add stack-j/task-145.1-move-incident-to-features
   git add -A app decisions backlog/tasks backlog/docs/stacks
   git commit -m "Move packages/incident to features/incident"
   gh stack submit
   gh pr view --web
   ```
   Then `cd app && uv sync` in any other checkout, because the entry-point target changed.
2. **human**: record the approval of the TASK-145.1 plan on the task (`backlog task edit 145.1 --comment "Plan approved"`), review the plans of TASK-145.2 to TASK-145.4 and record their approval, or ask for changes in the next session. Decide the open decisions below that touch layers 2 to 4 (none block layer 2).
3. **human**: create the layer-2 branch on top of layer 1:
   ```
   gh stack add stack-j/task-145.2-status-update-wording
   ```
4. **agent** (layer 2, after approval): re-ground the TASK-145.2 plan on `features.incident` paths, then implement it; run the gates from `app/` (`uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run lint-imports`, `uv run pytest tests --ignore=tests/smoke`); check the ACs through the CLI; write the task notes; set the task In Progress; update this doc; hand the human the commit and `gh stack submit` commands.
5. **agent**: repeat for layers 3 and 4, each on `gh stack add <branch>` run by the human, one layer per PR; a session may carry several layers.
6. **human**: merge bottom-up with re-approvals; after layer 1 merges, Stack K (TASK-145.5, TASK-145.6) can start from `main` in parallel with layers 2 to 4.

## Open decisions

- TASK-145.6 exceeds the size gate as one task: the plan proposes TASK-145.6.1 (IncidentReport, merging the three Google adapters) and TASK-145.6.2 (IncidentConversation, ProductCatalog, reference-taking reader). Approve the split before Stack K.
- TASK-145.7, 145.8 and 145.9 each propose a split in their plans (declare in two halves; status/update versus roles/archive/metadata; the summarize move separated from the timeline rebuild because doc-2 forbids mixing a move with a behaviour change). Approve before Stack L.
- TASK-145.12 needs the spreadsheets capability (TASK-121) for its projection writer, or the legacy writer stays until then: confirm and add the dependency.
- Severity scale (levels 0 to 3 recorded) to confirm with the incident process owners before TASK-145.5 merges.
- Key-as-fallback (TASK-145.2) versus empty-string fallback for the notices: either satisfies the AC; the plan picks the key.
- Whether user-facing "retro" labels become "postmortem" with TASK-145.10.

## Planning queue

- Layers 2 to 4: plans written, awaiting recorded approval (Next action 2).
- Stack K (group B): TASK-145.5 (read path of the record, plan written), TASK-145.6 (plan written with the proposed split). Waits for TASK-145.1 to merge.
- Stack L (group C): TASK-145.7, 145.8, 145.9 (outline plans with proposed splits). Waits for TASK-36.1 and TASK-36.3 (pinning) and Stack K.
- Stack M (group D): TASK-145.10, 145.11 (outline plans). Waits for TASK-138 (calendar capability), TASK-36.1 and Stack L's TASK-145.9.
- Standalone: TASK-145.12 (cutover; waits for TASK-145.9 and the TASK-121 decision), TASK-145.13 (contract; waits for TASK-145.11, 145.12 and TASK-118).
- Every outline plan (7 to 13) says "re-ground at pickup": the legacy module and the umbrella have moved to `features/incident/` with layer 1.
