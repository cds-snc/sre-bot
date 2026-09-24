---
id: TASK-124.2
title: Move packages/oncall_sync to app/features/oncall_sync/
status: To Do
assignee: []
created_date: '2026-09-24 20:01'
labels:
  - plugin-architecture
  - features
milestone: m-7
dependencies:
  - TASK-109
  - TASK-110
  - TASK-114
  - TASK-123
  - TASK-25.4
  - TASK-25.6
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-124
priority: medium
type: task
ordinal: 268000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. oncall_sync has a ports.py outside the layout table and builds a slack_sdk WebClient and reads integrations.slack.settings in providers.py. It moves after the rotations capability (TASK-123) removes its feature-to-feature import, after TASK-25.4 gives it the Slack client factory for its adapter, and after TASK-25.6 moves the Opsgenie operations into its adapters.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/<name>/ passes the package-shape check; platforms/ and interactions/ are renamed entrypoints/
- [ ] #2 providers.py resolves contracts from the service registry and imports nothing from infrastructure/ or server/; integrations are imported only from adapters/
- [ ] #3 The entry point targets features.<name> (dotted for subdomains) and has an enablement key; the settings slice's non-secret values live in the TOML files
- [ ] #4 The old packages/ path is deleted; every importer and mock patch string is rewritten; import-linter ignore entries only shrank
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #6 ports.py is folded into layout-table names; no slack_sdk client is built outside adapters/
<!-- AC:END -->
