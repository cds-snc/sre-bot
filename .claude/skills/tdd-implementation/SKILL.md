---
name: tdd-implementation
description: Implement approved work from existing failing tests with minimal code and quality-gate verification. Accepts a backlog task id.
argument-hint: "[task-id or description]"
disable-model-invocation: true
---

# TDD Implementation

Implement `$ARGUMENTS`.

**Run as**: `implementation` agent · Tier M (Claude Sonnet 5).
**Follow**: [backlog-task-workflow](../backlog-task-workflow/SKILL.md) and
[python-quality-gates](../python-quality-gates/SKILL.md).

## Steps

1. If the input is a backlog task id, read it and its approved plan first
   (`backlog task view <id> --plain`). A task **without** an approved plan goes
   back to `/plan-task` — do not start coding. Then
   `backlog task edit <id> -s "In Progress" -a @me`.
2. Restate the acceptance criteria and the failing-test backlog.
3. Write the minimal code that satisfies the failing tests. Existing failing tests
   are the contract — modify a test only when the architecture changed or the test
   is provably wrong, and say so explicitly.
4. Keep every change inside the approved architecture boundaries.
5. Refactor once green.
6. Run the quality gates every 3-5 edits and before completion. Report the actual
   command output as evidence.
7. Check off each acceptance criterion as its test verifies it
   (`backlog task edit <id> --check-ac <index>`) — one by one, never batched at
   the end. Record `--notes`: what changed, test evidence, DoD items left for
   human verification.
8. Summarize the diff against the acceptance criteria.

## Stop Conditions

- The diff grows past the single-PR size gate → stop, return to `/plan-task` for
  decomposition rather than finishing an unreviewable PR.
- A gate fails for a pre-existing unrelated reason → report it explicitly, do not
  fix it opportunistically.
- Never set a task to Done. Never run git commands.
