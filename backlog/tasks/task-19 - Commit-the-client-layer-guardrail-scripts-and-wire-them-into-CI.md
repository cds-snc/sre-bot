---
id: TASK-19
title: Commit the client-layer guardrail scripts and wire them into CI
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 21:12'
labels:
  - toolchain
  - phase-2
  - clients
milestone: m-2
dependencies: []
references:
  - decisions/migration.md
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1273'
priority: high
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The two uncommitted scripts app/bin/check_deprecated_infra_client_imports.py (freeze baseline over deprecated infrastructure/clients imports) and app/bin/generate_client_usage_matrix.sh (usage report), with app/bin/baselines/, are exactly the right migration tooling per decisions/toolchain.md - commit and enforce them.

Steps:
1. Commit both scripts and the baselines directory.
2. Add a CI step running the freeze check: fails on any NET-NEW deprecated import (baseline only ratchets down, per decisions/migration.md coexistence rule 3).
3. Make the usage-matrix script runnable via a Makefile target (make client-usage-matrix) for progress tracking during Phase 3.
4. Retirement condition (do not implement now, note in the script header): both are deleted when their baselines are empty after Phase 3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Scripts and baselines committed; CI fails on a net-new deprecated-client import (verified with a draft commit, then reverted)
- [ ] #2 Baseline shrinkage does not fail CI; growth does
- [ ] #3 make client-usage-matrix produces the report
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 CI blocking step live
- [ ] #2 PR references decisions/migration.md coexistence rules
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 21:12
---
Planning note from TASK-22 decomposition: as of 2026-07-29, app/bin/check_deprecated_infra_client_imports.py and app/bin/baselines/ do NOT yet exist in the repo — only app/bin/generate_client_usage_matrix.sh (exposed via 'make audit-client-usage-matrix') is committed. TASK-22's Step 1/AC and its subtasks assume the freeze-check + baseline from this task. If TASK-19 lands before the TASK-22 sprint, the baseline ratchet enforces monotonic shrinkage per-slice; if it does not, TASK-22.5's baseline-empty step is a no-op and the deletion is guarded only by the usage-matrix + import-linter (TASK-18). No blocker either way, but sequencing TASK-19 ahead of the TASK-22 sprint is preferable.
---
<!-- COMMENTS:END -->
