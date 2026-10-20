---
id: TASK-124.4
title: Move packages/talent to app/features/talent/
status: To Do
assignee: []
created_date: '2026-09-24 20:01'
updated_date: '2026-10-20 23:28'
labels:
  - plugin-architecture
  - features
milestone: m-7
dependencies:
  - TASK-109
  - TASK-110
  - TASK-114
  - TASK-120
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - 'https://github.com/cds-snc/sre-bot/issues/1669'
parent_task_id: TASK-124
priority: medium
type: task
ordinal: 270000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Child of TASK-124. talent was created under migration.md rule 5 as the destination of role logic leaving modules/role. It moves before the role surface is rebuilt into it (TASK-39), so the rebuild lands in the final path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/<name>/ passes the package-shape check; platforms/ and interactions/ are renamed entrypoints/
- [ ] #2 providers.py resolves contracts from the service registry and imports nothing from infrastructure/ or server/; integrations are imported only from adapters/
- [ ] #3 The entry point targets features.<name> (dotted for subdomains) and has an enablement key; the settings slice's non-secret values live in the TOML files
- [ ] #4 The old packages/ path is deleted; every importer and mock patch string is rewritten; import-linter ignore entries only shrank
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #6 Its settings slice follows decisions/configuration.md: lower snake_case fields and TOML keys, case_sensitive=False, extra=forbid, the <SLICE>__ env prefix with no per-field alias, and any remaining secret published as an SSM SecureString in the task definition (as TASK-111.4 does)
<!-- AC:END -->
