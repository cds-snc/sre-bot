---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-28 15:05'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | planning (docs only) | `stack-a/plan` | - | in progress | Realigns Stack A and Wave 0 to current decisions: task edits, TASK-105.1, 105.2, 36.1-36.3, 133 created, doc-2 updated, this doc, the `stacked-pr-session` skill. |
| 1 | TASK-18 | `stack-a/task-18-import-linter` | - | plan approved | Config only, 4 files; about 191 seeded ignores; contract (c) deferred to TASK-106. |
| 2 | TASK-105 | `stack-a/task-105-operation-result-envelope` | - | plan approved | 2 production files; also fixes decisions/operation-result.md. |
| 3 | TASK-105.1 | `stack-a/task-105.1-drop-provider-operation` | - | plan approved | 18 production files, mechanical; deletes the unused infrastructure/operations/classifiers.py. |
| 4 | TASK-105.2 | `stack-a/task-105.2-error-code-registry` | - | plan approved | ErrorCode StrEnum (76 members) and an AST-scan test. |
| 5 | TASK-106 | `stack-a/task-106-contracts` | - | planned | Plan written, awaiting approval: move to app/contracts/operations/, ~135 files with the same one-line import rewrite, adds import-linter contract (c). |
| 6 | TASK-26.1 | `stack-a/task-26.1-slack-handler-contract` | - | planned | Needs TASK-25.4 and TASK-36 merged first. |
| 7 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | |

Standalone PRs this stack waits on (not layers): TASK-25.4 (plan approved), TASK-35 -> TASK-36 (plans approved).

## Position

- On `main`, with the layer 0 changes uncommitted (planning is complete; no background agents running).
- TASK-104 (guidance realignment, 15 files, docs only) has a plan awaiting approval; it ships as a standalone PR, not a layer.

## Next actions

1. **human**: create layer 0 and layer 1:
   ```shell
   git fetch origin && git status          # main must equal origin/main
   git switch -c stack-a/plan
   git add backlog .claude/skills/stacked-pr-session
   git commit -m "plan: realign Stack A and Wave 0 to current decisions"
   gh stack init stack-a/plan
   gh stack add stack-a/task-18-import-linter
   ```
2. **agent**: implement TASK-18 on `stack-a/task-18-import-linter` from its approved plan, run the gates, check ACs, leave it In Progress with notes.
3. **human**: commit layer 1 and open both PRs:
   ```shell
   git add app/pyproject.toml app/uv.lock app/Makefile .github/workflows/ci_code.yml backlog/tasks
   git commit -m "feat(tooling): land import-linter with six-layer contracts (TASK-18)"
   gh stack submit
   ```
4. **agent**: implement TASK-105 on a new layer (`gh stack add stack-a/task-105-operation-result-envelope`), and continue up the approved layers.

## Open decisions

- Approve the TASK-106 plan (open question: test_operations_result.py moves to tests/unit/contracts/operations/, mirroring production).
- Approve the TASK-104 plan (standalone PR).

## Planning queue

- TASK-106: plan written against approved layers 1-4; awaiting approval.
- TASK-26.1: plan after TASK-106 is approved.
- TASK-107: plan after TASK-26.1 is approved.
