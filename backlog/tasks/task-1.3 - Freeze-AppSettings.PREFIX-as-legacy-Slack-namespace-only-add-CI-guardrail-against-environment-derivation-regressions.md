---
id: TASK-1.3
title: >-
  Freeze AppSettings.PREFIX as legacy Slack namespace only; add local guardrail
  against environment-derivation regressions
status: In Progress
assignee: []
created_date: '2026-07-21 18:56'
updated_date: '2026-07-22 13:43'
labels:
  - phase-0
  - security
milestone: m-0
dependencies:
  - TASK-1.2
references:
  - decisions/configuration.md
  - decisions/transport-slack.md
  - decisions/migration.md
parent_task_id: TASK-1
priority: high
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Close-out + regression lock for TASK-1, and the ratchet that drives PREFIX retirement (TASK-45). TASK-1.2.3 removed every is_production and PREFIX-derived environment branch. PREFIX remains only for the legacy Slack command namespace until TASK-45 cutovers complete.

Revised scope (single-maintainer/local-first):
1) Annotate AppSettings.PREFIX as legacy Slack command-namespace ONLY, no environment meaning, being retired via SLACK__COMMAND_PREFIX (TASK-45), then deleted at final cutover. Cross-reference decisions/configuration.md and decisions/transport-slack.md.
2) Add a local guardrail script under app/bin/ with a checked-in baseline under app/bin/baselines/ that fails on any is_production, PREFIX == / PREFIX != derivation forms, stale baseline entries, and net-new PREFIX readers not present in baseline.
3) Keep the guardrail lightweight: run locally via app/Makefile target and built-in script self-tests; do not add a mandatory GitHub Actions workflow step for this temporary retirement tracker.

Scope boundaries: no app/modules/** edits and no COMMAND_PREFIX introduction in this task (that remains TASK-45).
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Implementation references decisions/configuration.md and decisions/transport-slack.md in code/task context.
- [x] #2 Local verification is green: app settings unit tests, guardrail self-tests, and make check-prefix-guardrail.
<!-- DOD:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AppSettings.PREFIX in app/infrastructure/configuration/app.py is documented as legacy Slack command-namespace only, no environment meaning, with retirement path via SLACK__COMMAND_PREFIX (TASK-45) and deletion at final cutover; existing AppSettings behavior remains unchanged.
- [x] #2 A committed local guardrail under app/bin/ compares the tree against app/bin/baselines/prefix_readers.txt and fails on: any is_production identifier; any PREFIX == / PREFIX != derivation form; and any net-new PREFIX reader absent from the baseline. It exits 0 on the current tree.
- [x] #3 Baseline ratchet is enforced: a reader removed from the tree must be removed from the baseline (stale-entry violation), and net-new readers fail with file:line output.
- [x] #4 A Makefile target check-prefix-guardrail exists and runs the guardrail locally; no mandatory GitHub Actions workflow step is required for this temporary retirement tracker.
- [x] #5 Regression behavior is verified via built-in self-tests (--self-test) covering reject-new-consumer, reject-is_production, reject PREFIX derivation comparisons, accept baseline-shrink, and reject stale-baseline-entry.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Step 1 — Doc annotation (AC #1)
Update app/infrastructure/configuration/app.py PREFIX field with explicit Field(description=...) text: legacy Slack command namespace only, no environment meaning, retirement path via SLACK__COMMAND_PREFIX (TASK-45), and deletion when final module cuts over. Keep behavior unchanged.

Step 2 — Guardrail script + baseline (AC #2, #3)
Create app/bin/check_prefix_command_namespace.py with:
- Violation dataclass
- find_violations(root, baseline) scanner using ast
- Rules: reject is_production; reject PREFIX == / PREFIX != derivation forms; reject net-new PREFIX readers not in baseline; reject stale baseline entries whose file no longer reads PREFIX.
Create app/bin/baselines/prefix_readers.txt seeded with current legacy readers and ratchet-down-only comments.

Step 3 — Local tooling integration (AC #4 revised)
Add app/Makefile target check-prefix-guardrail to run the guardrail locally. Do not wire a mandatory CI step in .github/workflows/ci_code.yml for this temporary tracker.

Step 4 — Regression verification (AC #5 revised)
Implement built-in script self-tests via --self-test covering:
(a) current detection paths pass/fail as expected,
(b) synthetic net-new PREFIX consumer fails,
(c) is_production reintroduction fails,
(d) baseline shrink path passes,
(e) stale baseline entry fails.
Validate with:
- uv run pytest tests/unit/infrastructure/configuration/test_app_settings.py
- python bin/check_prefix_command_namespace.py --self-test
- make check-prefix-guardrail
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented revised local-only scope for TASK-1.3.

Changes delivered:
- app/infrastructure/configuration/app.py: PREFIX documented as legacy Slack command namespace only, no environment meaning; retirement path via SLACK__COMMAND_PREFIX (TASK-45) with decision-record references.
- app/bin/check_prefix_command_namespace.py: AST guardrail implementation with Violation dataclass, tree scanner, stale-baseline ratchet check, and built-in --self-test matrix.
- app/bin/baselines/prefix_readers.txt: seeded baseline of current allowed PREFIX readers; ratchet-down comments included.
- app/Makefile: added check-prefix-guardrail local target.

Verification evidence:
- uv run pytest tests/unit/infrastructure/configuration/test_app_settings.py -q
  Result: 14 passed.
- python bin/check_prefix_command_namespace.py --self-test
  Result: 6 passed, 0 failed.
- make check-prefix-guardrail
  Result: clean tree, exit 0.

Scope decisions:
- Kept guardrail local-first and temporary (no mandatory GitHub Actions wiring) per revised single-maintainer scope.
- No app/modules/** edits and no COMMAND_PREFIX introduction in this task; those remain under TASK-45.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Revised TASK-1.3 to a local-only guardrail scope and implemented all revised acceptance criteria: PREFIX field documentation, AST-based guardrail + baseline ratchet, local Makefile target, and built-in regression self-tests with passing verification.
<!-- SECTION:FINAL_SUMMARY:END -->
