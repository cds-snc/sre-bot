---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-08 00:51'
---
# Stack H handoff

## Stack

- Name: Stack H, incident status updates. Trunk: `main`. gh stack #1546.
- doc-2 line: Wave 5, "Incident status updates (prioritised 2026-10-06)". The human chose a stack on 2026-10-07 and approved every split below at the size gate.
- Scope (human, 2026-10-07, in `decisions/incident-management.md`): nothing is pushed to an external platform and nothing about status updates is posted in the incident channel. Draft, review (edit or redraft with instructions), approve, then copy the EN and FR text by hand; approved updates stay browsable. All of it lives in modals opened by `/sre incident status-update`.
- Each layer is reviewed, merged and deployed on its own, bottom-up (squash merges; the stack is rebased after each).

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | TASK-140.4 status-update records and table | `task-140.4-status-update-records` | [#1544](https://github.com/cds-snc/sre-bot/pull/1544) | merged | f3525fd8. Terraform table `sre_bot_incident_status_updates` + IAM applied. |
| 2 | TASK-140.5.1 draft service | `stack-h/task-140.5-status-update-draft` | [#1545](https://github.com/cds-snc/sre-bot/pull/1545) | merged | 6c3c57a0. |
| 3 | TASK-140.5.2 command opens the status-updates modal | `stack-h/task-140.5.2-status-updates-modal` | [#1547](https://github.com/cds-snc/sre-bot/pull/1547) | merged | 1ca8065c. |
| 4 | TASK-140.5.3 Draft button | `stack-h/task-140.5.3-status-update-draft-button` | [#1548](https://github.com/cds-snc/sre-bot/pull/1548) | merged | aca15521. |
| 5 | TASK-140.10.1 security flag | `stack-h/task-140.6-status-update-approve` | [#1549](https://github.com/cds-snc/sre-bot/pull/1549) | merged | 2ae430d1. Never revert the `Incident` field. |
| 6 | TASK-140.10.2 confirm before drafting | `stack-h/task-140.10.2-security-draft-confirm` | [#1550](https://github.com/cds-snc/sre-bot/pull/1550) | merged | 162f6fa9. |
| 7 | TASK-140.6.1 approval service + copy-ready publisher | `stack-h/task-140.6.1-status-update-approve` | [#1555](https://github.com/cds-snc/sre-bot/pull/1555) | merged | 5a23e162. |
| 8 | TASK-140.6.2 review modal + copy-ready view | `stack-h/task-140.6.2-status-update-review` | [#1556](https://github.com/cds-snc/sre-bot/pull/1556) | merged | Squash-merged 2026-10-08 as e820711e. 449c3588, base main 5a23e162. ACs 1-6 checked. Deviation: `build_review_error_view`. Bolt harness in `tests/factories/slack_bolt.py`. Manual workspace checks pending: `rich_text_preformatted` copy fidelity, `views.update` after an update ack. |
| 9 | TASK-140.8.1 approved-updates list + reopen | `stack-h/task-140.8-status-update-history` (pre-split name) | [#1557](https://github.com/cds-snc/sre-bot/pull/1557) | merged | Squash-merged 2026-10-08 as fc310275. 3627148c. ACs 1-6 checked. Manual checks: Open/Back in place, ET/HE row times. |
| 10 | TASK-140.8.2 published / not published toggle | `stack-h/task-140.8.2-status-update-published` | [#1558](https://github.com/cds-snc/sre-bot/pull/1558) | in review | Rebased onto main 2026-10-08 (4b2a518c + gate-record commit 7b6a6e92); PR retitled via REST. 9c1227e2. ACs 1-5 checked. Core `published_by` + PUBLISHED -> APPROVED. Never revert the core field once data exists. Manual checks: toggle in place in a real modal, ET/HE published line. |
| 11 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | [#1561](https://github.com/cds-snc/sre-bot/pull/1561) | in review | Rebased onto layer 10 2026-10-08 (562e3cdc), re-verified, gates in the task notes.  ACs 1-5 checked, notes with gate evidence. +430/-26 Python lines (net ~404, mostly docstrings) + 22 locale lines, 8 files: a little over the planned ~300. Manual checks: view.state in block_actions, views.update with the action hash, checkbox in the form, real model follows the guidance suffix. Last layer of the stack. |

Coordinators with no branch: TASK-140.5 (140.5.1-3), TASK-140.6 (140.6.1-2), TASK-140.8 (140.8.1-2), TASK-140.10 (140.10.1-2); AC mappings in their notes. After the stack: TASK-140.7 (legacy cutover, standalone PR, depends on 140.6 and 140.8.1).

## Position

- Checked out: `stack-h/task-140.9-status-update-redraft` (layer 11, PR #1561), stacked on layer 10 (`stack-h/task-140.8.2-status-update-published`, PR #1558, base `main`). Layers 1-9 merged (last: #1557 as fc310275; trunk tip df070fc8).
- 2026-10-08: `gh stack rebase` dropped the merged layers; layers 10 and 11 re-verified on the rebased branches, gates appended to the TASK-140.8.2 and TASK-140.9 notes (layer 10: 4328 passed; layer 11: 4437 passed; single-process, 0 failed now that TASK-90 #1560 is merged; mypy 57 repo-wide, 0 in each layer's touched files).
- PR #1558 was titled "Update Stack H handoff"; retitled to "Mark a status update published or not" with `gh api -X PATCH repos/cds-snc/sre-bot/pulls/1558 -f title=...` because `gh pr edit` fails on the `reviewRequests` GraphQL lookup ("Resource not accessible by integration"). Use the REST call for PR edits.
- TASK-140.7 (legacy cutover) is open as standalone PR #1564 off `main` (branch `task-140.7-retire-legacy-incident-updates`; ACs 1-3 checked, In Progress; also fixes the 9 mypy errors in `modules/incident/core.py` and an unset security-group crash at declare). It shares only this doc with layers 10-11, so the doc conflicts for whichever merges second: keep this version and fold in 140.7's state.
- No background agents.

## Next actions

1. **human**: commit the layer 11 gate record and this doc, push the stack (commands in the session hand-off).
2. **human**: run the manual workspace checks listed in the Layers notes for layers 10-11.
3. **human**: merge bottom-up with re-approval after each rebase: #1558, then `gh stack rebase` + `gh stack push`, then #1561. Then #1564 (TASK-140.7), resolving the doc-5 conflict in favour of this version. #1564 can also go first; its code does not overlap the stack.
4. **human**: set Done (agents never set Done) for the merged layers 140.4, 140.5.1, 140.5.2, 140.5.3, 140.10.1, 140.10.2, 140.6.1, 140.6.2, 140.8.1, then 140.8.2, 140.9 and 140.7 after their merges, and the coordinators 140.5, 140.10, 140.6 and 140.8 once their ACs are checked.
5. Then Stack H is closed. Follow-ups outside the stack: TASK-140.11 (timer pre-generated drafts, low), TASK-140.12 (un-approve or correct, low).

## Open decisions

- None pending.
- Settled 2026-10-07/08 (details in each task's plan and notes): modal-only flow, `views.update` in place everywhere; async scribe services calling the sync store inline, one `asyncio.run` per Slack listener; approval stops at APPROVED; forward-only stage floor; copy-ready text as a preformatted block per language; security confirmation at drafting and redrafting; 140.8 split into 140.8.1/140.8.2; FR toggle strings feminine ("publiée"); 140.9 redraft from the reviewer's form values, conflict shows "changed elsewhere", instructions not stored; TASK-90 fixed later outside the stack.

## Planning queue

- Empty for Stack H; every layer is implemented.
- Follow-ups outside the stack: TASK-140.7 (legacy cutover, next), TASK-90 (test-order leaks), TASK-140.11 (timer drafts, low), TASK-140.12 (un-approve or correct, low).
