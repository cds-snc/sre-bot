---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-28 15:37'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | planning (docs only) | `stack-a/plan` | #1504 | in review | Realigns Stack A and Wave 0 to current decisions: task edits, TASK-105.1, 105.2, 36.1-36.3, 133 created, doc-2 updated, this doc, the `stacked-pr-session` skill. |
| 1 | TASK-18 | `stack-a/task-18-import-linter` | #1505 | in review | 7 contracts kept; 143 seeded ignores; contract (c) deferred to TASK-106. |
| 2 | TASK-105 | `stack-a/task-105-operation-result-envelope` | - | in progress | Implemented, gates green, ACs 1-6 checked, uncommitted; waiting on the human commit and submit. Widening message/retry_after adds 29 mypy errors in 16 untouched files (non-blocking in CI: lint-ci runs mypy `|| true`), which TASK-105.3 clears. |
| 3 | TASK-105.1 | `stack-a/task-105.1-drop-provider-operation` | - | plan approved | 18 production files, mechanical; deletes the unused infrastructure/operations/classifiers.py. |
| 4 | TASK-105.2 | `stack-a/task-105.2-error-code-registry` | - | plan approved | ErrorCode StrEnum (76 members) and an AST-scan test. |
| 5 | TASK-105.3 | `stack-a/task-105.3-result-message-call-sites` | - | planned | New 2026-09-28. Clears the 29 mypy errors from TASK-105's widening; depends on TASK-105.1, which may remove some sites. No plan yet. |
| 6 | TASK-106 | `stack-a/task-106-contracts` | - | planned | Plan written, awaiting approval: move to app/contracts/operations/, ~135 files with the same one-line import rewrite, adds import-linter contract (c). |
| 7 | TASK-26.1 | `stack-a/task-26.1-slack-handler-contract` | - | planned | Needs TASK-25.4 and TASK-36 merged first. |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | |

Standalone PRs this stack waits on (not layers): TASK-25.4 (plan approved), TASK-35 -> TASK-36 (plans approved).

## Position

- Stack #1506 on GitHub. Checked out: `stack-a/task-105-operation-result-envelope` (layer 2), on top of `stack-a/task-18-import-linter`.
- Uncommitted work, all for layer 2 (TASK-105): app/infrastructure/operations/result.py, app/integrations/slack/formatter.py, app/tests/unit/infrastructure/test_operations_result.py, app/tests/unit/integrations/slack/test_slack_formatter.py, decisions/operation-result.md, the TASK-105 task file, the new TASK-105.3 task file, and this doc.
- No background agents running.

## Next actions

1. **human**: commit layer 2 and submit the stack:
   ```shell
   git add app/infrastructure/operations/result.py app/integrations/slack/formatter.py \
     app/tests/unit/infrastructure/test_operations_result.py \
     app/tests/unit/integrations/slack/test_slack_formatter.py \
     decisions/operation-result.md backlog/tasks/ backlog/docs/stacks/
   git commit -m "feat(operations): freeze OperationResult, drop monad helpers, add cause (TASK-105)"
   gh stack submit
   ```
   Then give the new PR a description that references decisions/operation-result.md and names TASK-105.3 as the follow-up for the 29 non-blocking mypy errors.
2. **human**: confirm the CI jobs on #1504 and #1505 and on the new layer-2 PR pass, then tick TASK-18 DoD in review.
3. **human**: create layer 3 from the top of the stack:
   ```shell
   gh stack top
   gh stack add stack-a/task-105.1-drop-provider-operation
   ```
4. **agent**: implement TASK-105.1 from its approved plan on `stack-a/task-105.1-drop-provider-operation`, run the gates, check ACs, leave it In Progress with notes, and give the human the commit and `gh stack submit` commands.
5. **agent**: continue with TASK-105.2 the same way.
6. **agent**: plan TASK-105.3 (`/plan-task TASK-105.3`) after TASK-105.1 is implemented, measuring the error list again against the pre-TASK-105 mypy baseline.

## Open decisions

- Approve the TASK-106 plan (open question: test_operations_result.py moves to tests/unit/contracts/operations/, mirroring production).
- Approve the TASK-104 plan (standalone PR).
- Approve the TASK-105.3 plan once written.

## Planning queue

- TASK-105.3: plan after TASK-105.1 is implemented (its site list depends on 105.1).
- TASK-106: plan written against approved layers 1-4; awaiting approval.
- TASK-26.1: plan after TASK-106 is approved.
- TASK-107: plan after TASK-26.1 is approved.
