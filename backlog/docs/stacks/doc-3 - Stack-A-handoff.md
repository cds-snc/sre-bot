---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-28 17:11'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`. GitHub stack #1506.

**Status: paused after layer 6 (2026-09-28).** Layers 0-6 are submitted and in review. Layer 7 (TASK-26.1) is blocked on two standalone PRs, so the stack stops here until they merge. The dependencies were re-checked against doc-2 and kept.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | planning (docs only) | `stack-a/plan` | #1504 | in review | Realigned Stack A and Wave 0 to current decisions; created TASK-105.1, 105.2, 36.1-36.3 and 133; added this doc and the `stacked-pr-session` skill. |
| 1 | TASK-18 | `stack-a/task-18-import-linter` | #1505 | in review | import-linter with 7 contracts and a shrink-only ignore list; contract (c) deferred to TASK-106. |
| 2 | TASK-105 | `stack-a/task-105-operation-result-envelope` | #1507 | in review | OperationResult frozen, monad helpers removed, `cause` added; `message` optional and `retry_after` a float, which left mypy errors at call sites (cleared by TASK-105.3). |
| 3 | TASK-105.1 | `stack-a/task-105.1-drop-provider-operation` | #1508 | in review | Dropped `provider`/`operation`; deleted the unused operations classifiers. |
| 4 | TASK-105.2 | `stack-a/task-105.2-error-code-registry` | #1509 | in review | `ErrorCode` StrEnum (76 members) plus an AST scan that fails on an unregistered static `error_code`. |
| 5 | TASK-105.3 | `stack-a/task-105.3-result-message-call-sites` | #1510 | in review | Cleared the widening mypy errors at call sites; fixed a `None < str` crash in `incident_folder.get_incidents_from_sheet`. Reviewer to check the 12 fallback messages in packages/access. |
| 6 | TASK-106 | `stack-a/task-106-contracts` | #1511 | in review | Created app/contracts/operations/, deleted app/infrastructure/operations/ (137 importers rewritten), added import-linter contract (c), removed 45 ignore entries. |
| 7 | TASK-26.1 | `stack-a/task-26.1-slack-handler-contract` | - | planned, blocked | Needs TASK-25.4 and TASK-36 merged. No plan yet. |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned, blocked | Needs TASK-26.1. No plan yet. |

TASK-105.2, 105.3 and 106 each carry implementation notes with their gate output.

## Resume conditions

Resume Stack A when all of these hold:
1. TASK-25.4 (Slack client factory and classifier) has merged. It is a standalone PR off `main` with an approved plan.
2. TASK-35 -> TASK-36 (Slack command inventory and pinning tests) have merged. Both are standalone PRs off `main` with approved plans.
3. TASK-26.1 has an approved plan. Plan it after TASK-25.4 merges: its outbound messaging Protocol wraps 25.4's client factory.

Then add layer 7 on top of whatever remains of the stack: `gh stack add stack-a/task-26.1-slack-handler-contract` (on top of #1511 if it is still open, otherwise the new bottom layer targets `main`).

## Carried into later layers

- TASK-26.1: `packages/geolocate/platforms/slack.py:15` and `packages/access/sync/interactions/slack.py:33` import `SlackPlatformProvider` under `TYPE_CHECKING` from `infrastructure.platforms.providers.slack`, which does not exist. mypy's incremental cache usually hides the error. The fix needs a contract type (or a new contract (e) ignore entry, which the list forbids), so it belongs with TASK-26.1's Slack contract.

## Planning queue

- TASK-26.1: after TASK-25.4 merges.
- TASK-107: after TASK-26.1's plan is approved.
