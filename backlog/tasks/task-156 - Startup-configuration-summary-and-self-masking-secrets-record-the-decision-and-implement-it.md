---
id: TASK-156
title: >-
  Startup configuration summary and self-masking secrets: record the decision
  and implement it
status: To Do
assignee: []
created_date: '2026-10-20 12:31'
labels:
  - plugin-architecture
  - configuration
  - observability
milestone: m-7
dependencies:
  - TASK-111
references:
  - decisions/configuration.md
  - decisions/observability.md
  - decisions/lifecycle.md
priority: medium
type: feature
ordinal: 405000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The startup configuration log is legacy code no ADR designed. server/lifespan.py _list_configs_from_sections logs the key names of a hand-kept list of four slices (app, server, directory, sre_ops) plus the LOG_LEVEL and GIT_SHA values. It misses the logging, Slack and Google slices and every vendor slice. decisions/configuration.md bans secrets from logs and repr and makes every slice validate at boot, but no record decides what startup reports about configuration.

Industry guidance sets the target:
- OWASP Logging Cheat Sheet: log start-ups and configuration changes with an application identifier and version; never log secrets.
- OWASP ASVS 5.0 V16 (16.3.3): log the use of security bypasses.
- Spring Boot Actuator: configuration views are sanitized by default and not exposed over HTTP by default.
- OpenTelemetry service resource attributes: service.name, service.version, service.instance.id, deployment.environment.name.
- pydantic SecretStr masks itself in repr and JSON.

Decisions to record, as an amendment to decisions/configuration.md cross-linked from observability.md and lifecycle.md (lifecycle.md Context line 15 becomes a decision):
- A startup identity event carries service name, version (GIT_SHA), environment and an instance id, bound as context on every record.
- A configuration summary is generated from every slice the configuration phase validates, never from a hand-kept list. It shows field names, a set/unset state for secrets, non-secret values from the reviewed TOML files, the configuration files loaded (names only), and a SHA-256 of the non-secret effective configuration so drift between replicas and environments shows.
- Every secret field is typed SecretStr or SecretBytes; key-name redaction stays the second line of defence.
- A setting that weakens security at boot (dev bypass enabled, no issuers configured) logs at WARNING naming the setting.
- No HTTP endpoint exposes configuration; any future one is authenticated, admin-only and sanitized by default.

Depends on TASK-111, which builds the TOML loader that the summary reports on. Env names follow TASK-111's renames.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/configuration.md records the startup identity event, the generated configuration summary (field names, secret presence only, non-secret file values, files loaded, non-secret config hash), secret typing, the WARNING rule for security-weakening settings and the no-config-endpoint rule; observability.md and lifecycle.md link to it
- [ ] #2 Lifespan's configuration phase emits the summary for every slice it validates, generated from that set rather than a hand-kept list, and _list_configs_from_sections is removed
- [ ] #3 Every secret field in a settings slice is SecretStr or SecretBytes, and a test asserts no slice repr or model_dump_json shows a secret value
- [ ] #4 The dev bypass enabled at boot and an empty issuer configuration each log a WARNING naming the setting
- [ ] #5 ruff, lint-imports, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
