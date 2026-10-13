---
id: doc-10
title: Stack J handoff
type: guide
created_date: '2026-10-09 18:23'
updated_date: '2026-10-09 18:54'
---
# Stack J handoff

## Stack

- Name: Stack J, incident rebuild group A: the umbrella moves to `features/incident/` and the status-update code is cleaned and carved out as `comms`. Trunk: `main` (d3d03d7e, planning PR #1576 merged). gh stack #1578.
- doc-2 line: Wave 5, "Legacy rebuild by surface": Stack J is TASK-145.1 -> TASK-145.2 -> TASK-145.3 -> TASK-145.4. The stack implements group A of coordinator TASK-145; backlog doc-9 holds the whole chain.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase. Layer 4 is the last layer of this stack; groups B to E are later stacks (Planning queue).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | TASK-145 plans (docs only) | `stack-j/plan` | #1576 | merged | Plans for TASK-145.1 to 145.13 (1-6 grounded in code; 7-13 outlines to re-ground at pickup). |
| 1 | TASK-145.1 move packages/incident to features/incident with the first-mover wiring | `stack-j/task-145.1-move-incident-to-features` | #1577 | in review | df0e953. Task set Done by the human (uncommitted task-file edit, see Position). Branch is behind `main` by the squash of #1576; `gh stack submit` after layer 2 is committed handles the bases. |
| 2 | TASK-145.2 wording and prompt text out of the views module; translator through core.api | `stack-j/task-145.2-status-update-wording` (not created yet) | - | in progress | Implemented 2026-10-09, all gates green, all five ACs checked, notes written, task In Progress. Uncommitted in the working tree on the layer-1 branch until Next action 1. 14 modified, 4 new files. |
| 3 | TASK-145.3 one service call per status-update handler | `stack-j/task-145.3-status-update-handlers` | - | planned | Service results carry the form to render; `approve_and_publish`, `read_published`, `set_published_and_render` become service functions; handlers shrink to parse, call, render. Behaviour-preserving. Re-ground on layer 2: `status_t` now takes `**variables`, `origin_line` passes author and time to the translator, views reach the translator through `core.api.translate`. |
| 4 | TASK-145.4 carve `comms` out of scribe as plugin `incident.comms` | `stack-j/task-145.4-comms-subdomain` | - | planned | Mechanical move; ids become `incident.comms.status_update.*`; modals open across the deploy are accepted as broken. The comms views module imports `translate` from `core.api` (no new ignore entry); the scribe test conftests that load the catalogues move with the tests. |

## Position

- Checked out: `stack-j/task-145.1-move-incident-to-features` (df0e953, PR #1577). The layer-2 branch does not exist yet: the human runs `gh stack add` first (Next action 1) and the uncommitted work carries onto it.
- Uncommitted, all for layer 2 except the two task-file edits the human made: `app/features/incident/core/adapters/i18n.py` (new), `app/features/incident/core/api.py`, `app/features/incident/scribe/{service.py,README.md,entrypoints/slack.py,entrypoints/slack_views.py}`, `app/pyproject.toml`, `app/tests/factories/i18n.py`, new conftests under `app/tests/unit/features/incident/scribe/` and `app/tests/integration/features/incident/scribe/`, `app/tests/unit/features/incident/core/test_incident_core_translate.py` (new), six edited test files under `app/tests/unit/features/incident/`, `backlog/tasks/task-145.2*.md` (approval comment, status, ACs, notes), `backlog/tasks/task-145.1*.md` (status Done, set by the human), this doc. Committing the TASK-145.1 Done edit with layer 2 is fine; move it to layer 1 only if the human prefers.
- Never stage: `backlog/docs/doc-6*`, `backlog/docs/doc-8*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md` (working files, not kept in the repo).
- Plan approval: TASK-145.2 has a "Plan approved" task comment (2026-10-09 18:42). TASK-145.1 was approved in a resume prompt (no comment). TASK-145.3 and TASK-145.4 have no recorded approval yet.
- No background agents.

## Next actions

1. **human**: create the layer-2 branch on top of layer 1, commit the layer and submit the stack:
   ```
   gh stack add stack-j/task-145.2-status-update-wording
   git add -A app backlog/tasks backlog/docs/stacks
   git commit -m "Move status-update wording out of the views module"
   gh stack submit
   gh pr view --web
   ```
2. **human**: review the plans of TASK-145.3 and TASK-145.4 and record the approval on each (`backlog task edit 145.3 --comment "Plan approved"`), or ask for changes in the next session. Decide the open decisions below that touch layers 3 and 4 (none block layer 3).
3. **human**: create the layer-3 branch on top of layer 2:
   ```
   gh stack add stack-j/task-145.3-status-update-handlers
   ```
4. **agent** (layer 3, after approval): re-ground the TASK-145.3 plan on the layer-2 code (see the layer table), then implement it; run the gates from `app/` (`uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run lint-imports`, `uv run pytest tests --ignore=tests/smoke`); check the ACs through the CLI; write the task notes; set the task In Progress; update this doc; hand the human the commit and `gh stack submit` commands.
5. **agent**: repeat for layer 4 on `gh stack add stack-j/task-145.4-comms-subdomain` run by the human, one layer per PR.
6. **human**: merge bottom-up with re-approvals (`gh stack rebase` after each merge); after layer 1 merges, Stack K (TASK-145.5, TASK-145.6) can start from `main` in parallel with layers 2 to 4.

## Open decisions

- TASK-145.6 exceeds the size gate as one task: the plan proposes TASK-145.6.1 (IncidentReport, merging the three Google adapters) and TASK-145.6.2 (IncidentConversation, ProductCatalog, reference-taking reader). Approve the split before Stack K.
- TASK-145.7, 145.8 and 145.9 each propose a split in their plans (declare in two halves; status/update versus roles/archive/metadata; the summarize move separated from the timeline rebuild because doc-2 forbids mixing a move with a behaviour change). Approve before Stack L.
- TASK-145.12 needs the spreadsheets capability (TASK-121) for its projection writer, or the legacy writer stays until then: confirm and add the dependency.
- Severity scale (levels 0 to 3 recorded) to confirm with the incident process owners before TASK-145.5 merges.
- Whether user-facing "retro" labels become "postmortem" with TASK-145.10.
- Resolved in layer 2: the notices and origin line use the catalogue key as the neutral fallback (a missing key renders as the key, guarded by the parity and catalogue tests).

## Planning queue

- Layers 3 and 4: plans written, awaiting recorded approval (Next action 2).
- Stack K (group B): TASK-145.5 (read path of the record, plan written), TASK-145.6 (plan written with the proposed split). Waits for TASK-145.1 to merge.
- Stack L (group C): TASK-145.7, 145.8, 145.9 (outline plans with proposed splits). Waits for TASK-36.1 and TASK-36.3 (pinning) and Stack K.
- Stack M (group D): TASK-145.10, 145.11 (outline plans). Waits for TASK-138 (calendar capability), TASK-36.1 and Stack L's TASK-145.9.
- Standalone: TASK-145.12 (cutover; waits for TASK-145.9 and the TASK-121 decision), TASK-145.13 (contract; waits for TASK-145.11, 145.12 and TASK-118).
- Every outline plan (7 to 13) says "re-ground at pickup": the umbrella lives in `features/incident/` since layer 1 and the views reach the translator through `core.api` since layer 2.
