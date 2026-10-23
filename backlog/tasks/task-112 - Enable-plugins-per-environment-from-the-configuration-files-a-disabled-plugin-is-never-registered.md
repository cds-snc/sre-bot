---
id: TASK-112
title: >-
  Enable plugins per environment from the configuration files; a disabled plugin
  is never registered
status: To Do
assignee: []
created_date: 2026-09-24 19:59
updated_date: '2026-10-23T19:42:00Z'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-110
  - TASK-111.3
  - TASK-111.17
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - decisions/lifecycle.md
  - https://github.com/cds-snc/sre-bot/issues/1655
priority: medium
type: feature
ordinal: 254000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md and configuration.md: every entry point has an enablement key in the base configuration file, and an environment file may override it. The host skips a disabled plugin before registering it (pm.set_blocked, or by filtering the entry-point list). A disabled plugin registers nothing: no routes, no OpenAPI entries, no strategies, no settings reads.

Today which features and jobs run is decided by environment variables and ENVIRONMENT checks in code (for example, scheduled tasks gated on ENVIRONMENT == "production"). This ticket moves plugin switches into the files and deletes the corresponding environment-variable switches and ENVIRONMENT checks for plugins. Runtime flags (OpenFeature with flagd) are out of scope and added only when a feature needs one.

Vendor tenant entries (decisions/configuration.md, workplace-systems.md): a vendor client is available when its slice holds a tenant entry carrying the vendor's real tenant id, validated at boot with no network call. This ticket gives the Slack transport its keys in [slack_transport] beside command_prefix: enabled (replacing SLACK_ENABLED; production.toml and local.toml set it true) and socket_mode (replacing SLACK_SOCKET_MODE; default true, set nowhere). The Slack slice then holds only the client's credentials and tenant entry (TASK-111.9 moves it onto [slack] next), so the tenant entry alone says whether the workspace is configured; there is no <VENDOR>_ENABLED key. The rules that join the two slices run in the host's configuration phase (server/configuration/host_configuration.py), not in either slice: the transport on requires the Slack tenant entry (today derived from SLACK_TEAM_ID) and the bot token; Socket Mode requires the app token; HTTP Events mode requires the signing secret; Socket Mode without the signing secret logs slack_signing_secret_not_set_in_socket_mode at info. Production runs Socket Mode with no signing secret, which must keep booting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every entry point has an enablement key in the base configuration file (boot test fails on a missing key)
- [ ] #2 A plugin disabled in the environment file is never registered: no routes, no OpenAPI entries, no hookimpl calls, no settings reads (boot test)
- [ ] #3 grep finds no environment-variable feature switch or ENVIRONMENT check deciding whether a plugin runs
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #5 Enablement keys in the base configuration are grouped by product area as decisions/product-scope.md names them (incident response, cloud operations, platform access, workplace utilities)
- [x] #6 The SLACK_ENABLED exception is removed from bin/check_settings_key_ownership.py's vendor-enabled rule, and the check passes with an empty allowlist
- [x] #7 The Slack transport's enabled and socket_mode keys are in [slack_transport] (decisions/configuration.md, transport-slack.md); SLACK_ENABLED and SLACK_SOCKET_MODE are no longer read, and switching the transport on without the Slack tenant entry or the app token Socket Mode needs fails boot naming the key
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 (SLACK_TEAM_ID review): tenant entries stay validated at boot with no network call; the Slack entry (team id and optional enterprise id, TASK-157) is verified per inbound request by the runtime guard, and a stamping batch job verifies it with auth.test (decisions/workplace-systems.md rule 3). Moving the entries into the files keeps both ids.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-23T19:22:00Z

---

2026-10-23: size gate tripped (~450-550 prod LOC, ~30 files, three subsystems); split into TASK-112.1 (Slack transport keys, contract, host rules; parent ACs #6, #7, SLACK_* part of #3), TASK-112.2 (plugin keys by area, set_blocked; ACs #1, #2, #5) and TASK-112.3 (ACCESS_*_ENABLED, [scheduler] enabled, guard test; AC #3). This task is the coordinator: each AC is checked as the subtask that verifies it lands. Decisions: plugin keys are [plugins.<area>] tables mapping entry-point name to bool; user_rotations under incident response; the scheduler's run switch is [scheduler] enabled (from TASK-111.13); the transport slice moves to server/slack/ with a SlackTransportInfo contract for the legacy command prefix; the Notify ENVIRONMENT check rides in TASK-111.12. Follow-up gap, not created: running the access plugins locally needs an AWS profile with cross-account permissions and is undocumented.

---
<!-- COMMENTS:END -->
