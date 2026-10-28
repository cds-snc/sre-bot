---
id: TASK-159
title: >-
  Delete infrastructure/configuration/ once every settings slice lives with its
  owner
status: To Do
assignee: []
created_date: 2026-10-20 23:28
updated_date: '2026-10-28T17:05:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111
  - TASK-145.13
  - TASK-40
  - TASK-88
references:
  - decisions/configuration.md
  - decisions/plugin-architecture.md
  - https://github.com/cds-snc/sre-bot/issues/1760
type: chore
ordinal: 423000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After TASK-111, infrastructure/configuration/ holds only the feature slices features/sre_ops.py and features/aws_ops.py (ConfigurationSlice subclasses on [sre_ops] and [cloud_operations] since TASK-111.14; TASK-111.15.1 moves features/incident.py into the incident response slice), and the package __init__.py (TASK-111.14 deleted the FeatureSettings base in base.py and the uncalled docs_generator.py). The host slices are in server/configuration/ behind the contracts HostInfo (TASK-111.7), RetrySettings moves to infrastructure/resilience/retry/ and InfrastructureSettings is deleted (TASK-111.13), and atip and groups are deleted (TASK-111.14). The feature slices move with their features, each move standardising its keys: incident with TASK-111.15.1, sre_ops with TASK-40 (server/configuration/host_configuration.py and server/lifespan.py read it today), aws_ops with TASK-88 (which deletes aws_admin_groups with modules/permissions). This task deletes what is left, the package, and the tolerated-list item in decisions/configuration.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/configuration/ no longer exists and nothing imports it
- [ ] #2 decisions/configuration.md no longer tolerates feature slices in infrastructure/configuration/features/
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
