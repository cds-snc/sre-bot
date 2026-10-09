---
id: doc-7
title: Stack I handoff
type: guide
created_date: '2026-10-09 13:34'
updated_date: '2026-10-09 15:35'
---
# Stack I handoff

## Stack

- Name: Stack I, human-first incident status updates. Trunk: `main`. gh stack #1570, layer 1 at the bottom.
- doc-2 line: none yet. The stack implements coordinator TASK-144, planned in backlog doc-6. doc-6 is the uncommitted planning record and is never staged with a layer.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase.
- Layer 5 is the last layer: TASK-144 has no further subtasks.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-144.1 merge scribe platforms/ into entrypoints/ | `fix/incident_scribe_shape` | [#1568](https://github.com/cds-snc/sre-bot/pull/1568) | in review | Approved. c2f1106f on top of 6f89a897 (TASK-144 planning); a squash merge folds both. PR title is still the branch name (the human chose to leave it). |
| 2 | TASK-144.2 human-first records and README | `stack-i/task-144.2-human-first-records` | [#1569](https://github.com/cds-snc/sre-bot/pull/1569) | in review | db5efe18. Docs only. The feature-packages.md edit depends on layer 1 merging first. |
| 3 | TASK-144.3 service and store: origin, save, AI fill, availability | `stack-i/task-144.3-status-update-service` | [#1571](https://github.com/cds-snc/sre-bot/pull/1571) | in review | 62b2e0d7. Review points in the TASK-144.3 notes. |
| 4 | TASK-144.4 modal: New update, origin line, Save draft | `stack-i/task-144.4-start-by-hand-and-save` | [#1572](https://github.com/cds-snc/sre-bot/pull/1572) | in review | 17a4fd28. Review points in the TASK-144.4 notes. |
| 5 | TASK-144.5 modal: AI inside the form | `stack-i/task-144.5-ai-inside-the-form` | - | ready | Gates green (4535 passed), ACs 1-5 checked, notes written. Title, description and AC #4 no longer mention Write it myself. Uncommitted until the human runs Next action 1. |

## Position

- Checked out: `stack-i/task-144.5-ai-inside-the-form` (layer 5). Uncommitted, all for layer 5: `app/packages/incident/scribe/{README.md,status_update.py,status_update_approval.py,entrypoints/slack.py,entrypoints/slack_views.py,locales/incident_status_update.{en-US,fr-FR}.yml}`; scribe unit tests (new: `test_incident_scribe_status_update_generate_{entrypoint,view,instructions}.py`; deleted: `..._entrypoint.py`, `..._confirmation.py`, `..._redraft.py`, `..._redraft_entrypoint.py`, `..._redraft_view.py`; 18 edited); integration tests (new `..._generate_dispatch.py`, deleted `..._redraft_dispatch.py`, 2 edited); the TASK-144.5 and TASK-140.11 task files (140.11 got a note on the new service entry points); this handoff doc.
- Never stage `backlog/docs/doc-6*`.
- No background agents.

## Next actions

1. **human**: commit and submit layer 5:
   ```
   git add app/ backlog/tasks/ backlog/docs/stacks/
   git commit -m "Move AI drafting into the status update form"
   gh stack submit
   gh pr view --web
   ```
2. **human**: review #1569, #1571, #1572 and the layer 5 PR (#1568 approved); merge bottom-up with re-approvals.
3. **agent** (after the last merge): reconcile TASK-144's coordinator AC and doc-6 with what shipped; leave every task at In Progress for the human to close.

## Open decisions

- Layer 3 review points (TASK-144.3 notes): a save replay is detected before the stale-sequence check, so a double submit returns the stored draft; with blank instructions, generate uses the base prompt over the typed fields; the redraft-specific log event names became generic.
- Layer 4 review points (TASK-144.4 notes): the origin line names a person only for hand-written and pre-origin records; a form with no readable stage is not saved and re-renders the stored draft with the failure notice.
- Layer 5 review points (TASK-144.5 notes): New update with nothing new stores a HAND copy of the approved update (no carry forward); a first update with no person's message is still refused with EMPTY_HISTORY; after TEXT_GENERATION_UNAVAILABLE the form drops its AI section; Review is primary when a draft is pending; `ErrorCode.STATUS_UPDATE_INSTRUCTIONS_INVALID` in contracts has no user left; modals opened before deploy carry the old draft, draft_confirmed and redraft ids, which now hit unregistered actions.

## Planning queue

- Empty: every layer has an approved plan, and layer 5 is the last.
