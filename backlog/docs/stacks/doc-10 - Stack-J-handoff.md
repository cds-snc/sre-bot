---
id: doc-10
title: Stack J handoff
type: guide
created_date: '2026-10-09 18:23'
updated_date: '2026-10-09 19:37'
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
| 2 | TASK-145.2 wording and prompt text out of the views module; translator through core.api | `stack-j/task-145.2-status-update-wording` | #1579 | in review | dd779db, rebased on `main`, PR base `main`, review required. Gates green, all five ACs checked, notes written, task In Progress. After merge: `backlog task edit 145.2 --status Done` (human). |
| 3 | TASK-145.3 one service call per status-update handler | `stack-j/task-145.3-status-update-handlers` | - | ready | Implemented 2026-10-09, gates green, all five ACs checked, notes written, task In Progress. Uncommitted on the layer-3 branch until Next action 1. New `scribe/status_update_form.py`; `approve_and_publish`, `read_published`, `set_published_and_render`; `StatusUpdateFormState`, `PublishedRecord`, `StatusUpdateEdit.blank_fields()`. Deviations from the plan are in the task notes. |
| 4 | TASK-145.4 carve `comms` out of scribe as plugin `incident.comms` | `stack-j/task-145.4-comms-subdomain` | - | plan approved | Re-ground on layer 3 first: the task notes list what layer 3 added (`status_update_form.py` moves too, new test files, stub targets). Mechanical move; ids become `incident.comms.status_update.*`; modals open across the deploy are accepted as broken. The comms views module imports `translate` from `core.api` (no new ignore entry); the scribe test conftests that load the catalogues move with the tests. |

## Position

- Checked out: `stack-j/task-145.3-status-update-handlers` (on dd779db, layer 2). Layer 2 (#1579) is open and in review.
- Uncommitted, all for layer 3: `app/features/incident/scribe/{domain.py,status_update_form.py (new),status_update_approval.py,status_update_history.py,README.md,entrypoints/slack.py,entrypoints/slack_views.py}`; under `app/tests/unit/features/incident/scribe/`, five new test files (`test_incident_scribe_status_update_{form_save,form_fill,form_view,approval_publish,history_render}.py`) and edits to the six `*_entrypoint.py` files, `..._approval.py` and `..._slack.py`; the five `app/tests/integration/features/incident/scribe/*_dispatch.py` (stub targets only); `backlog/tasks/task-145.3*.md` (status, ACs, notes), `backlog/tasks/task-145.4*.md` (re-ground note), the two plan-approval comments, this doc, and `.claude/skills/stacked-pr-session/SKILL.md` (End routine: Done and next-layer commands). The new files are marked intent-to-add in the index (`git add -N`); `git add -A` stages them as usual.
- Never stage: `backlog/docs/doc-6*`, `backlog/docs/doc-8*`, `CDS Incident Management Handbook.md`, `Incident Response Runbook.md` (working files, not kept in the repo).
- Plan approval: TASK-145.2, 145.3 and 145.4 have "Plan approved" comments.
- No background agents.

## Next actions

1. **human**: commit layer 3 and submit the stack:
   ```
   git add -A app backlog/tasks backlog/docs/stacks .claude/skills/stacked-pr-session
   git commit -m "One service call per status-update handler"
   gh stack submit
   gh pr view --web
   ```
2. **human**: create the layer-4 branch on top of layer 3 before the next session:
   ```
   gh stack add stack-j/task-145.4-comms-subdomain
   gh stack view
   ```
3. **agent** (layer 4): re-ground the TASK-145.4 plan on the layer-3 code (task notes), then implement it as a mechanical move (`git mv`); run the gates from `app/` (`uv run ruff check .`, `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run lint-imports`, `uv run pytest tests --ignore=tests/smoke`); check the ACs through the CLI; write the task notes; set the task In Progress; update this doc; hand the human the commit and `gh stack submit` commands. Layer 4 is the top of Stack J, so there is no next layer to add.
4. **human**, as each PR merges (bottom-up, with re-approvals): `gh stack sync`, `gh stack submit`, then `backlog task edit <id> --status Done` (145.2 when #1579 merges, 145.3 and 145.4 after theirs). The task-file edit goes in the next layer's commit, or a small follow-up commit once the stack is merged.
5. **human**: Stack K (TASK-145.5, TASK-145.6) can start from `main` now, in parallel with this stack.

## Open decisions

- TASK-145.6 exceeds the size gate as one task: the plan proposes TASK-145.6.1 (IncidentReport, merging the three Google adapters) and TASK-145.6.2 (IncidentConversation, ProductCatalog, reference-taking reader). Approve the split before Stack K.
- TASK-145.7, 145.8 and 145.9 each propose a split in their plans (declare in two halves; status/update versus roles/archive/metadata; the summarize move separated from the timeline rebuild because doc-2 forbids mixing a move with a behaviour change). Approve before Stack L.
- TASK-145.12 needs the spreadsheets capability (TASK-121) for its projection writer, or the legacy writer stays until then: confirm and add the dependency.
- Severity scale decided 2026-10-09: levels 0 to 4, wide because teams use different scales; revisit if the organisation standardises.
- Whether user-facing "retro" labels become "postmortem" with TASK-145.10.

## Planning queue

- Stack K (group B): TASK-145.5 (read path of the record, plan written), TASK-145.6 (plan written with the proposed split). Unblocked since TASK-145.1 merged; can start from `main` in parallel with layers 3 and 4.
- Stack L (group C): TASK-145.7, 145.8, 145.9 (outline plans with proposed splits). Waits for TASK-36.1 and TASK-36.3 (pinning) and Stack K.
- Stack M (group D): TASK-145.10, 145.11 (outline plans). Waits for TASK-138 (calendar capability), TASK-36.1 and Stack L's TASK-145.9.
- Standalone: TASK-145.12 (cutover; waits for TASK-145.9 and the TASK-121 decision), TASK-145.13 (contract; waits for TASK-145.11, 145.12 and TASK-118).
- Every outline plan (7 to 13) says "re-ground at pickup": the umbrella lives in `features/incident/` since layer 1 and the views reach the translator through `core.api` since layer 2.
