---
id: TASK-124.6
title: Move packages/geolocate to app/features/geolocate/
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
  - TASK-118
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-124
priority: medium
type: task
ordinal: 272000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. geolocate puts Slack handlers in platforms/ and has a routes.py; both move into entrypoints/ (slack.py, http.py). It waits for the translator contract (TASK-118) and for the active TASK-25.5 (Retire MaxMindClient), so its MaxMind adapter already owns classification.

TASK-25.5 is not in this task's dependency list only because its ID collides with an archived TASK-25.5 (Delete dead AWSShield), which makes the CLI reject --dep TASK-25.5. Add it once the collision is resolved.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/<name>/ passes the package-shape check; platforms/ and interactions/ are renamed entrypoints/
- [ ] #2 providers.py resolves contracts from the service registry and imports nothing from infrastructure/ or server/; integrations are imported only from adapters/
- [ ] #3 The entry point targets features.<name> (dotted for subdomains) and has an enablement key; the settings slice's non-secret values live in the TOML files
- [ ] #4 The old packages/ path is deleted; every importer and mock patch string is rewritten; import-linter ignore entries only shrank
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
