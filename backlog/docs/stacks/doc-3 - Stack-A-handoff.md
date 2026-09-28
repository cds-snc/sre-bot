---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-28 16:40'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | planning (docs only) | `stack-a/plan` | #1504 | in review | Realigns Stack A and Wave 0 to current decisions: task edits, TASK-105.1, 105.2, 36.1-36.3, 133 created, doc-2 updated, this doc, the `stacked-pr-session` skill. |
| 1 | TASK-18 | `stack-a/task-18-import-linter` | #1505 | in review | 7 contracts kept; 143 seeded ignores; contract (c) deferred to TASK-106. |
| 2 | TASK-105 | `stack-a/task-105-operation-result-envelope` | #1507 | in review | Widening message/retry_after adds 29 mypy errors in 16 untouched files (non-blocking in CI: lint-ci runs mypy `\|\| true`), which TASK-105.3 clears. |
| 3 | TASK-105.1 | `stack-a/task-105.1-drop-provider-operation` | #1508 | in review | Deleted classifiers.py. Also cleared 3 of TASK-105.3's errors (26 remain, 13 files). |
| 4 | TASK-105.2 | `stack-a/task-105.2-error-code-registry` | #1509 | in review | ErrorCode StrEnum (76 members) in app/infrastructure/operations/codes.py plus an AST-scan test. PR body still the gh-stack placeholder; draft ready (see Next actions). |
| 5 | TASK-105.3 | `stack-a/task-105.3-result-message-call-sites` | - | in progress | Implemented, gates green, ACs 1-3 checked, uncommitted; waiting on the human commit and submit. Cleared all 25 widening errors plus 8 older errors in touched files (repo-wide mypy 102 -> 69); fixed a None < str crash in incident_folder.get_incidents_from_sheet. |
| 6 | TASK-106 | `stack-a/task-106-contracts` | - | planned | Plan written and amended for codes.py, awaiting approval: move to app/contracts/operations/, 135 files (confirmed) with the same one-line import rewrite, adds import-linter contract (c). codes.py travels with the directory move; registry test keeps parents[4]. |
| 7 | TASK-26.1 | `stack-a/task-26.1-slack-handler-contract` | - | planned | Needs TASK-25.4 and TASK-36 merged first. |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | |

Standalone PRs this stack waits on (not layers): TASK-25.4 (plan approved), TASK-35 -> TASK-36 (plans approved).

## Position

- Stack #1506 on GitHub. Layers 0-4 are submitted (#1504, #1505, #1507, #1508, #1509). Checked out: `stack-a/task-105.3-result-message-call-sites` (layer 5), on top of `stack-a/task-105.2-error-code-registry`.
- Uncommitted work for layer 5 (TASK-105.3): 11 production files (app/modules/{provisioning/users.py,provisioning/groups.py,incident/incident_folder.py,incident/db_operations.py,permissions/handler.py,slack/webhooks.py}, app/packages/access/{catalog/service.py,request/schemas.py,sync/desired_state.py,sync/adapters/aws_identity_center.py,sync/adapters/fake_platform.py}), 7 test files edited in place, the TASK-105.3 task file, and this doc.
- Also uncommitted but NOT part of layer 5: the amended TASK-106 plan (backlog/tasks/task-106 - ...md). Leave it out of the layer-5 commit; it carries forward to the TASK-106 layer.
- CI green on #1504-#1508 at last check; #1509 was pending.
- None of #1507, #1508, #1509 reference decisions/operation-result.md in their descriptions yet; #1507 does not name TASK-105.3.
- No background agents running.

## Next actions

1. **human**: commit layer 5 and submit the stack (the TASK-106 task file stays uncommitted):
   ```shell
   git add -A app/modules app/packages/access app/tests \
     "backlog/tasks/task-105.3 - Clear-the-mypy-errors-from-the-optional-OperationResult-message-and-float-retry_after-at-call-sites.md" \
     backlog/docs/stacks/
   git commit -m "fix(operations): clear optional message/retry_after mypy errors at call sites (TASK-105.3)"
   gh stack submit
   ```
   In the PR, review the 12 fallback strings in packages/access (a decision deferred to PR review).
2. **human**: fix PR descriptions: set #1509's from the draft (`gh pr edit 1509 --body-file /tmp/claude-1000/-workspace/7d144039-1230-4b9f-8cf0-d383f5322e6c/scratchpad/pr-1509-body.md`; ask the agent to redraft if the scratchpad is gone), add the decisions/operation-result.md reference to #1507 and #1508, and name TASK-105.3 in #1507.
3. **human**: answer the TASK-106 open decisions and approve its plan.
4. **human**: once TASK-106 is approved, create layer 6 (the TASK-106 plan edit carries onto it):
   ```shell
   gh stack top
   gh stack add stack-a/task-106-contracts
   ```
5. **agent**: implement TASK-106 from its approved plan.

## Open decisions

- TASK-106: test_operations_result.py moves to tests/unit/contracts/operations/ (mirroring production) vs flat tests/unit/contracts/.
- TASK-106: the 135-file single-PR size-gate exception (mechanical import rewrite; a partial move cannot keep main green).
- Approve the TASK-104 plan (standalone PR).

## Planning queue

- TASK-106: plan written and amended for codes.py; awaiting approval.
- TASK-26.1: plan after TASK-106 is approved.
- TASK-107: plan after TASK-26.1 is approved.
