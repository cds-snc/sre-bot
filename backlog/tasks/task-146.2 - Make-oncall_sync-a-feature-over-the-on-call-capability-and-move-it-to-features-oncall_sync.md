---
id: TASK-146.2
title: >-
  Make oncall_sync a feature over the on-call capability and move it to
  features/oncall_sync
status: To Do
assignee: []
created_date: '2026-10-09 16:44'
labels:
  - oncall
  - capabilities
dependencies:
  - TASK-146.1
parent_task_id: TASK-146
priority: medium
type: task
ordinal: 366000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 2 of TASK-146; supersedes TASK-124.2.

THIS SLICE
- oncall_sync resolves current on-call people through capabilities.oncall.api for every rotation in rotations.json (Opsgenie and self-managed alike); its own Opsgenie adapter and ports.py are deleted; the feature-to-feature import of user_rotations is gone.
- The feature keeps the usergroup projection: adapters/slack.py writes usergroups with the user token (decisions/service-accounts.md), the five-minute job registers through the background-job hookimpl, approved_email_domains filtering stays.
- Move to app/features/oncall_sync/ in the feature-packages shape (entry point features.oncall_sync, enablement key, settings slice values in the TOML files when TASK-111 has landed); providers.py resolves contracts from the registry and imports nothing from infrastructure/ or server/.
- Every importer and mock patch string rewritten; import-linter ignore entries only shrink.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 oncall_sync imports capabilities.oncall.api and no other package; packages.user_rotations and its own Opsgenie adapter are gone
- [ ] #2 features/oncall_sync/ passes the package shape (no ports.py, entrypoints/ not platforms/) and the old packages/ path is deleted
- [ ] #3 The usergroup sync behaviour is unchanged: existing tests pass with the lookup stubbed through the capability's fake
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
