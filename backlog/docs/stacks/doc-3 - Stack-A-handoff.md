---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-29 20:21'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

**Status: part 2 planned (2026-09-29).** Part 1 (layers 0-6, GitHub stack #1506) merged to `main`. The three standalone prerequisites merged too: TASK-35 (#1512), TASK-36 (#1513) and TASK-25.4 (#1515). TASK-26.1 was decomposed into three layers with approved plans. Part 2 is a new stack whose bottom layer targets `main`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0-6 | planning, TASK-18, 105, 105.1, 105.2, 105.3, 106 | `stack-a/*` | #1504-#1511 (stack #1506) | merged | Part 1: import-linter contracts (a)-(h), OperationResult envelope, ErrorCode registry, app/contracts/operations/. |
| 7a | TASK-26.1.1 | `stack-a/task-26.1.1-slack-models-to-contracts` | - | plan approved | Five command models to app/contracts/slack/models.py; mechanical; deletes 8 contract (e) ignore entries. |
| 7b | TASK-26.1.2 | `stack-a/task-26.1.2-slack-lookup-adapters` | - | plan approved | Slack lookups in rant, incident_draft and incident_summary behind package Protocols in adapters/; behaviour-neutral. |
| 7c | TASK-26.1.3 | `stack-a/task-26.1.3-slack-registrar-reply` | - | plan approved | SlackCommandRegistrar and SlackReplyPort; register_slack_commands re-signed, register_slack_listeners deleted, all 8 hookimpls; deletes 4 contract (e) entries. Closest review. |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | Needs TASK-26.1.3. No plan yet. |

TASK-26.1 is the parent of 7a-7c; it is done when they are.

## Position

Branch `main`, up to date with #1515. Uncommitted planning edits on `main`: TASK-26.1 plan, new TASK-26.1.1-26.1.3, this doc and doc-2. They carry onto the 7a branch as its first commit. No background agents.

## Next actions

1. **human**: create the 7a branch from `main` with the planning edits, and commit them as the first commit:
   ```shell
   git checkout main && git pull
   gh stack init
   gh stack add stack-a/task-26.1.1-slack-models-to-contracts
   git add backlog/ && git commit -m "plan: decompose TASK-26.1 into Stack A layers 7a-7c"
   ```
2. **agent**: implement TASK-26.1.1 from its plan (TDD, gates, ACs, notes, left In Progress), then hand over commit commands.
3. **human**: commit 7a; `gh stack add stack-a/task-26.1.2-slack-lookup-adapters`.
4. **agent**: implement TASK-26.1.2; then the same for 7c (TASK-26.1.3).
5. **human**: `gh stack submit` when the layers are ready; merge bottom-up one layer at a time, with a re-approval per rebased layer (doc-2 rules).

## Open decisions

None.

## Planning queue

- TASK-107: plan once TASK-26.1.3's shape is final (after 7c is implemented), since it moves the re-signed hookspecs to app/contracts/.
