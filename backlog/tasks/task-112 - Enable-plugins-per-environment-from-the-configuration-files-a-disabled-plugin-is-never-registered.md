---
id: TASK-112
title: >-
  Enable plugins per environment from the configuration files; a disabled plugin
  is never registered
status: To Do
assignee: []
created_date: '2026-09-24 19:59'
updated_date: '2026-10-20 23:27'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-110
  - TASK-111.3
  - TASK-111.9
  - TASK-111.10
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/lifecycle.md
  - 'https://github.com/cds-snc/sre-bot/issues/1655'
priority: medium
type: feature
ordinal: 254000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md and configuration.md: every entry point has an enablement key in the base configuration file, and an environment file may override it. The host skips a disabled plugin before registering it (pm.set_blocked, or by filtering the entry-point list). A disabled plugin registers nothing: no routes, no OpenAPI entries, no strategies, no settings reads.

Today which features and jobs run is decided by environment variables and ENVIRONMENT checks in code (for example, scheduled tasks gated on ENVIRONMENT == "production"). This ticket moves plugin switches into the files and deletes the corresponding environment-variable switches and ENVIRONMENT checks for plugins. Runtime flags (OpenFeature with flagd) are out of scope and added only when a feature needs one.

Vendor tenant entries (decisions/configuration.md, workplace-systems.md): a vendor client is available when its slice holds a tenant entry carrying the vendor's real tenant id, validated at boot with no network call. TASK-111.9 and TASK-111.10 (2026-10-20) already move the Slack and Google tenant entries into the files. This ticket gives the Slack transport its enablement key in the files, replacing the interim SLACK_ENABLED, so the Slack tenant entry alone says whether the workspace is configured. There is no <VENDOR>_ENABLED key.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every entry point has an enablement key in the base configuration file (boot test fails on a missing key)
- [ ] #2 A plugin disabled in the environment file is never registered: no routes, no OpenAPI entries, no hookimpl calls, no settings reads (boot test)
- [ ] #3 grep finds no environment-variable feature switch or ENVIRONMENT check deciding whether a plugin runs
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #5 Enablement keys in the base configuration are grouped by product area as decisions/product-scope.md names them (incident response, cloud operations, platform access, workplace utilities)
- [ ] #6 The SLACK_ENABLED exception is removed from bin/check_settings_key_ownership.py's vendor-enabled rule, and the check passes with an empty allowlist
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (SLACK_TEAM_ID review): tenant entries stay validated at boot with no network call; the Slack entry (team id and optional enterprise id, TASK-157) is verified per inbound request by the runtime guard, and a stamping batch job verifies it with auth.test (decisions/workplace-systems.md rule 3). Moving the entries into the files keeps both ids.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-25 15:00
---
2026-09-25: an enabled feature whose settings slice fails validation is skipped rather than aborting boot (decisions/plugins.md); TASK-126 implements that on top of this ticket. The plugin's configuration table carries only the enablement key: there is no per-plugin boot-failure override.
---
<!-- COMMENTS:END -->
