---
id: TASK-112.3
title: >-
  Delete the remaining plugin switches: ACCESS_*_ENABLED and the production-only
  scheduled-jobs gate; [scheduler] enabled
status: To Do
assignee: []
created_date: '2026-10-23T19:21:00Z'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-112.2
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/reliability.md
parent_task_id: TASK-112
priority: medium
type: feature
ordinal: 441000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-112. The access plugins' in-code switches go: AccessSyncSettings.enabled (ACCESS_SYNC_ENABLED), AccessRequestsSettings.enabled (ACCESS_REQUESTS_ENABLED) and AccessCatalogSettings.enabled (ACCESS_CATALOG_ENABLED) and every 'if not settings.enabled' guard; the [plugins.platform_access] keys from TASK-112.2 decide instead (false in base and production, as today). The requests fallback-slug requirement stays in the access slice, which is validated only when the plugin is enabled (decisions/configuration.md). reconciliation_enabled is a job sub-switch and stays. The scheduler is a host capability composed like a transport (decisions/reliability.md), so it gets a run switch the same way: SchedulerSettings (jobs/settings.py) becomes a ConfigurationSlice with a [scheduler] table holding enabled (false in base, true in production) and the default lease TTL, taken out of TASK-111.13's scope, and server/lifespan.py's ENVIRONMENT == production check reads it. Scheduled jobs still start only after the Slack app initialised (legacy pull-hub, TASK-64 and TASK-65). Ride-along: the _is_test_environment() (sys.modules, prohibited by decisions/configuration.md) guard on the scheduler start is redundant once ci.toml leaves the scheduler off and is removed; its guard on the Slack start stays until the transport test fixtures are audited. A guard test fails when an environment-variable switch or an ENVIRONMENT comparison decides whether a plugin or the scheduler runs (server, packages, features; legacy modules/ excluded). decisions/reliability.md records the [scheduler] enabled key.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ACCESS_SYNC_ENABLED, ACCESS_REQUESTS_ENABLED and ACCESS_CATALOG_ENABLED are no longer read; a disabled access plugin has no routes and an enabled one works without them (tests)
- [ ] #2 [scheduler] enabled decides whether scheduled jobs start (false in base, true in production); server/lifespan.py has no ENVIRONMENT comparison; production still starts its scheduled jobs (test pins production.toml)
- [ ] #3 A guard test fails on an environment-variable switch or an ENVIRONMENT comparison deciding whether a plugin or the scheduler runs in server/, packages/ or features/
- [ ] #4 decisions/reliability.md records the scheduler run switch; TASK-111.13 no longer lists SchedulerSettings
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->
