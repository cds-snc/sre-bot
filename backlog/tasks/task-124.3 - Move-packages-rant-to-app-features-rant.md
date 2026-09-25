---
id: TASK-124.3
title: Move packages/rant to app/features/rant/
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
  - TASK-25.4
  - TASK-26.1
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-124
priority: medium
type: task
ordinal: 269000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. rant imports slack_sdk.WebClient in platforms/slack.py, which transport-slack.md tolerates only until the client factory (TASK-25.4) and the Slack handler contract (TASK-26.1) exist.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/<name>/ passes the package-shape check; platforms/ and interactions/ are renamed entrypoints/
- [ ] #2 providers.py resolves contracts from the service registry and imports nothing from infrastructure/ or server/; integrations are imported only from adapters/
- [ ] #3 The entry point targets features.<name> (dotted for subdomains) and has an enablement key; the settings slice's non-secret values live in the TOML files
- [ ] #4 The old packages/ path is deleted; every importer and mock patch string is rewritten; import-linter ignore entries only shrank
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
