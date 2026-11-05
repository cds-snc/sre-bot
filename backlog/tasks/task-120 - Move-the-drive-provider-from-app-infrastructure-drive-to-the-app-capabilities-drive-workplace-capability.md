---
id: TASK-120
title: >-
  Dissolve infrastructure/drive/: incident and talent Drive calls in their own
  adapters over integrations/google_workspace/
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
  - TASK-145.6
  - TASK-169
references:
  - decisions/workplace-systems.md
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - decisions/cloud-portability.md
  - https://github.com/cds-snc/sre-bot/issues/1663
priority: medium
type: task
ordinal: 262000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Re-scoped by the TASK-169 ruling, 2026-11-05 (human) (decisions/workplace-systems.md, 2026-10-26 and 2026-11-05). Drive is a vendor product API, not a workplace capability: no second suite is planned for files, so a neutral drive port buys nothing (Hohpe, cited in the ADR). Each consumer owns a purpose-named port, and its adapter calls integrations/google_workspace/ directly, the only feature files that may import integrations/ (decisions/outbound-clients.md).

Consumers of app/infrastructure/drive/ today:
- incident: features/incident/drive (list folder files, list child folders, create folder, create document from template, find document by channel name, appProperties metadata), absorbed into the incident core's Google Docs adapter by TASK-145.6;
- talent: packages/talent/adapters/google_drive.py (create role folder, copy template into it), through get_drive_provider().

Scope: after TASK-145.6, the talent adapter calls the gateway's Drive factory directly; any remaining incident use moves into the core adapter; app/infrastructure/drive/ is deleted with no re-export, its fake and its DriveProvider fake-coverage line. Behaviour-preserving (migration.md rule 6). No capability, entry point or enablement key is created.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The talent role-folder adapter calls integrations/google_workspace directly and keeps its talent-owned port; its tests use the talent fake
- [ ] #2 No incident code uses app/infrastructure/drive; the incident core adapter holds its Drive calls (TASK-145.6)
- [ ] #3 app/infrastructure/drive/ is deleted with no re-export; grep finds no import of the old path, including mock patch strings; the DriveProvider line leaves app/bin/baselines/fake_coverage.txt and make check-fake-coverage passes
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-26T19:32:00Z

---

2026-10-26 (human approved): scope under review by TASK-169. decisions/workplace-systems.md now says a vendor product API is not a capability by itself; this task is expected to be re-scoped from a move into app/capabilities/ to purpose-named ports owned by its consumers over integrations/google_workspace/. Do not plan it before TASK-169 lands.

---
<!-- COMMENTS:END -->
