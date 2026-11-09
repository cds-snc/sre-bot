---
id: TASK-114.5
title: >-
  app/bin guards read shared definitions: package roots and names from the
  layout manifest, platform env names from one place
status: To Do
assignee: []
created_date: '2026-11-09T15:41:00Z'
labels:
  - tooling
milestone: m-3
dependencies:
  - TASK-114.3
references:
  - decisions/feature-packages.md
  - decisions/testing.md
  - decisions/configuration.md
parent_task_id: TASK-114
priority: low
ordinal: 497000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of the TASK-114.3 re-plan (approved 2026-11-09). Remove the remaining duplicated rule data in app/bin (survey 2026-11-09). From the layout manifest (TASK-114.3): package_toml.py's CAPABILITIES/CORE/COMMON names (:30-32), check_test_seams.py's features/capabilities roots (STRICT_ZONES :63, GUARDED_ROOTS :68), check_fake_coverage.py's api.py and adapters names (:47-48). Env names (human, 2026-11-09: dedup kept in current tasks): audit_env_names.py RUNTIME (:47-60) repeats check_settings_key_ownership.py PLATFORM_NAMES (:80); RUNTIME derives from it; whether RUNTIME_PREFIXES and SDK_NAMESPACE (:83) can share one definition is settled at plan with a classification test (merging must not widen what the audit treats as runtime). Off the incident critical path; side row. Tooling only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 package_toml.py, check_test_seams.py and check_fake_coverage.py take their package roots and layout names from the manifest loader; their existing tests pass unchanged in assertions
- [ ] #2 audit_env_names.py's runtime names derive from check_settings_key_ownership.PLATFORM_NAMES (no repeated literal); audit classification tests pass unchanged; the prefix question is decided in the plan
- [ ] #3 rg finds no second literal definition of the features/capabilities roots or the layout file names under app/bin outside the manifest and its loader
- [ ] #4 ruff, targeted bin tests, then mypy and pytest tests --ignore=tests/smoke once each, make check-test-seams, check-fake-coverage, check-settings-key-ownership and check-package-shape pass, with output in notes
<!-- AC:END -->
