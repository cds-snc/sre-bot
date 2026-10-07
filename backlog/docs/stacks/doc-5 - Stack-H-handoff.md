---
id: doc-5
title: Stack H handoff
type: guide
created_date: '2026-10-07 14:30'
updated_date: '2026-10-07 23:44'
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
| 8 | TASK-140.6.2 review modal + copy-ready view | `stack-h/task-140.6.2-status-update-review` | [#1556](https://github.com/cds-snc/sre-bot/pull/1556) | in review | ACs 1-6 checked. Deviation: `build_review_error_view`. Moved the Bolt harness to `tests/factories/slack_bolt.py`. Manual workspace checks pending: `rich_text_preformatted` copy fidelity, `views.update` after an update ack. |
| 9 | TASK-140.8.1 approved-updates list + reopen | `stack-h/task-140.8-status-update-history` (pre-split name) | [#1557](https://github.com/cds-snc/sre-bot/pull/1557) | in review | bbba973d. ACs 1-6 checked. `get_status_update_overview`, `status_update_history.get_approved_update`, `build_overview_view`, Open/Back in place, 50-row cap. Fixed catalogue-inconsistent fallbacks (`_language_heading`, FR modal title/Close). Manual checks: Open/Back in place, ET/HE row times. |
| 10 | TASK-140.8.2 published / not published toggle | `stack-h/task-140.8.2-status-update-published` | - | plan approved | Branch created on #1557, no code yet. Core `published_by` + PUBLISHED -> APPROVED + DynamoDB adapter (no Terraform), `set_published` in `status_update_history.py`, toggle in the detail view; ~170 LOC, ~8 files. Never revert the core field once data exists. |
| 11 | TASK-140.9 redraft from reviewer instructions | `stack-h/task-140.9-status-update-redraft` | - | plan approved | Not created yet. Redraft section in the review form, `redraft_status_update` in `status_update.py`, security gate with in-form checkbox, `STATUS_UPDATE_INSTRUCTIONS_INVALID`; ~300 LOC, 6 files. |

Coordinators with no branch: TASK-140.5 (140.5.1-3), TASK-140.6 (140.6.1-2), TASK-140.8 (140.8.1-2), TASK-140.10 (140.10.1-2); AC mappings in their notes. After the stack: TASK-140.7 (legacy cutover, standalone, depends on 140.6 and 140.8.1).

## Position

- Checked out: `stack-h/task-140.8.2-status-update-published` (layer 10) at bbba973d. Uncommitted: this doc only.
- `main` is at 5a23e162 (#1549, #1550, #1555 merged); the open layers (#1556, #1557, layer 10) are not yet rebased onto it.
- Single-process `pytest tests --ignore=tests/smoke` on layer 9: 4235 passed, 14 failed = 6 known TASK-90 + 8 scribe `capture_logs` tests (TASK-90 leak 2: `configure_logging`'s pytest branch sets `cache_logger_on_first_use=True`). They pass in isolation and in the split runs (`pytest tests/unit tests/integration`). TASK-90 is deferred by the human to a later standalone PR (local branch `fix/task-90-test-order-leaks`, tracking `origin/main`; push with `-u origin fix/task-90-test-order-leaks`).
- Imports: ruff PLC0415 is on; inline `__import__`/`importlib` is still missed, grep for it.
- Subagents: write failing tests with a general-purpose agent on opus and an explicit quality bar (structural exact assertions; no `str(view)` matching, `or` assertions, `if` guards, invented enum values or stub plugins; real `OperationResult` fakes; a real-plugin dispatch test via `harness_fixture("incident.scribe")`). The tests-creation agent twice produced vacuous Slack view tests. Then the implementation agent. Review both diffs and rerun every gate yourself.
- Trap: a view test that pins a `t()` fallback fails in the combined run when the fallback differs from the catalogue value. That is a bug; make the fallback match the catalogue.
- No background agents.

## Next actions

1. **human**: commit this doc, rebase the stack onto `main` and submit:
   ```bash
   git add "backlog/docs/stacks/doc-5 - Stack-H-handoff.md"
   git commit -m "Update Stack H handoff"
   git checkout main && git pull
   gh stack checkout stack-h/task-140.8.2-status-update-published
   gh stack rebase
   gh stack submit
   ```
2. **human**: move the merged tasks to Done (`backlog task edit <id> -s Done`): 140.4, 140.5.1, 140.5.2, 140.5.3, 140.10.1, 140.10.2, 140.6.1, then the coordinators 140.5 and 140.10 once their ACs are checked.
3. **agent**: implement TASK-140.8.2 (layer 10) test-first per its approved plan: failing tests (general-purpose opus agent, quality bar), review them, implementation agent, review the diff, rerun gates, check ACs, append notes. Stop at In Progress.
4. **human**: commit layer 10, `gh stack submit`, `gh stack add stack-h/task-140.9-status-update-redraft`.
5. **agent**: implement TASK-140.9 (layer 11) the same way.
6. **human**: merge #1556, #1557, then layers 10-11, bottom-up with re-approval after each rebase; move each task to Done after its merge (agents never set Done). Then TASK-140.7.

## Open decisions

- None pending.
- Settled 2026-10-07 (details in each task's plan and notes): modal-only flow, `views.update` in place everywhere; async scribe services calling the sync store inline, one `asyncio.run` per Slack listener (pivot path to async listeners); approval stops at APPROVED; forward-only stage floor; copy-ready text as a preformatted block per language; security confirmation at drafting and redrafting; 140.8 split into 140.8.1/140.8.2, Open in place with Back, undo clears `published_at` and `published_by`, 50-row cap; 140.9 redraft from the reviewer's form values, conflict shows "changed elsewhere", instructions not stored; TASK-90 fixed later outside the stack.

## Planning queue

- TASK-140.8.2, TASK-140.9: plans approved 2026-10-07 (approval comments on each task).
- Expected textual overlap between layers 10 and 11: `scribe/platforms/slack.py`, `scribe/entrypoints/slack.py` (`register()`), the `incident_status_update` locale files.
- Follow-ups outside the stack: TASK-90 (test-order leaks), TASK-140.7 (legacy cutover), TASK-140.11 (timer drafts, low), TASK-140.12 (un-approve or correct, low).
