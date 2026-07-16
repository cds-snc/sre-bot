---
id: TASK-38
title: Migrate modules/incident to a feature package
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:58'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-36
  - TASK-37
references:
  - decisions/migration.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1292'
priority: medium
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second strangler target (largest user surface; 51 files, plus the incident_helper legacy-list entry). Same recipe as task-37; the webhooks migration (task-37) establishes the pattern to copy.

Steps:
1. Confirm smoke coverage of every incident command/action (task-36 inventory).
2. Build app/packages/incident/ per decisions/feature-packages.md; subdomains only if the feature is genuinely complex (copy the access/ shape then).
3. Slack handlers via register_slack_commands hookspec; parsing via the shared parser; rendering via the shared renderer; locales/ EN+FR per decisions/i18n.md (parity gate from task-21 applies).
4. Cut over, delete app/modules/incident/, smoke green pre/post, command names unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/incident/ matches the layout; handlers pass the five-step review
- [ ] #2 Smoke tests pass pre and post cutover; command names and responses unchanged
- [ ] #3 app/modules/incident/ deleted; legacy list entry removed; baselines never grew
- [ ] #4 EN/FR catalogues complete (parity check green)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke suite green post-cutover
- [ ] #2 PR series references decisions/migration.md
<!-- DOD:END -->
