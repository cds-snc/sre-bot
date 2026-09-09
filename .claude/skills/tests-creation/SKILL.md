---
name: tests-creation
description: Create or update the smallest deterministic set of failing behavior tests from an approved architecture packet or planned backlog task.
argument-hint: "[task-id or spec reference]"
disable-model-invocation: true
---

# Create Failing Tests

Author failing tests for `$ARGUMENTS`.

**Run as**: `tests-creation` agent · Tier L (Claude Haiku 4.5) — this is
spec-driven mechanical work and does not need a reasoning-tier model.
**Follow**: [testing-standards](../testing-standards/SKILL.md).

## Steps

1. Restate the test acceptance criteria from the feature architecture packet, or —
   for a backlog task — from its acceptance criteria and plan
   (`backlog task view <id> --plain`). When a plan exists, its test matrix is the
   source of truth.
2. Create or update tests in `app/tests/` with feature-prefix naming
   (`test_<domain>_<entity>_<action>.py`).
3. Cover success and failure-mapping paths first.
4. Add the boundary and contract tests that protect ingress/egress behavior.
5. Run the targeted tests and confirm each fails **for the intended reason** —
   a test failing on an import error is not yet a valid failing test.
6. Report the failing set as the implementation backlog.

## Hard Constraints

- Do not edit non-test files, except essential fixtures/fakes under test scope.
- Do not implement feature behavior in production modules.
- Never author tests that assert on architecture-packet wording, sprint labels or
  documentation metadata.
- Docstrings describe observable behavior, stub strategy and assertion rationale
  only — never task ids, plan step numbers or phase language.
- Keep assertions behavior-focused and deterministic; use dependency overrides and
  Protocol-conformant fakes.
- Do not run `app/tests/smoke/*`.
- Do not check off acceptance criteria here — verification happens during implementation.

## Output

Tests created/updated · why each exists, mapped to an AC · execution output showing
the intended failures · the derived implementation backlog.
