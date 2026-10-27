---
id: TASK-172
title: >-
  Abort boot when an enabled plugin's settings fail validation or a dependency
  it requires is not configured; CI switches off the plugins that require a
  vendor
status: To Do
assignee: []
created_date: '2026-10-27T18:10:00Z'
labels:
  - plugin-architecture
  - plugins
  - configuration
milestone: m-7
dependencies:
  - TASK-111.11.2
references:
  - decisions/plugins.md
  - decisions/lifecycle.md
priority: medium
ordinal: 453000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md and lifecycle.md (2026-10-27): an enabled plugin states that it must work in this environment, so every boot failure aborts, in every layer: an import error or a raising hookimpl, a settings slice that fails validation, a vendor slice that fails validation, and a vendor or capability the plugin requires that is not configured. A plugin is switched off with its enablement key, never skipped. Runtime drift (credential checks, TASK-126) never aborts.

TODAY: an invalid feature slice already aborts boot (lifecycle.md Migration listed it as a tolerance of the old skip target; that item is gone). No plugin states a requirement: a plugin enabled without its vendor boots and fails at use. base.toml enables incident.comms, incident.scribe, oncall_sync, user_rotations, geolocate and rant; ci.toml configures no vendor tenant, so once requirements are stated the CI boot fails unless ci.toml switches those plugins off.

SCOPE:
- contracts/: one typed error for a required dependency that is not configured, carrying the configuration key; the host logs one CRITICAL plugin_boot_failed event (plugin, phase, error type, key; no secrets) and aborts before yield.
- Each enabled plugin resolves what it requires while it registers (configured-systems read, workplace-systems.md rule 3) and raises the error when it is absent. Re-grep each plugin's vendor reads to list them. incident.scribe requires the OpenAI tenant ([openai.tenant], TASK-111.11.2); incident.comms uses text generation optionally (its designed fallback, incident-management.md) and requires none for it.
- ci.toml switches off every plugin that requires a vendor; the tests that need one switch it on with fakes (the pytest-env pattern for access.*). A developer switches a plugin off from app/.env.
- feature-packages.md guidance and the TASK-114 generator point new plugins at the rule.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An enabled plugin whose settings slice fails validation aborts boot before yield naming the key, in every layer (lifespan test)
- [ ] #2 An enabled plugin whose required vendor is not configured aborts boot with one CRITICAL plugin_boot_failed event naming the plugin and the configuration key, and no secret value (lifespan test)
- [ ] #3 incident.scribe enabled with no [openai.tenant] aborts boot naming the key; incident.comms enabled with no [openai.tenant] boots and reports text generation unavailable (tests)
- [ ] #4 ci.toml switches off every plugin that requires a vendor; the CI boot and the full suite pass with no vendor tenant configured
- [ ] #5 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->
