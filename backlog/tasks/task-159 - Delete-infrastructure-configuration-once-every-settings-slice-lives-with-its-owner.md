---
id: TASK-159
title: >-
  Delete infrastructure/configuration/ once every settings slice lives with its
  owner
status: To Do
assignee: []
created_date: 2026-10-20 23:28
updated_date: '2026-10-23T17:31:00Z'
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
After TASK-111, infrastructure/configuration/ holds only the feature slices features/sre_ops.py and features/aws_ops.py (TASK-111.15.1 deletes features/incident.py), the FeatureSettings base they inherit (base.py), the uncalled docs_generator.py and the package __init__.py. The host slices are in server/configuration/ behind the contracts HostInfo (TASK-111.7), RetrySettings moves to infrastructure/resilience/retry/ and InfrastructureSettings is deleted (TASK-111.13), and atip and groups are deleted (TASK-111.14). The three feature slices move with their features: incident with TASK-145.13, sre_ops with TASK-40 (server/configuration/host_configuration.py and server/lifespan.py read it today), aws_ops with TASK-88. This task deletes what is left, FeatureSettings and docs_generator.py included, the package, and the tolerated-list item in decisions/configuration.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/configuration/ no longer exists and nothing imports it
- [ ] #2 decisions/configuration.md no longer tolerates feature slices in infrastructure/configuration/features/
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
