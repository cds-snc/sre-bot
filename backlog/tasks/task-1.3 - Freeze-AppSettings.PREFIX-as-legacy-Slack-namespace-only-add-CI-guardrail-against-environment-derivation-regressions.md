---
id: TASK-1.3
title: >-
  Freeze AppSettings.PREFIX as legacy Slack namespace only; add CI guardrail
  against environment-derivation regressions
status: To Do
assignee: []
created_date: '2026-07-21 18:56'
updated_date: '2026-07-21 19:12'
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
Close-out + regression lock for TASK-1, and the ratchet that drives PREFIX retirement (TASK-45). TASK-1.2.3 removed every is_production and PREFIX-derived environment branch (verified: zero is_production hits; PREFIX now read only by app/infrastructure/configuration/app.py [definition], its pre-existing mirror in app/infrastructure/configuration/settings.py, a diagnostic log in app/server/lifespan.py, and the 6 frozen Slack command-namespace readers app/modules/{atip,aws,incident,role,secret,sre}). Scope: (1) annotate AppSettings.PREFIX (field description) as legacy Slack command-namespace ONLY, no environment meaning, being retired per-module via SLACK__COMMAND_PREFIX (TASK-45), deleted when the last module cuts over; cross-reference decisions/configuration.md and decisions/transport-slack.md — doc-only, additive. (2) Add a CI guardrail script under app/bin/ (co-located with app/bin/baselines/, wired into app/Makefile + .github/workflows/ci_code.yml) that fails on any is_production, any PREFIX environment-derivation form (PREFIX ==/!=/bool(PREFIX)), and any NET-NEW AppSettings.PREFIX reader not in a checked-in baseline. The baseline is the current legacy-reader set and only ratchets DOWN — TASK-45's per-module cutovers each delete one baseline entry until it is empty and PREFIX is removed. (3) A regression test proving reject-new-consumer, reject-is_production, accept-current-tree, and accept-baseline-shrink. Respects the migration.md carve-out: this task does NOT edit app/modules/** and does NOT introduce COMMAND_PREFIX (that is TASK-45); it only makes the retirement measurable and regression-proof.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR references decisions/configuration.md and decisions/transport-slack.md
- [ ] #2 CI guardrail step is green on the PR that introduces it
<!-- DOD:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/configuration/app.py's PREFIX field carries a description/docstring stating: legacy Slack command-namespace ONLY, no environment meaning, being retired per-module via SLACK__COMMAND_PREFIX (TASK-45) and deleted when the last module cuts over; cross-references decisions/configuration.md and decisions/transport-slack.md; no behavior change (existing tests pass unmodified)
- [ ] #2 A committed guardrail under app/bin/ compares the tree against a checked-in baseline of accepted AppSettings.PREFIX readers (the app.py definition plus the documented legacy readers) and fails on: any is_production identifier; any PREFIX environment-derivation form (PREFIX ==, PREFIX !=, bool(PREFIX)); or any NET-NEW PREFIX reader absent from the baseline. It exits 0 against the current tree
- [ ] #3 The baseline only ratchets DOWN: a reader removed from the tree must be removed from the baseline (script self-checks for stale entries), and no PR may add a baseline entry; a net-new reader fails CI naming the offending file:line
- [ ] #4 The guardrail runs in CI on every PR touching app/** via a new app/Makefile target invoked from .github/workflows/ci_code.yml and fails the workflow on a violation
- [ ] #5 A regression test in app/tests/unit/ asserts: (a) the current tree passes; (b) a synthetic new non-baseline PREFIX consumer fails with a message naming the file; (c) is_production reintroduction fails; (d) removing a now-migrated reader from both tree and baseline still passes (proves the ratchet direction)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Verified pre-state (2026-07-21): grep -rn PREFIX/is_production app/ --include=*.py. is_production: zero hits. AppSettings.PREFIX readers (production): app/infrastructure/configuration/app.py:14 (definition); app/infrastructure/configuration/settings.py:97,175 (legacy aggregator mirror, pre-existing); app/server/lifespan.py:71 (diagnostic startup log, pre-existing); app/modules/{atip/atip.py:37,428, aws/aws.py:63, incident/incident.py:25, role/role.py:19, secret/secret.py:15, sre/sre.py:23} (frozen command-namespace reads). NOTE: atip.py:428 is a SECOND use (channel-name prefix, not command namespace) — it still reads AppSettings.PREFIX and is a baseline entry until TASK-45's atip cutover moves it to ENVIRONMENT/atip-setting.

Step 1 — Doc annotation (AC #1). app/infrastructure/configuration/app.py: add Field(description=...) on PREFIX (line 14): legacy Slack command-namespace ONLY; no environment meaning; being retired per-module via SLACK__COMMAND_PREFIX (TASK-45); deleted when the last module cuts over; refs decisions/configuration.md + decisions/transport-slack.md. No type/default/behavior change. Verify existing test_app_settings.py passes; black/mypy clean.

Step 2 — Guardrail script + baseline (AC #2, #3). New app/bin/check_prefix_command_namespace.py exposing find_violations(root, baseline) -> list[Violation] (frozen dataclass: file, line, reason) plus a __main__ that exits 1 printing violations. Uses ast (not naive regex) over app/**/*.py excluding app/tests/**. Baseline: new app/bin/baselines/prefix_readers.txt listing each accepted (file, symbol-kind) reader — seeded with the readers enumerated above. Rules: (a) is_production identifier anywhere in app/ (incl. tests) -> violation; (b) any Name/Attribute 'PREFIX' in a file NOT in the baseline -> NET-NEW violation; (c) inside any file, a Compare of the form PREFIX ==/!= -> violation (no legitimate namespace read needs equality); bare truthy use (bool(PREFIX)/if PREFIX/ternary) is NOT flagged (atip.py's ternary is legitimate namespace building — a baseline reader); (d) self-check: any baseline entry whose file no longer reads PREFIX -> 'stale baseline entry, remove it' violation (enforces ratchet-down + keeps the baseline honest). Follows the app/bin/ + app/bin/baselines/ convention TASK-19 will also use. Verify: run against current tree -> exit 0.

Step 3 — Wire into tooling (AC #4). app/Makefile: add target check-prefix-guardrail (uv run python bin/check_prefix_command_namespace.py) near lint-ci/fmt-ci. .github/workflows/ci_code.yml: add step 'Check PREFIX command-namespace guardrail' (working-directory ./app, run: make check-prefix-guardrail) after Lint, before Format. Distinct step for clear failure attribution.

Step 4 — Regression test (AC #5). New app/tests/unit/bin/test_check_prefix_command_namespace.py (+ __init__.py). Matrix: accepts_current_tree (real tree, []); rejects_new_non_baseline_consumer (tmp_path fixture with packages/widgets/service.py reading get_app_settings().PREFIX -> one violation naming it); rejects_is_production_reintroduction; rejects_prefix_equality_even_in_baseline_file; accepts_truthy_ternary_in_baseline_file (atip pattern -> no violation); accepts_baseline_shrink (remove a reader from both fixture tree and baseline -> pass); rejects_stale_baseline_entry (baseline lists a file that no longer reads PREFIX -> violation). Verify: uv run pytest tests/unit/bin green.

Relationship to TASK-45: this baseline file IS the retirement tracker. Each TASK-45 per-module cutover PR deletes that module's baseline entry in the same PR; when prefix_readers.txt reaches only the app.py definition + the settings.py mirror + lifespan.py log, the final TASK-45 teardown removes those and the field. Rule (d) guarantees the baseline can't silently retain migrated entries.

Assumptions/doubts: (1) settings.py mirror + lifespan.py log are seeded as baseline entries (tolerated pre-existing reads); TASK-45 teardown removes them with the field. (2) app/modules/dev/__init__.py stale docstring left untouched (freeze); optional doc fix is its own trivial change. (3) Rule (c)/(d) scoping locked by Step 4 tests.

Blast radius: app.py (doc-only), new app/bin/ script + baseline (no prod import), app/Makefile (+target), ci_code.yml (+step), new test package. No prod import-graph change; no app/modules/** edit; no manifest change. Rollback: revert the PR — CI-only tooling, no runtime coupling.
<!-- SECTION:PLAN:END -->
