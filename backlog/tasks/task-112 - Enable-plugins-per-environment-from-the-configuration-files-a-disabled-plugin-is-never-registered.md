---
id: TASK-112
title: >-
  Enable plugins per environment from the configuration files; a disabled plugin
  is never registered
status: To Do
assignee: []
created_date: '2026-09-24 19:59'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-110
  - TASK-111
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/lifecycle.md
priority: medium
type: feature
ordinal: 254000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md and configuration.md: every entry point has an enablement key in the base configuration file, and an environment file may override it. The host skips a disabled plugin before registering it (pm.set_blocked, or by filtering the entry-point list). A disabled plugin registers nothing: no routes, no OpenAPI entries, no strategies, no settings reads.

Today which features and jobs run is decided by environment variables and ENVIRONMENT checks in code (for example, scheduled tasks gated on ENVIRONMENT == "production"). This ticket moves plugin switches into the files and deletes the corresponding environment-variable switches and ENVIRONMENT checks for plugins. Runtime flags (OpenFeature with flagd) are out of scope and added only when a feature needs one.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every entry point has an enablement key in the base configuration file (boot test fails on a missing key)
- [ ] #2 A plugin disabled in the environment file is never registered: no routes, no OpenAPI entries, no hookimpl calls, no settings reads (boot test)
- [ ] #3 grep finds no environment-variable feature switch or ENVIRONMENT check deciding whether a plugin runs
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
