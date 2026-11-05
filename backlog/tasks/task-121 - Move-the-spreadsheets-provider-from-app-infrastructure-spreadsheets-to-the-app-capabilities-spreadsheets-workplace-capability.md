---
id: TASK-121
title: >-
  Delete infrastructure/spreadsheets/ once the incident list projection and AWS
  spending own their sheet ports
status: To Do
assignee: []
created_date: 2026-09-24 20:00
updated_date: '2026-11-05T00:14:00Z'
labels:
  - plugin-architecture
  - capabilities
  - workplace-systems
milestone: m-7
dependencies:
  - TASK-145.12
  - TASK-88
  - TASK-169
references:
  - decisions/workplace-systems.md
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - decisions/cloud-portability.md
  - https://github.com/cds-snc/sre-bot/issues/1664
priority: medium
type: task
ordinal: 263000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Re-scoped by the TASK-169 ruling, 2026-11-05 (human) (decisions/workplace-systems.md, 2026-10-26 and 2026-11-05). Sheets is a vendor product API, not a workplace capability; spreadsheets become projections (workplace-systems.md rule 5). Its two consumers own their ports: the incident list projection (TASK-145.12, AC added) and AWS spending (TASK-88, AC added), each adapter calling integrations/google_workspace/ directly. Once both have landed, app/infrastructure/spreadsheets/ has no consumer and is deleted with its fake and its fake-coverage line. Delete-only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No code imports app/infrastructure/spreadsheets; app/infrastructure/spreadsheets/ is deleted with no re-export, including mock patch strings
- [ ] #2 The SpreadsheetProvider line leaves app/bin/baselines/fake_coverage.txt and make check-fake-coverage passes
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-26T19:32:00Z

---

2026-10-26 (human approved): scope under review by TASK-169. decisions/workplace-systems.md now says a vendor product API is not a capability by itself; this task is expected to be re-scoped from a move into app/capabilities/ to purpose-named ports owned by its consumers over integrations/google_workspace/. Do not plan it before TASK-169 lands.

---
<!-- COMMENTS:END -->
