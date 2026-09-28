---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-28 16:05'
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
| 4 | TASK-105.2 | `stack-a/task-105.2-error-code-registry` | - | in progress | Implemented, gates green, ACs 1-5 checked, uncommitted; waiting on the human commit and submit. ErrorCode StrEnum (76 members) in app/infrastructure/operations/codes.py plus an AST-scan test. |
| 5 | TASK-105.3 | `stack-a/task-105.3-result-message-call-sites` | - | planned | Clears the 26 remaining mypy errors from TASK-105's widening (list in its notes): 12 production files in 2 subsystems (legacy modules/, packages/access), so planning must decide whether to split it. |
| 6 | TASK-106 | `stack-a/task-106-contracts` | - | planned | Plan written, awaiting approval: move to app/contracts/operations/, ~135 files with the same one-line import rewrite, adds import-linter contract (c). Must now also move codes.py (ErrorCode) and its test. |
| 7 | TASK-26.1 | `stack-a/task-26.1-slack-handler-contract` | - | planned | Needs TASK-25.4 and TASK-36 merged first. |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | |

Standalone PRs this stack waits on (not layers): TASK-25.4 (plan approved), TASK-35 -> TASK-36 (plans approved).

## Position

- Stack #1506 on GitHub. Layers 0-3 are submitted (#1504, #1505, #1507, #1508). Checked out: `stack-a/task-105.2-error-code-registry` (layer 4), on top of `stack-a/task-105.1-drop-provider-operation`.
- Uncommitted work, all for layer 4 (TASK-105.2): app/infrastructure/operations/codes.py (new), app/infrastructure/operations/__init__.py (ErrorCode export), app/tests/unit/infrastructure/operations/test_error_code_registry.py (new), the TASK-105.2 task file, and this doc.
- PR/CI state for #1504-#1508 was not re-checked this session (GitHub API rate limit hit).
- No background agents running.

## Next actions

1. **human**: commit layer 4 and submit the stack:
   ```shell
   git add -A app/infrastructure/operations app/tests/unit/infrastructure/operations \
     backlog/tasks/ backlog/docs/stacks/
   git commit -m "feat(operations): add ErrorCode registry with AST enforcement test (TASK-105.2)"
   gh stack submit
   ```
   Then give the new PR a description that references decisions/operation-result.md.
2. **human**: confirm the CI jobs on #1504, #1505, #1507, #1508 and the layer-4 PR pass; tick TASK-18 DoD in review. #1507's description must reference decisions/operation-result.md and name TASK-105.3 as the follow-up for the non-blocking mypy errors.
3. **agent**: plan TASK-105.3 (`/plan-task TASK-105.3`), using the site list in its notes; decide on a split, since it spans 2 subsystems.
4. **agent**: update the TASK-106 plan to include moving app/infrastructure/operations/codes.py and tests/unit/infrastructure/operations/test_error_code_registry.py (the test hard-codes `parents[4]` as the app root, so its depth matters after the move).

## Open decisions

- Approve the TASK-106 plan (open question: test_operations_result.py moves to tests/unit/contracts/operations/, mirroring production).
- Approve the TASK-104 plan (standalone PR).
- Approve the TASK-105.3 plan once written.

## Planning queue

- TASK-105.3: ready to plan; the site list after TASK-105.1 is in its notes (12 files, 2 subsystems).
- TASK-106: plan written against approved layers 1-4; awaiting approval; needs the codes.py addition (next action 4).
- TASK-26.1: plan after TASK-106 is approved.
- TASK-107: plan after TASK-26.1 is approved.
