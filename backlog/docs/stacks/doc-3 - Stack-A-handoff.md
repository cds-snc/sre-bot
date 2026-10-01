---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-10-01 12:49'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

**Status: part 2 in progress (2026-10-01).** Part 1 (layers 0-6, GitHub stack #1506) merged to `main`. The three standalone prerequisites merged too: TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515). TASK-26.1 was decomposed into three layers with approved plans. Part 2 is a new stack (`gh stack init` done) whose bottom layer targets `main`. Nothing in part 2 is pushed yet.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0-6 | planning, TASK-18, 105, 105.1, 105.2, 105.3, 106 | `stack-a/*` | #1504-#1511 (stack #1506) | merged | Part 1: import-linter contracts (a)-(h), OperationResult envelope, ErrorCode registry, app/contracts/operations/. |
| 7a | TASK-26.1.1 | `stack-a/task-26.1.1-slack-models-to-contracts` | - | ready | Committed: 90d9d72a (planning) and 1a87d62a (implementation). Also fixes the help.py locale bug (user-visible) and deprecated utcnow. |
| 7b | TASK-26.1.2 | `stack-a/task-26.1.2-slack-lookup-adapters` | - | in progress | Implementation done, gates green, ACs checked, notes written; uncommitted. Slack lookups in rant, incident_draft and incident_summary run through package Protocols (service.py) implemented in adapters/slack.py and wired by providers.py. |
| 7c | TASK-26.1.3 | `stack-a/task-26.1.3-slack-registrar-reply` | - | plan approved | SlackCommandRegistrar and SlackReplyPort; register_slack_commands re-signed, register_slack_listeners deleted, all 8 hookimpls; deletes 4 contract (e) entries. Must also remove the stale TYPE_CHECKING imports of infrastructure.platforms.providers.slack in access/sync and geolocate, and drop the optional port parameter on handle_summarize_command (task notes). Closest review. |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | Needs TASK-26.1.3. No plan yet. |

TASK-26.1 is the parent of 7a-7c; it is done when they are.

## Position

Branch `stack-a/task-26.1.2-slack-lookup-adapters`, on top of 1a87d62a. Uncommitted: the whole 7b implementation (app/packages/rant, app/packages/incident_draft, app/packages/incident_summary, their tests under app/tests/unit/packages/, app/tests/integration/legacy_surface/conftest.py) plus task edits on TASK-26.1.2 (status, ACs, notes) and TASK-26.1.3 (hand-off note) and this doc. All belong to the 7b commit. No background agents.

Gate results for 7b (from `app/`): ruff clean; lint-imports 8 kept with no new ignore entry; mypy 0 errors in touched files (67 repo-wide, all elsewhere); legacy_surface 17 passed; full suite 3563 passed and 6 failed, the 6 being the known order-dependent failures in test_webhooks_aws_sns.py and unit/infrastructure/directory/test_google.py, which pass on their own.

## Next actions

1. **human**: review and commit 7b, then open the 7c layer:
   ```shell
   git add app/ backlog/
   git commit -m "refactor(packages): move Slack lookups in rant, incident_draft and incident_summary behind package adapters (TASK-26.1.2)"
   gh stack add stack-a/task-26.1.3-slack-registrar-reply
   ```
2. **agent**: implement TASK-26.1.3 from its plan (TDD, gates, ACs, notes, left In Progress), then hand over commit commands.
3. **human**: commit 7c; decide whether to plan TASK-107 before submitting.
4. **human**: `gh stack submit` when the layers are ready; merge bottom-up one layer at a time, with a re-approval per rebased layer (doc-2 rules).

## Open decisions

- 7a carries a one-line user-visible bug fix (Slack argument help now honours the user's locale; before, it always rendered en-US). It is kept per the fix-bugs-in-touched-files rule. If the reviewer wants 7a to be purely mechanical, split it into its own task/PR.
- 7b moves the three packages' lookups onto `integrations.slack.client.get_slack_web_client()`, so those calls now carry that factory's timeout and retry handlers instead of the Bolt app client's defaults. Same token, same calls and arguments. This follows from the approved plan; flag it in the PR description.
- 7b came out larger than the plan's estimate (14 production files, about 320 added lines, against 12 files and 140 LOC). It is one subsystem and behaviour-neutral, so it was kept as one layer; split per package if the reviewer prefers.

## Planning queue

- TASK-107: plan once TASK-26.1.3's shape is final (after 7c is implemented), since it moves the re-signed hookspecs to app/contracts/.
