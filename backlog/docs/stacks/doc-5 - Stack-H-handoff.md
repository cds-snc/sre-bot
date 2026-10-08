---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-08 00:16'
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
| 8 | TASK-140.6.2 review modal + copy-ready view | `stack-h/task-140.6.2-status-update-review` | [#1556](https://github.com/cds-snc/sre-bot/pull/1556) | in review | Rebased on main 5a23e162. ACs 1-6 checked. Deviation: `build_review_error_view`. Bolt harness in `tests/factories/slack_bolt.py`. Manual workspace checks pending: `rich_text_preformatted` copy fidelity, `views.update` after an update ack. |
| 9 | TASK-140.8.1 approved-updates list + reopen | `stack-h/task-140.8-status-update-history` (pre-split name) | [#1557](https://github.com/cds-snc/sre-bot/pull/1557) | in review | 3627148c. ACs 1-6 checked. Manual checks: Open/Back in place, ET/HE row times. |
| 10 | TASK-140.8.2 published / not published toggle | `stack-h/task-140.8.2-status-update-published` | [#1558](https://github.com/cds-snc/sre-bot/pull/1558) | ready (uncommitted) | ACs 1-5 checked, notes with gate evidence. PR #1558 so far holds only the handoff-doc commit b43c78b5; the layer's code is uncommitted. Core `published_by` + PUBLISHED -> APPROVED + DynamoDB adapter (no Terraform); `set_published`; toggle as the `approved_status` section's accessory; `build_published_error_view`. Never revert the core field once data exists. Manual checks: toggle in place in a real modal, ET/HE published line. |
| 11 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | plan approved | Not created yet. Redraft section in the review form, `redraft_status_update` in `status_update.py`, security gate with in-form checkbox, `STATUS_UPDATE_INSTRUCTIONS_INVALID`; ~300 LOC, 6 files. Last layer of the stack. |

Coordinators with no branch: TASK-140.5 (140.5.1-3), TASK-140.6 (140.6.1-2), TASK-140.8 (140.8.1-2), TASK-140.10 (140.10.1-2); AC mappings in their notes. After the stack: TASK-140.7 (legacy cutover, standalone, depends on 140.6 and 140.8.1).

## Position

- Checked out: `stack-h/task-140.8.2-status-update-published` (layer 10) at b43c78b5, on top of #1557, stack rebased on main 5a23e162.
- Uncommitted, all layer 10 (TASK-140.8.2) plus this doc:
  - production: `app/packages/incident/core/{domain.py,api.py,adapters/status_updates.py}`, `app/packages/incident/scribe/{status_update_history.py,platforms/slack.py,entrypoints/slack.py,README.md}`, `app/packages/incident/scribe/locales/incident_status_update.{en-US,fr-FR}.yml`
  - tests edited: `app/tests/unit/packages/incident/core/test_incident_core_status_update_{fake,record,store}.py`, `app/tests/unit/packages/incident/scribe/test_incident_scribe_status_update_{history_entrypoint,history_view,review_entrypoint}.py`
  - tests new: `app/tests/unit/packages/incident/scribe/test_incident_scribe_status_update_published{,_view,_entrypoint}.py`, `app/tests/integration/packages/incident/scribe/test_incident_scribe_status_update_published_dispatch.py`
  - backlog: the TASK-140.8.2 task file (CLI edits: In Progress, ACs, notes), this doc.
- Single-process `pytest tests --ignore=tests/smoke` on layer 10: 4311 passed, 16 failed = 6 known TASK-90 + 10 scribe `capture_logs` tests (TASK-90 leak 2: `configure_logging`'s pytest branch sets `cache_logger_on_first_use=True`; layer 10 added 2 in `..._published_entrypoint.py`). They pass in isolation and in the split run (`pytest tests/unit tests/integration`: 3544 passed). TASK-90 is deferred by the human to a later standalone PR (local branch `fix/task-90-test-order-leaks`).
- mypy: 57 errors repo-wide, 0 in touched files (the 3 under `packages/incident` are in untouched `scheduling` and `meet` adapters).
- Imports: ruff PLC0415 is on; inline `__import__`/`importlib` is still missed, grep for it.
- Subagents: write failing tests with a general-purpose agent on opus and an explicit quality bar (structural exact assertions; no `str(view)` matching, `or` assertions, `if` guards, invented enum values or stub plugins; real `OperationResult` fakes; a real-plugin dispatch test via `harness_fixture("incident.scribe")`). Then the implementation agent (opus) with the exact names the test agent chose. Review both diffs and rerun every gate yourself.
- Trap: a view test that pins a `t()` fallback fails in the combined run when the fallback differs from the catalogue value. That is a bug; make the fallback match the catalogue.
- No background agents.

## Next actions

1. **human**: commit layer 10 and submit, then create layer 11:
   ```bash
   git add app/packages/incident/core app/packages/incident/scribe app/tests/unit/packages/incident app/tests/integration/packages/incident/scribe "backlog/tasks/task-140.8.2 - Mark-an-approved-status-update-as-published-or-not-published-from-its-copy-ready-view.md" "backlog/docs/stacks/doc-5 - Stack-H-handoff.md"
   git commit -m "Mark a status update published or not"
   gh stack submit
   gh stack add stack-h/task-140.9-status-update-redraft
   ```
2. **human**: move the merged tasks to Done (`backlog task edit <id> -s Done`): 140.4, 140.5.1, 140.5.2, 140.5.3, 140.10.1, 140.10.2, 140.6.1, then the coordinators 140.5 and 140.10 once their ACs are checked.
3. **agent**: implement TASK-140.9 (layer 11) test-first per its approved plan: In Progress, failing tests (general-purpose opus agent, quality bar), review them, implementation agent, review the diff, rerun gates, check ACs, append notes. Stop at In Progress.
4. **human**: commit layer 11 and `gh stack submit`.
5. **human**: merge #1556, #1557, #1558, then layer 11, bottom-up with re-approval after each rebase; move each task to Done after its merge (agents never set Done), then coordinators 140.6 and 140.8. Then TASK-140.7.

## Open decisions

- None pending.
- Settled 2026-10-07/08 (details in each task's plan and notes): modal-only flow, `views.update` in place everywhere; async scribe services calling the sync store inline, one `asyncio.run` per Slack listener; approval stops at APPROVED; forward-only stage floor; copy-ready text as a preformatted block per language; security confirmation at drafting and redrafting; 140.8 split into 140.8.1/140.8.2, Open in place with Back, undo clears `published_at` and `published_by`, 50-row cap, toggle as the status section's accessory, FR toggle strings feminine ("publiée"); 140.9 redraft from the reviewer's form values, conflict shows "changed elsewhere", instructions not stored; TASK-90 fixed later outside the stack.

## Planning queue

- TASK-140.9: plan approved 2026-10-07 (approval comment on the task).
- Expected textual overlap between layers 10 and 11: `scribe/platforms/slack.py`, `scribe/entrypoints/slack.py` (`register()`: layer 11 must keep `PUBLISHED_ACTION_ID` in the `TestRegister` expected dicts), the `incident_status_update` locale files.
- Follow-ups outside the stack: TASK-90 (test-order leaks), TASK-140.7 (legacy cutover), TASK-140.11 (timer drafts, low), TASK-140.12 (un-approve or correct, low).
