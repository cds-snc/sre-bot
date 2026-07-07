---
id: TASK-15
title: Adopt ruff as sole formatter and linter; remove black and standalone bandit
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies:
  - TASK-13
references:
  - decisions/toolchain.md
priority: medium
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Format & lint). Today black formats, ruff lints only E,F,W (no import sorting anywhere), and bandit runs as a separate unconfigured workflow.

Steps:
1. In app/pyproject.toml set ruff as formatter (ruff format) and expand lint rule families to E,F,W,I,B,UP,C4,SIM,S. Line length 100-130 to match current code (pick one, apply).
2. Remove black from dependencies and Makefile; replace format targets with ruff format.
3. Remove the standalone bandit workflow; S rules cover it with one suppression syntax.
4. Run ruff format + ruff check --fix across the tree in a dedicated commit (mechanical churn isolated from logic changes).
5. Fix or explicitly noqa (with justification) remaining violations, notably the new I (import order) and S (security) families.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ruff format --check and ruff check pass in CI over the whole tree
- [ ] #2 black absent from all dependency groups and Makefile targets; bandit workflow deleted
- [ ] #3 Rule families E,F,W,I,B,UP,C4,SIM,S enabled in pyproject
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Reformat commit separated from any logic change
- [ ] #2 Tests pass; PR references decisions/toolchain.md
<!-- DOD:END -->
