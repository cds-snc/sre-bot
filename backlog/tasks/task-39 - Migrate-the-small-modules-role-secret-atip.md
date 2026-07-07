---
id: TASK-39
title: 'Migrate the small modules: role, secret, atip'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-36
references:
  - decisions/migration.md
  - decisions/feature-packages.md
priority: medium
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The quick wins per decisions/migration.md order - small modules to cement the pattern. One module per PR series, same recipe as task-37.

Steps per module (role, then secret, then atip):
1. Smoke coverage confirmed (task-36).
2. Feature package per decisions/feature-packages.md (these are likely simple layouts: __init__.py + service.py + interactions/slack.py + locales/).
3. Cut over, remove from _register_legacy_handlers(), delete app/modules/<name>/, smoke green pre/post.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Three feature packages exist matching the layout; three module directories deleted
- [ ] #2 Smoke tests pass pre/post for each module independently
- [ ] #3 Baselines only shrank
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Each module landed as its own reviewable PR series
- [ ] #2 PR series references decisions/migration.md
<!-- DOD:END -->
