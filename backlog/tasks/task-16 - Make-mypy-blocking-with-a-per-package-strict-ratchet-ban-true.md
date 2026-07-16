---
id: TASK-16
title: Make mypy blocking with a per-package strict ratchet; ban || true
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies:
  - TASK-13
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1270'
priority: high
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Types, CI gates). Today app/Makefile lint-ci runs mypy ... || true (soft-fail) and disallow_untyped_defs=false globally - the exact antipattern the old quality record named while CI ran it.

Steps:
1. Remove || true from app/Makefile (and any workflow) - every quality command exits nonzero on failure.
2. Global mypy baseline: check_untyped_defs = true (loose but honest).
3. Per-package strict overrides for packages/ and infrastructure/ ([[tool.mypy.overrides]] with strict flags). Fix resulting errors or add targeted per-module exemptions INSIDE the strict list with a TODO - the strict list only grows.
4. Document the ratchet rule in pyproject comments: new packages enter the strict list at creation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep -rn "|| true" app/Makefile .github/ returns zero hits
- [ ] #2 mypy failures fail CI (verified by a deliberate error in a draft commit, then reverted)
- [ ] #3 packages/ and infrastructure/ are under strict overrides and pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 CI green with mypy blocking
- [ ] #2 PR references decisions/toolchain.md
<!-- DOD:END -->
