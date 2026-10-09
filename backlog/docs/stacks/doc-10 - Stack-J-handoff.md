---
id: doc-10
title: Stack J handoff
type: guide
created_date: '2026-10-09 18:23'
updated_date: '2026-10-09 18:24'
---
# Stack J handoff

## Stack

- Name: Stack J, incident rebuild group A: the umbrella moves to `features/incident/` and the status-update code is cleaned and carved out as `comms`. Trunk: `main` (d2d973ae, TASK-144 fully merged). gh stack: not created yet.
- doc-2 line: Wave 5, "Legacy rebuild by surface": Stack J is TASK-145.1 -> TASK-145.2 -> TASK-145.3 -> TASK-145.4. The stack implements group A of coordinator TASK-145; backlog doc-9 holds the whole chain.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase. Layer 4 is the last layer of this stack; groups B to E are later stacks (Planning queue).
- Planning layer: `stack-j/plan` carries the thirteen task plans, this doc and the doc-2 line, so the plans can be reviewed and approved before any code. It is the bottom PR of the stack, or folded into layer 1 by a squash merge if the human prefers (as Stack I did).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | TASK-145 plans (docs only) | `stack-j/plan` | - | ready | Plans written for TASK-145.1 to 145.13 (1-6 grounded in code; 7-13 outlines to re-ground at pickup). Uncommitted until Next action 1. |
| 1 | TASK-145.1 move packages/incident to features/incident with the first-mover wiring | `stack-j/task-145.1-move-incident-to-features` | - | planned | Pure move: `git mv`, sed over `packages.incident`, hatch/import-linter/pyproject contracts gain `features`, tests move under `tests/*/features/incident/`. About 130 files, nearly all renames. |
| 2 | TASK-145.2 wording and prompt text out of the views module; translator through core.api | `stack-j/task-145.2-status-update-wording` | - | planned | Deletes the six EN/FR fallback tables; moves `SLACK_FORMAT_INSTRUCTIONS` to the summary service (it is the summarize command's mrkdwn instruction); adds `core/adapters/i18n.py` so the umbrella keeps one `infrastructure.i18n` import (ignore entry renamed, not added). |
| 3 | TASK-145.3 one service call per status-update handler | `stack-j/task-145.3-status-update-handlers` | - | planned | Service results carry the form to render (`StatusUpdateFormState`, `PublishedRecord`); `approve_and_publish`, `read_published`, `set_published_and_render` become service functions; handlers shrink to parse, call, render. Behaviour-preserving, pinned by the existing entrypoint and dispatch tests. |
| 4 | TASK-145.4 carve `comms` out of scribe as plugin `incident.comms` | `stack-j/task-145.4-comms-subdomain` | - | planned | Mechanical move; ids become `incident.comms.status_update.*`; modals open across the deploy are accepted as broken. |

## Position

- Checked out: `main`. Uncommitted, all for layer 0: `backlog/tasks/task-145*.md` (plans on 145.1 to 145.13; corrected descriptions and ACs on 145.2, 145.4, 145.5), `backlog/docs/stacks/doc-10 - Stack-J-handoff.md` (this doc), `backlog/docs/doc-2 - Delivery-Sequence-and-Stacked-Pull-Requests.md` (the Stack J line).
- Never stage: `backlog/docs/doc-6*`, `backlog/docs/doc-8*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md` (working files, not kept in the repo).
- No background agents.

## Next actions

1. **human**: commit the planning layer and start the stack:
   ```
   git checkout -b stack-j/plan
   git add backlog/tasks/ backlog/docs/stacks/ "backlog/docs/doc-2 - Delivery-Sequence-and-Stacked-Pull-Requests.md"
   git commit -m "Plan Stack J: incident rebuild layers 1 to 4"
   gh stack init
   gh stack submit
   gh pr view --web
   ```
2. **human**: review the plans of TASK-145.1 to TASK-145.4 and record the approval on each task (a task comment or note), or ask for changes in the next session. Decide the open decisions below that touch layers 1 to 4 (none block layer 1).
3. **human**: create the layer-1 branch on top of the stack:
   ```
   gh stack add stack-j/task-145.1-move-incident-to-features
   ```
4. **agent** (layer 1, after approval): implement TASK-145.1 per its plan; run the gates from `app/` (`uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run lint-imports`, `uv run pytest tests --ignore=tests/smoke`, `uv build`); check the ACs through the CLI; write the task notes; set the task In Progress; update this doc; hand the human the commit and `gh stack submit` commands.
5. **agent**: repeat for layers 2, 3, 4, each on `gh stack add <branch>` run by the human, one layer per PR; a session may carry several layers.
6. **human**: merge bottom-up with re-approvals; after layer 1 merges, Stack K (TASK-145.5, TASK-145.6) can start from `main` in parallel with layers 2 to 4.

## Open decisions

- TASK-145.6 exceeds the size gate as one task: the plan proposes TASK-145.6.1 (IncidentReport, merging the three Google adapters) and TASK-145.6.2 (IncidentConversation, ProductCatalog, reference-taking reader). Approve the split before Stack K.
- TASK-145.7, 145.8 and 145.9 each propose a split in their plans (declare in two halves; status/update versus roles/archive/metadata; the summarize move separated from the timeline rebuild because doc-2 forbids mixing a move with a behaviour change). Approve before Stack L.
- TASK-145.12 needs the spreadsheets capability (TASK-121) for its projection writer, or the legacy writer stays until then: confirm and add the dependency.
- Severity scale (levels 0 to 3 recorded) to confirm with the incident process owners before TASK-145.5 merges.
- Key-as-fallback (TASK-145.2) versus empty-string fallback for the notices: either satisfies the AC; the plan picks the key.
- Whether user-facing "retro" labels become "postmortem" with TASK-145.10.

## Planning queue

- Layers 1 to 4: plans written, awaiting approval (Next action 2).
- Stack K (group B): TASK-145.5 (read path of the record, plan written), TASK-145.6 (plan written with the proposed split). Waits for TASK-145.1 to merge.
- Stack L (group C): TASK-145.7, 145.8, 145.9 (outline plans with proposed splits). Waits for TASK-36.1 and TASK-36.3 (pinning) and Stack K.
- Stack M (group D): TASK-145.10, 145.11 (outline plans). Waits for TASK-138 (calendar capability), TASK-36.1 and Stack L's TASK-145.9.
- Standalone: TASK-145.12 (cutover; waits for TASK-145.9 and the TASK-121 decision), TASK-145.13 (contract; waits for TASK-145.11, 145.12 and TASK-118).
- Every outline plan (7 to 13) says "re-ground at pickup": the legacy module and the umbrella will have moved by then.
