---
id: TASK-156
title: >-
  Startup configuration summary and self-masking secrets: record the decision
  and implement it
status: To Do
assignee: []
created_date: 2026-10-20 12:31
updated_date: '2026-10-23T17:07:00Z'
labels:
  - plugin-architecture
  - configuration
  - observability
milestone: m-7
dependencies:
  - TASK-111.2
  - TASK-111.17
references:
  - decisions/configuration.md
  - decisions/observability.md
  - decisions/lifecycle.md
  - https://github.com/cds-snc/sre-bot/issues/1757
priority: medium
type: feature
ordinal: 405000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The startup configuration log is legacy code no ADR designed. server/lifespan.py _list_configs_from_sections (lifespan.py:64) logs the key names of a hand-kept list of slices (identity, server, security, directory, sre_ops) plus the LOG_LEVEL and GIT_SHA values; a separate configuration_files_loaded event names the files. It misses the logging keys, the Slack and Google slices and every vendor slice. decisions/configuration.md bans secrets from logs and repr and makes every slice validate at boot, but no record decides what startup reports about configuration.

Industry guidance sets the target:
- OWASP Logging Cheat Sheet: log start-ups and configuration changes with an application identifier and version; never log secrets.
- OWASP ASVS 5.0 V16 (16.3.3): log the use of security bypasses.
- Spring Boot Actuator: configuration views are sanitized by default and not exposed over HTTP by default.
- OpenTelemetry service resource attributes: service.name, service.version, service.instance.id, deployment.environment.name.
- pydantic SecretStr masks itself in repr and JSON.

Decisions to record, as an amendment to decisions/configuration.md cross-linked from observability.md and lifecycle.md (lifecycle.md Context line 15 becomes a decision):
- A startup identity event carries service name, version (GIT_SHA), environment and an instance id, bound as context on every record.
- A configuration summary is generated from every slice the configuration phase validates, never from a hand-kept list. It shows field names (lower snake_case), a set/unset state for secrets, non-secret values from the reviewed TOML files, the configuration files loaded (names only), and a SHA-256 of the non-secret effective configuration so drift between replicas and environments shows.
- Every secret field is typed SecretStr or SecretBytes; key-name redaction stays the second line of defence.
- A setting that weakens security at boot (dev bypass enabled, no issuers configured) logs at WARNING naming the setting.
- No HTTP endpoint exposes configuration; any future one is authenticated, admin-only and sanitized by default.

The configuration phase runs in the app factory (create_app, server/server.py), and TASK-111.17 configures logging there, so the summary is emitted from that phase as JSON. TASK-111.17 also makes a slice validation error carry no input value, which the no-secret test can rely on. Secrets reach the app as task-definition secrets named <SLICE>__<FIELD>. In production the dev bypass already fails boot (server/configuration/host_configuration.py:42), so the bypass WARNING applies outside production only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/configuration.md records the startup identity event, the generated configuration summary (field names, secret presence only, non-secret file values, files loaded, non-secret config hash), secret typing, the WARNING rule for security-weakening settings and the no-config-endpoint rule; observability.md and lifecycle.md link to it
- [ ] #2 The app factory's configuration phase emits the summary for every slice it validates, generated from that set rather than a hand-kept list, and _list_configs_from_sections is removed
- [ ] #3 Every secret field in a settings slice is SecretStr or SecretBytes, and a test asserts no slice repr or model_dump_json shows a secret value
- [ ] #4 Outside production, the dev bypass enabled at boot logs a WARNING naming the setting, and an empty issuer configuration logs a WARNING in every environment (in production the bypass already fails boot, TASK-111.8)
- [ ] #5 ruff, lint-imports, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
