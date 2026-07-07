---
id: TASK-21
title: Add the EN/FR catalogue parity check to CI
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - toolchain
  - phase-2
  - i18n
milestone: m-2
dependencies: []
references:
  - decisions/i18n.md
priority: medium
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/i18n.md: the bilingualism guarantee is a CI gate, not a runtime fallback. Every user-facing key must exist in both en and fr catalogues.

Steps:
1. Write a small CI script (app/bin/check_i18n_parity.py) that loads every registered feature catalogue under app/packages/**/locales/ and app/infrastructure/i18n/ resources, compares en and fr key sets, and exits nonzero listing missing keys per side.
2. Scope: the new infrastructure/i18n stack only. Legacy app/locales/*.yml (python-i18n) is exempt until decisions/migration.md retires the modules using it - note the exemption in the script.
3. Wire into CI as a blocking step.
4. Fix any parity gaps the first run finds (add the missing translations).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CI fails when a key exists in en but not fr (or vice versa) in any registered catalogue (verified with a draft commit)
- [ ] #2 Current catalogues pass (gaps fixed in this PR)
- [ ] #3 Legacy app/locales/ exemption documented in the script header
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 CI blocking step live
- [ ] #2 PR references decisions/i18n.md
<!-- DOD:END -->
