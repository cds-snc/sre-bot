---
id: TASK-175
title: >-
  Plugins state their Slack, Google and Opsgenie requirements through the
  configured-systems read; ADR rule on how CI satisfies them
status: To Do
assignee: []
created_date: '2026-10-29T00:46:00Z'
labels:
  - plugins
dependencies:
  - TASK-172
  - TASK-145.5.9
priority: medium
ordinal: 459000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-172 (human, 2026-10-29: create). TASK-172 adds the register_requirements hookspec and states one requirement (incident.scribe requires [openai.tenant]). The Slack, Google Workspace and Opsgenie requirements of incident.scribe, oncall_sync, rant and user_rotations are not stated yet: decisions/plugins.md Tolerated. Each plugin resolves them through the configured-systems read (TASK-145.5.9) inside register_requirements. Needs first an ADR rule in decisions/plugins.md on how CI satisfies a requirement (a fake tenant in ci.toml, or the plugin switched off in ci.toml with a guard test as TASK-172 does for scribe); research current practice before ruling.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/plugins.md records how CI satisfies a plugin's vendor requirement, with sources, and drops the Tolerated entry once this task lands
- [ ] #2 incident.scribe, oncall_sync, rant and user_rotations each state their Slack, Google Workspace or Opsgenie requirement through register_requirements, resolved through the configured-systems read
- [ ] #3 An enabled plugin whose stated vendor is not configured aborts boot with one CRITICAL plugin_boot_failed event naming the requirement; tests cover each plugin's success and failure
- [ ] #4 ci.toml and local.toml boot under the rule the ADR sets; development without a vendor (local.toml leaves it unconfigured) still boots
<!-- AC:END -->
