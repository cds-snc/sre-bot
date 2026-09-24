---
id: TASK-123
title: >-
  Make user rotations the app/capabilities/rotations/ capability and remove
  oncall_sync's feature-to-feature import
status: To Do
assignee: []
created_date: '2026-09-24 20:00'
labels:
  - plugin-architecture
  - capabilities
  - rotations
milestone: m-7
dependencies:
  - TASK-106
  - TASK-109
  - TASK-110
  - TASK-114
references:
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
priority: medium
type: task
ordinal: 265000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human decision 2026-09-24: user rotations become a capability. decisions/plugin-architecture.md: features never import each other, and a need two features share becomes a capability when it passes the three tests.

Verified 2026-09-24: packages/oncall_sync imports packages.user_rotations in three places (providers.py get_user_rotations_service, __init__.py get_rotations, ports.py CurrentUserRotation), a live violation of "features never import each other". Rotations qualify as a capability:
1. a feature needs it now (oncall_sync);
2. it carries organization policy across external systems (Opsgenie schedules, Slack user groups);
3. its vocabulary (rotation, current on-call member) is feature-free.

Scope:
- move packages/user_rotations to app/capabilities/rotations/ with api.py (the Protocol, CurrentUserRotation and the other domain types, the provider function), a README naming oncall_sync as consumer and stating the classification, and an in-memory fake;
- keep its Slack entry points, renamed from platforms/ to entrypoints/;
- register it through its entry point and enablement key;
- repoint oncall_sync to api.py only;
- delete packages/user_rotations with no re-export.
Behaviour-preserving.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/rotations/ matches the capability layout, and its README states the classification and names oncall_sync as a consumer
- [ ] #2 packages/oncall_sync imports only app/capabilities/rotations/api.py; import-linter shows no feature-to-feature import and no new ignore entry
- [ ] #3 An in-memory fake of the rotations Protocol lives in the package and is exercised by tests
- [ ] #4 packages/user_rotations is deleted with no re-export; its Slack command behaviour is unchanged (tests)
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
