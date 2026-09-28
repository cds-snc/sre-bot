---
id: doc-3
title: Stack A handoff
type: guide
created_date: '2026-09-28 15:02'
updated_date: '2026-09-28 15:14'
---
# Stack A handoff

## Stack

Stack A, the contracts spine (doc-2, Wave 1). Trunk: `main`.

## Layers

| # | Task | Branch | PR | State | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | planning (docs only) | `stack-a/plan` | - | ready | Realigns Stack A and Wave 0 to current decisions: task edits, TASK-105.1, 105.2, 36.1-36.3, 133 created, doc-2 updated, this doc, the `stacked-pr-session` skill. |
| 1 | TASK-18 | `stack-a/task-18-import-linter` | - | ready | Implemented, gates green, uncommitted. 7 contracts kept; 143 seeded ignores; contract (c) deferred to TASK-106. A new test forces root_packages to list contracts/features/capabilities once they exist. |
| 2 | TASK-105 | `stack-a/task-105-operation-result-envelope` | - | plan approved | 2 production files; also fixes decisions/operation-result.md. |
| 3 | TASK-105.1 | `stack-a/task-105.1-drop-provider-operation` | - | plan approved | 18 production files, mechanical; deletes the unused infrastructure/operations/classifiers.py. |
| 4 | TASK-105.2 | `stack-a/task-105.2-error-code-registry` | - | plan approved | ErrorCode StrEnum (76 members) and an AST-scan test. |
| 5 | TASK-106 | `stack-a/task-106-contracts` | - | planned | Plan written, awaiting approval: move to app/contracts/operations/, ~135 files with the same one-line import rewrite, adds import-linter contract (c). |
| 6 | TASK-26.1 | `stack-a/task-26.1-slack-handler-contract` | - | planned | Needs TASK-25.4 and TASK-36 merged first. |
| 7 | TASK-107 | `stack-a/task-107-hookspecs-to-contracts` | - | planned | |

Standalone PRs this stack waits on (not layers): TASK-25.4 (plan approved), TASK-35 -> TASK-36 (plans approved).

## Position

- On `stack-a/task-18-import-linter`. Layer 0 is committed; layer 1's changes are uncommitted: `.github/workflows/ci_code.yml`, `app/Makefile`, `app/pyproject.toml`, `app/uv.lock`, `app/tests/unit/tooling/`, and the TASK-18 task file.
- No background agents running.

## Next actions

1. **human**: commit layer 1 and open both PRs:
   ```shell
   git add .github/workflows/ci_code.yml app/Makefile app/pyproject.toml app/uv.lock app/tests/unit/tooling backlog/tasks backlog/docs/stacks
   git commit -m "feat(tooling): land import-linter with six-layer contracts (TASK-18)"
   gh stack submit
   ```
   Then put the TASK-18 PR description in place (it must reference decisions/toolchain.md and decisions/plugin-architecture.md), and confirm the "Import contract check" step runs and passes on both PRs.
2. **agent**: start layer 2: after the human runs `gh stack add stack-a/task-105-operation-result-envelope`, implement TASK-105 from its approved plan.
3. **agent**: continue with TASK-105.1 and TASK-105.2 the same way, one `gh stack add` per layer.

## Open decisions

- Approve the TASK-106 plan (open question: test_operations_result.py moves to tests/unit/contracts/operations/, mirroring production).
- Approve the TASK-104 plan (standalone PR).

## Planning queue

- TASK-106: plan written against approved layers 1-4; awaiting approval.
- TASK-26.1: plan after TASK-106 is approved.
- TASK-107: plan after TASK-26.1 is approved.
