---
id: TASK-67
title: >-
  Bring register_slack_commands into the new hookspec deprecation lifecycle and
  retire it
status: To Do
assignee: []
created_date: '2026-07-29 17:46'
updated_date: '2026-09-24 20:10'
labels:
  - governance
  - plugins
  - phase-3
milestone: m-3
dependencies:
  - TASK-26.1
references:
  - decisions/hookspec-deprecation.md
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1389'
priority: low
ordinal: 102000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/hookspec-deprecation.md (Accepted, applies: target). app/infrastructure/plugins/specs.py's register_slack_commands hookspec already carries an ad hoc docstring ('DEPRECATED: will be removed in favor of register_slack_listeners for direct Bolt app registration') with no formal marker format, no minimum lifetime, and no removal checklist. Four hookimpls still implement it: app/modules/dev, app/modules/sre, app/packages/access/sync, app/packages/geolocate; app/packages/access/request has a pending/commented-out one.

Steps:
1. Reformat the docstring to the new required marker format: 'DEPRECATED (since m-1, replacement: register_slack_listeners).'
2. Do not remove the hookspec yet - only migrate hookimpls onto register_slack_listeners as their owning tasks land (dev/sre via the modules strangler, access/sync and geolocate can migrate independently since they are already feature packages).
3. Once every current implementer has migrated (repo-wide grep for @hookimpl register_slack_commands returns zero hits) and at least one milestone boundary has passed since m-1, remove the hookspec from specs.py, update plugins.md if it names the spec, and update the boot test (app/tests/unit/infrastructure/plugins/test_plugins_hookspecs.py) to drop it.
4. This task's own single PR should cover step 1 only (the docstring reformat, a documentation-only change with zero behavior impact) if the migrations in step 2 are not yet complete when this task is picked up; steps 3-4 (actual removal) may need to be split into a later follow-up task once all implementers have migrated - decide this at planning time based on how many implementers have migrated by then.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 register_slack_commands's docstring follows the DEPRECATED (since <milestone>, replacement: <name>) marker format, naming the registrar-based Slack registration hookspec defined by TASK-26.1 as the replacement
- [ ] #2 A repo-wide grep for @hookimpl implementers of register_slack_commands is documented in the PR (count of remaining implementers stated explicitly)
- [ ] #3 If zero implementers remain, the hookspec is deleted from the hookspecs module (app/contracts/ after TASK-107) and the boot-test hookspec inventory is updated to match; if implementers remain, the hookspec is left in place with the reformatted marker and removal is filed as an explicit follow-up task
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:10
---
2026-09-24 alignment with decisions/platform-entrypoints.md and plugins.md: the replacement is no longer register_slack_listeners(app: AsyncApp), which hands features the Bolt app. It is the registrar-based Slack hookspec in app/contracts/slack/ from TASK-26.1. Dependency moved from TASK-26 to TASK-26.1.
---
<!-- COMMENTS:END -->
