---
id: TASK-45.6
title: >-
  Teardown: delete AppSettings.PREFIX, aggregator mirror, and lifespan
  diagnostic field
status: To Do
assignee: []
created_date: '2026-07-21 19:13'
updated_date: '2026-07-22 17:13'
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
  - 'https://github.com/cds-snc/sre-bot/issues/1320'
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

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-07-22 14:39
---
Architecture alignment (2026-07-22): per decisions/configuration.md, the god-settings aggregator (app/infrastructure/configuration/settings.py's Settings/get_settings()/settings_map) is being removed by a separate, open PR — not a target this task should assume is stable. Before executing this teardown: (1) check whether app/infrastructure/configuration/settings.py still exists / still contains the PREFIX field and kwargs.setdefault('PREFIX', app.PREFIX) at the cited lines (97, 175) — line numbers may have shifted or the file may already be gone; (2) if the aggregator has already been removed by the other PR, AC #1's 'aggregator mirror... deleted' clause is trivially satisfied — re-verify by grep rather than assuming the cited lines still apply; (3) TASK-1.3's guardrail/baseline check (AC #2) and the app.py PREFIX field deletion are unaffected either way. No change to ACs made here; flagging for whoever picks up this task's plan.
---

author: @copilot
created: 2026-07-22 14:58
---
Alignment (2026-07-22): teardown must not reintroduce or re-reference the dead infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings duplicate (deletion tracked by TASK-24); when updating tests that referenced AppSettings.PREFIX, use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). COMMAND_PREFIX continues to live in infrastructure.slack.settings (TASK-45.1). Transport provider relocation is TASK-26, out of scope here.
---
<!-- COMMENTS:END -->
