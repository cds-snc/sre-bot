---
id: doc-7
title: Stack I handoff
type: guide
created_date: '2026-10-09 13:34'
updated_date: '2026-10-09 15:14'
---
# Stack I handoff

## Stack

- Name: Stack I, human-first incident status updates. Trunk: `main`. gh stack #1570, layer 1 at the bottom.
- doc-2 line: none yet. The stack implements coordinator TASK-144, planned in backlog doc-6. doc-6 is the uncommitted planning record and is never staged with a layer.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each). Merges are manual and bottom-up, with a re-approval for each layer after its rebase.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-144.1 merge scribe platforms/ into entrypoints/ | `fix/incident_scribe_shape` | [#1568](https://github.com/cds-snc/sre-bot/pull/1568) | in review | c2f1106f on top of 6f89a897 (TASK-144 planning); a squash merge folds both. PR title is still the branch name (the human chose to leave it). |
| 2 | TASK-144.2 human-first records and README | `stack-i/task-144.2-human-first-records` | [#1569](https://github.com/cds-snc/sre-bot/pull/1569) | in review | db5efe18. Docs only. The feature-packages.md edit depends on layer 1 merging first. |
| 3 | TASK-144.3 service and store: origin, save, AI fill, availability | `stack-i/task-144.3-status-update-service` | [#1571](https://github.com/cds-snc/sre-bot/pull/1571) | in review | 62b2e0d7. Review points in the TASK-144.3 notes. |
| 4 | TASK-144.4 modal: New update, origin line, Save draft | `stack-i/task-144.4-start-by-hand-and-save` | - | ready | Gates green (4572 passed), ACs 1-5 checked, notes written. Uncommitted until the human runs Next action 1. |
| 5 | TASK-144.5 modal: AI inside the form | `stack-i/task-144.5-ai-inside-the-form` (proposed) | - | planned | Plan written; no approval comment. Deletes the `redraft_status_update` wrapper. Its description and title still list Write it myself / `handle_write_action` as things to delete; layer 4 already removed them (fix on the layer 5 branch, see Next actions). |

## Position

- Checked out: `stack-i/task-144.4-start-by-hand-and-save` (layer 4). Uncommitted, all for layer 4: `app/packages/incident/scribe/{README.md,entrypoints/slack.py,entrypoints/slack_views.py,locales/incident_status_update.{en-US,fr-FR}.yml}`; scribe unit tests (4 new: `test_incident_scribe_status_update_{new_entrypoint,origin_line_view,save_entrypoint,save_view}.py`; `..._manual_entrypoint.py` deleted, replaced by `..._new_entrypoint.py`; 10 edited); one new integration test `tests/integration/packages/incident/scribe/test_incident_scribe_status_update_save_dispatch.py`; the TASK-144.4 task file; this handoff doc.
- Never stage `backlog/docs/doc-6*`.
- No background agents.

## Next actions

1. **human**: commit and submit layer 4:
   ```
   git add app/ backlog/tasks/ backlog/docs/stacks/
   git commit -m "Start status updates by hand and save drafts"
   gh stack submit
   gh pr view --web
   ```
2. **human**: review and approve the TASK-144.5 plan (`backlog task edit TASK-144.5 --comment "Plan approved (human, <date>)"`), or tell the agent it is approved.
3. **human**: `gh stack add stack-i/task-144.5-ai-inside-the-form`
4. **agent**: on the layer 5 branch, first drop the stale Write it myself / `handle_write_action` mentions from the TASK-144.5 title, description and AC #4 via the CLI (layer 4 removed them); then execute TASK-144.5 from its plan (TDD: failing tests first), ending with the commit/submit block for layer 5.
5. **human**: review #1568, #1569, #1571 and the layer 4 PR; merge bottom-up with re-approvals.

## Open decisions

- Plan approval for TASK-144.5 (plan written, no approval comment).
- Layer 3 review points (TASK-144.3 notes): a save replay is detected before the stale-sequence check, so a double submit returns the stored draft; with blank instructions, generate uses the base prompt over the typed fields; the redraft-specific log event names became generic.
- Layer 4 review points (TASK-144.4 notes): with no pending draft, New update is primary and Draft loses its primary style; the origin line names a person only for hand-written and pre-origin records; a form with no readable stage is not saved and re-renders the stored draft with the failure notice; modals opened before deploy still show Write it myself, which now hits an unregistered action id.

## Planning queue

- Empty: TASK-144.5 has a plan and waits only on approval (Open decisions).
