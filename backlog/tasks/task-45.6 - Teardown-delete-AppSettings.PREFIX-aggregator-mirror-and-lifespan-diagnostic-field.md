---
id: TASK-45.6
title: >-
  Teardown: delete AppSettings.PREFIX, aggregator mirror, and lifespan
  diagnostic field
status: To Do
assignee: []
created_date: '2026-07-21 19:13'
labels:
  - phase-0
  - security
milestone: m-0
dependencies:
  - TASK-45.2
  - TASK-45.3
  - TASK-45.4
  - TASK-45.5
references:
  - decisions/configuration.md
  - decisions/transport-slack.md
  - decisions/migration.md
parent_task_id: TASK-45
priority: high
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Contract slice — runs only after all module cutovers land. Delete AppSettings.PREFIX (app/infrastructure/configuration/app.py:14), its mirror in app/infrastructure/configuration/settings.py (PREFIX field at line 97 and the kwargs.setdefault('PREFIX', app.PREFIX) at line 175), and the diagnostic PREFIX field in app/server/lifespan.py:71. Empty app/bin/baselines/prefix_readers.txt (down to zero readers). Update any tests referencing AppSettings.PREFIX. TASK-1.3's guardrail must still pass with an empty baseline.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AppSettings.PREFIX and its aggregator mirror and the lifespan diagnostic field are deleted; boot and existing tests pass
- [ ] #2 app/bin/baselines/prefix_readers.txt is empty and the TASK-1.3 guardrail passes
- [ ] #3 grep -rn 'app_settings.PREFIX|get_app_settings().PREFIX|AppSettings().PREFIX' app/ --include=*.py returns no hits
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR references decisions/configuration.md and decisions/transport-slack.md
<!-- DOD:END -->
