---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-28 16:56'
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
| 5 | TASK-105.3 | `stack-a/task-105.3-result-message-call-sites` | #1510 | in review | Cleared all 25 widening errors plus 8 older errors in touched files (repo-wide mypy 102 -> 69); fixed a None < str crash in incident_folder.get_incidents_from_sheet. Fallback wording in packages/access to be reviewed in the PR. |
| 6 | TASK-106 | `stack-a/task-106-contracts` | - | in progress | Implemented, gates green, ACs 1-6 checked, uncommitted; waiting on the human commit and submit. app/contracts/operations/ created, app/infrastructure/operations/ deleted, 137 importers rewritten, contract (c) added, 45 ignore entries removed. |
| 7 | TASK-26.1 | `stack-a/task-26.1-slack-handler-contract` | - | planned | Needs TASK-25.4 and TASK-36 merged first. Also fix the dead TYPE_CHECKING import of infrastructure.platforms.providers.slack in packages/geolocate/platforms/slack.py and packages/access/sync/interactions/slack.py (found in TASK-106). |
| 8 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | |

Standalone PRs this stack waits on (not layers): TASK-25.4 (plan approved), TASK-35 -> TASK-36 (plans approved).

## Position

- Stack #1506 on GitHub. Layers 0-5 are submitted (#1504, #1505, #1507, #1508, #1509, #1510). Checked out: `stack-a/task-106-contracts` (layer 6), on top of `stack-a/task-105.3-result-message-call-sites`.
- Uncommitted work, all for layer 6 (TASK-106): new app/contracts/ and app/tests/unit/contracts/ (untracked), deleted app/infrastructure/operations/ and the two old test files, 137 rewritten importers across app/, app/pyproject.toml, app/infrastructure/__init__.py, decisions/{operation-result,outbound-clients,plugin-architecture}.md, the TASK-106 task file, and this doc.
- PR descriptions for #1507-#1509 still need the decisions/operation-result.md reference (#1509 is still the placeholder); #1510's fallback strings await review.
- No background agents running.

## Next actions

1. **human**: commit layer 6 and submit the stack (`-A` on app/ picks up the renames, deletions and the new contracts/ tree):
   ```shell
   git add -A app decisions/operation-result.md decisions/outbound-clients.md decisions/plugin-architecture.md \
     "backlog/tasks/task-106 - Create-app-contracts-and-move-OperationResult-OperationStatus-and-the-error-code-registry-into-it.md" \
     backlog/docs/stacks/
   git commit -m "refactor(contracts): move operations into app/contracts, add import-linter contract (c) (TASK-106)"
   gh stack submit
   ```
2. **human**: fix PR descriptions: set #1509's from the draft (`gh pr edit 1509 --body-file /tmp/claude-1000/-workspace/7d144039-1230-4b9f-8cf0-d383f5322e6c/scratchpad/pr-1509-body.md`; ask the agent to redraft if the scratchpad is gone), add the decisions/operation-result.md reference to #1507 and #1508, and name TASK-105.3 in #1507. Review the fallback strings in #1510.
3. **agent**: plan TASK-26.1 (`/plan-task TASK-26.1`), including the dead Slack provider import found in TASK-106; its implementation waits on TASK-25.4 and TASK-36 merging.

## Open decisions

- Approve the TASK-104 plan (standalone PR).

## Planning queue

- TASK-26.1: ready to plan (TASK-106 approved); implementation also waits on TASK-25.4 and TASK-36 merging.
- TASK-107: plan after TASK-26.1 is approved.
