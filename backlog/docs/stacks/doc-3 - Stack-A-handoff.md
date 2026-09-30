---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-29 20:44'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

**Status: part 2 in progress (2026-09-29).** Part 1 (layers 0-6, GitHub stack #1506) merged to `main`. The three standalone prerequisites merged too: TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515). TASK-26.1 was decomposed into three layers with approved plans. Part 2 is a new stack (`gh stack init` done) whose bottom layer targets `main`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0-6 | planning, TASK-18, 105, 105.1, 105.2, 105.3, 106 | `stack-a/*` | #1504-#1511 (stack #1506) | merged | Part 1: import-linter contracts (a)-(h), OperationResult envelope, ErrorCode registry, app/contracts/operations/. |
| 7a | TASK-26.1.1 | `stack-a/task-26.1.1-slack-models-to-contracts` | - | in progress | First commit = planning (90d9d72). Implementation done, gates green, ACs checked; uncommitted. Also fixes the help.py locale bug (user-visible) and deprecated utcnow. |
| 7b | TASK-26.1.2 | `stack-a/task-26.1.2-slack-lookup-adapters` | - | plan approved | Slack lookups in rant, incident_draft and incident_summary behind package Protocols in adapters/; behaviour-neutral. |
| 7c | TASK-26.1.3 | `stack-a/task-26.1.3-slack-registrar-reply` | - | plan approved | SlackCommandRegistrar and SlackReplyPort; register_slack_commands re-signed, register_slack_listeners deleted, all 8 hookimpls; deletes 4 contract (e) entries. Must also remove the stale TYPE_CHECKING imports of infrastructure.platforms.providers.slack in access/sync and geolocate (task note). Closest review. |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | Needs TASK-26.1.3. No plan yet. |

TASK-26.1 is the parent of 7a-7c; it is done when they are.

## Position

Branch `stack-a/task-26.1.1-slack-models-to-contracts`. Uncommitted: the whole 7a implementation (app/contracts/slack/, app/tests/unit/contracts/slack/, 25 importer files, app/pyproject.toml, help.py locale fix, geolocate typing fix) plus task edits on TASK-26.1.1 (ACs, notes) and TASK-26.1.3 (hand-off note) and this doc. All belong to the 7a commit. No background agents.

## Next actions

1. **human**: review and commit 7a, then open the 7b layer:
   ```shell
   git add app/ backlog/
   git commit -m "refactor(contracts): move Slack command models to app/contracts/slack (TASK-26.1.1)"
   gh stack add stack-a/task-26.1.2-slack-lookup-adapters
   ```
2. **agent**: implement TASK-26.1.2 from its plan (TDD, gates, ACs, notes, left In Progress), then hand over commit commands.
3. **human**: commit 7b; `gh stack add stack-a/task-26.1.3-slack-registrar-reply`.
4. **agent**: implement TASK-26.1.3.
5. **human**: `gh stack submit` when the layers are ready; merge bottom-up one layer at a time, with a re-approval per rebased layer (doc-2 rules).

## Open decisions

- 7a carries a one-line user-visible bug fix (Slack argument help now honours the user's locale; before, it always rendered en-US). It is kept per the fix-bugs-in-touched-files rule. If the reviewer wants 7a to be purely mechanical, split it into its own task/PR.

## Planning queue

- TASK-107: plan once TASK-26.1.3's shape is final (after 7c is implemented), since it moves the re-signed hookspecs to app/contracts/.
