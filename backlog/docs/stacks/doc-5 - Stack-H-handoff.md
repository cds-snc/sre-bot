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
| 8 | TASK-140.6.2 review modal + copy-ready view | `stack-h/task-140.6.2-status-update-review` | [#1556](https://github.com/cds-snc/sre-bot/pull/1556) | in review | 449c3588, base main 5a23e162. ACs 1-6 checked. Deviation: `build_review_error_view`. Bolt harness in `tests/factories/slack_bolt.py`. Manual workspace checks pending: `rich_text_preformatted` copy fidelity, `views.update` after an update ack. |
| 9 | TASK-140.8.1 approved-updates list + reopen | `stack-h/task-140.8-status-update-history` (pre-split name) | [#1557](https://github.com/cds-snc/sre-bot/pull/1557) | in review | 3627148c. ACs 1-6 checked. Manual checks: Open/Back in place, ET/HE row times. |
| 10 | TASK-140.8.2 published / not published toggle | `stack-h/task-140.8.2-status-update-published` | [#1558](https://github.com/cds-snc/sre-bot/pull/1558) | in review | 9c1227e2. ACs 1-5 checked. Core `published_by` + PUBLISHED -> APPROVED. Never revert the core field once data exists. Manual checks: toggle in place in a real modal, ET/HE published line. |
| 11 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - (created at submit) | ready (uncommitted) | ACs 1-5 checked, notes with gate evidence. +430/-26 Python lines (net ~404, mostly docstrings) + 22 locale lines, 8 files: a little over the planned ~300. Manual checks: view.state in block_actions, views.update with the action hash, checkbox in the form, real model follows the guidance suffix. Last layer of the stack. |

Coordinators with no branch: TASK-140.5 (140.5.1-3), TASK-140.6 (140.6.1-2), TASK-140.8 (140.8.1-2), TASK-140.10 (140.10.1-2); AC mappings in their notes. After the stack: TASK-140.7 (legacy cutover, standalone PR, depends on 140.6 and 140.8.1).

## Position

- Checked out: `stack-h/task-140.9-status-update-redraft` (layer 11), branch tip 9c1227e2 (same as layer 10), stacked on #1558.
- Uncommitted, all layer 11 (TASK-140.9) plus this doc:
  - production: `app/contracts/operations/codes.py`, `app/packages/incident/scribe/{status_update.py,status_update_prompt.py,platforms/slack.py,entrypoints/slack.py,README.md}`, `app/packages/incident/scribe/locales/incident_status_update.{en-US,fr-FR}.yml`
  - tests edited: `app/tests/unit/packages/incident/scribe/test_incident_scribe_plugin_registration.py`, `..._status_update_{review,history,published}_entrypoint.py` (TestRegister), `..._status_update_review_view.py`
  - tests new: `app/tests/unit/packages/incident/scribe/test_incident_scribe_status_update_redraft{,_prompt,_view,_entrypoint}.py`, `app/tests/integration/packages/incident/scribe/test_incident_scribe_status_update_redraft_dispatch.py`
  - backlog: the TASK-140.9 task file (CLI edits: In Progress, ACs, notes), this doc.
- Gates on layer 11 (app/): ruff check and format clean, lint-imports 10 kept, mypy 57 repo-wide with 0 in touched files, `pytest tests/unit tests/integration` 3653 passed. Single-process `pytest tests --ignore=tests/smoke`: 4416 passed, 20 failed = 6 known TASK-90 + 14 scribe `capture_logs` tests (TASK-90 leak 2: `configure_logging`'s pytest branch sets `cache_logger_on_first_use=True`). All 14 pass in isolation. TASK-90 is deferred by the human to a later standalone PR (local branch `fix/task-90-test-order-leaks`).
- No background agents.

## Next actions

1. **human**: commit layer 11 and submit:
   ```bash
   git add app/contracts/operations/codes.py app/packages/incident/scribe app/tests/unit/packages/incident/scribe app/tests/integration/packages/incident/scribe "backlog/tasks/task-140.9 - Redraft-a-status-update-from-reviewer-instructions-in-the-review-modal.md" "backlog/docs/stacks/doc-5 - Stack-H-handoff.md"
   git commit -m "Redraft a status update from instructions"
   gh stack submit
   ```
2. **human**: run the manual workspace checks listed in the Layers notes for layers 8-11.
3. **human**: merge bottom-up, re-approving after each rebase: #1556, #1557, #1558, then layer 11's PR. After each merge, `gh stack rebase` and push, then set that layer's task to Done. Agents never set Done.
4. **human**: set Done for the merged layers 140.4, 140.5.1, 140.5.2, 140.5.3, 140.10.1, 140.10.2, 140.6.1 and for the coordinators 140.5, 140.10, 140.6 (after 140.6.2) and 140.8 (after 140.8.2).
5. **agent** (new session): TASK-140.7 legacy cutover as a standalone PR off main, once Stack H is merged.

## Open decisions

- None pending.
- Settled 2026-10-07/08 (details in each task's plan and notes): modal-only flow, `views.update` in place everywhere; async scribe services calling the sync store inline, one `asyncio.run` per Slack listener; approval stops at APPROVED; forward-only stage floor; copy-ready text as a preformatted block per language; security confirmation at drafting and redrafting; 140.8 split into 140.8.1/140.8.2; FR toggle strings feminine ("publiée"); 140.9 redraft from the reviewer's form values, conflict shows "changed elsewhere", instructions not stored; TASK-90 fixed later outside the stack.

## Planning queue

- Empty for Stack H; every layer is implemented.
- Follow-ups outside the stack: TASK-140.7 (legacy cutover, next), TASK-90 (test-order leaks), TASK-140.11 (timer drafts, low), TASK-140.12 (un-approve or correct, low).
