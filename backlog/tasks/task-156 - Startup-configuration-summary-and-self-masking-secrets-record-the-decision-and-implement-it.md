---
id: TASK-156
title: >-
  Startup configuration summary and self-masking secrets: record the decision
  and implement it
status: In Progress
assignee: []
created_date: 2026-10-20 12:31
updated_date: '2026-10-29T16:44:00Z'
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
- [x] #1 decisions/configuration.md records the generated configuration summaries (host in the configuration phase, plugins after plugin boot; field names, secret presence only, non-public values at most their last four characters, files loaded, a hash of the shown values), secret typing, the WARNING rule for security-weakening settings and the no-config-endpoint rule; observability.md records the service identity carried on every record (OpenTelemetry names) and the log destinations; lifecycle.md, plugins.md and security.md link to it
- [x] #2 The app factory's configuration phase emits the summary for every slice it validates, generated from that set rather than a hand-kept list, plugin boot emits plugin_configuration_summary for the enabled plugins' slices, and _list_configs_from_sections is removed
- [x] #3 Every secret field in a settings slice is SecretStr or SecretBytes, and a test asserts no slice repr or model_dump_json shows a secret value
- [x] #4 Outside production, the dev bypass enabled at boot logs a WARNING naming the setting, and an empty issuer configuration logs a WARNING in every environment (in production the bypass already fails boot, TASK-111.8)
- [x] #5 ruff, lint-imports, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (approved by the human 2026-10-29, open questions decided below; the ADR text was recorded the same day in the planning session and this PR carries it). Grounded against main cd090014 and, read-only, origin/task-172-plugin-requirements and origin/task-173-legacy-incident-google.

## Findings that shape the plan
- Summary source: _validate_slices (server/configuration/host_configuration.py:152-190) calls ~25 getters and discards the results; lifespan.py:64-92 (_list_configs_from_sections) is the only consumer of slices, with a hand list of five; lifespan.py:255-272 emits configuration_files_loaded and calls it. Only test: tests/integration/server/test_lifespan.py:60-96. No terraform, bin, docs or alarm names these events (rg).
- Key-name redaction would corrupt a dict-shaped summary: infrastructure/logging/formatters.py SENSITIVE_PATTERNS match substrings of dict keys and replace the value, so a field named unauthorized_errors ("auth") or a secret's set/unset under bot_token would log as ***REDACTED***. The summary is therefore a list of records {slice, name, value|state} (names are values, never dict keys); redaction stays the second line.
- env_only (contracts/configuration.py:106) marks credentials AND non-public values (Drive ids, AWS ARNs, customer id, delegated email). Both must never be logged, so "withheld" = env_only metadata OR a SecretStr/SecretBytes value (nested models and lists recursed). No name heuristic in production code. Nested tenant models (Slack, Google, AWS, Trello) carry env_only fields too.
- Secrets typed plain str today: SlackSettings bot_token, user_token, app_token, signing_secret (integrations/slack/settings.py:71-74) and GoogleWorkspaceTenant.service_account_key (google_workspace/settings.py:68). Already SecretStr: security dev_bypass_token, trello app_key/token, sentinel shared_key, openai api_key, notify sre_user_name/sre_client_secret, opsgenie integrations_key. Production readers to swap to get_secret_value(): slack/client.py:42,57; slack/bootstrap.py:65,89; slack/provider.py:324; google_workspace/settings.py:88. Truthiness checks (host_configuration.py:111-117, provider.py:294,301, oncall_sync/adapters/slack.py:140, slack/settings.py:116) keep working: bool(SecretStr("")) is False (verified with uv run python; repr and model_dump_json mask).
- logging chain: structlog.contextvars.clear_contextvars() exists (infrastructure/logging/context.py:142), so contextvars-bound identity could be wiped; a static-field processor in the chain (also in foreign_pre_chain) reaches every record, stdlib/uvicorn included. add_app_info (formatters.py:55) is exported, never wired: dead, replaced by this processor and deleted with its test.
- The dev-bypass-in-production refusal is host_configuration.py:42-ish (refuse_dev_bypass_in_production); the empty-issuer WARNING already exists in lifespan._initialize_security_services (lifespan.py:147-152, event security_services_no_issuer_config, no test).

## Design
1. Identity: server/configuration/identity.py gains ServiceIdentity (frozen dataclass: service_name from the distribution metadata (importlib.metadata, pyproject [project].name; one source, no setting), version = git_sha, environment, instance_id = uuid4 per process) and log_fields() returning the OpenTelemetry resource names: service.name, service.version, service.instance.id, deployment.environment.name (dotted keys follow the existing code.file.path precedent in setup.py). configure_logging(environment, logging_settings, log_level=None, static_fields=None) adds a processor right after merge_contextvars. load_host_configuration passes the fields and logs service_identity (INFO) right after logging is configured.
2. Recording: ConfigurationSlice.__init__ records each successfully built slice by class in contracts/configuration.py (installed-state precedent: _files, _host); install_configuration_files starts a fresh record; built_slices() returns a snapshot sorted by table. _validate_slices is NOT restructured (no hand list, and no edit to the getter lines TASK-173 changes).
3. Summary (new server/configuration/summary.py, pure functions, frozen dataclasses): walk each slice's model_fields; leaf path = dotted name (tenant.team_id, issuers.0.audience); withheld leaf -> {"slice","name","state":"set"|"unset"} by truthiness; a SecretStr/SecretBytes value is never read (no get_secret_value, no repr); a non-public env_only str value of twelve or more characters also carries "tail" = its last four characters (configuration.md: not logged in full), shorter ones state only; other leaf -> {"slice","name","value"}. config_hash = SHA-256 of canonical JSON (sorted, compact) of the shown (slice, name, value) triples only; withheld values (secrets and non-public values) are never hashed, tails included (a fast unsalted hash of a low-entropy value is guessable: OWASP Password Storage). Identifier rule: no variable, parameter or attribute on this path contains secret, token, key or password (CodeQL clear-text-logging, #1806); the code says withheld, state, field_name, entry.
4. Events, all through the one pipeline: configuration_summary (INFO, phase=configuration, environment, files = names only, config_hash, slices = records) emitted at the end of load_host_configuration; replaces configuration_files_loaded, configuration_initialized and configuration_loaded. Plugin-owned slices (validated in plugin boot, decisions/plugins.md "Boot failure policy" and lifecycle.md phase 3) are reported once after plugin boot as plugin_configuration_summary with a section per plugin (slices first built during that plugin's boot, attributed by a recorder snapshot around each plugin's registration; its own hash), emitted in lifespan after register_feature_integrations; a slice of a disabled plugin is never built and so never listed, which is the truth. Host summary logs first, so a plugin boot abort still leaves it in the log.
5. Security WARNINGs (AC4): host_configuration.warn_on_weakened_security(host, security) after refuse_dev_bypass_in_production: event security_setting_weakened (WARNING) with setting="security.dev_bypass_enabled" outside production, and setting="security.issuers" in every environment when empty. The lifespan copy of the issuer warning is deleted (lifespan keeps the early return that skips JWKS warmup); one owner, one event name a deploy check can filter on.
6. Slack coverage finding: SLACK__SIGNING_SECRET and SLACK__USER_TOKEN change env_only source from "codespaces" to "local" (a user token is one person's identity and the signing secret is HTTP-Events-only; development runs Socket Mode); app/.env.example regenerates with make env-example (human reviews the diff). Alternative needs human-held Codespaces secrets (OQ8).

## Steps (red tests first for each, then code)
S1 ADR amendment (AC1): recorded 2026-10-29 in the planning session, uncommitted on main, carried by this branch: configuration.md (line 45 partial display, Fail fast: plugin slices validate in plugin boot, new paragraph "Startup reports configuration, never a secret", Changes line), observability.md ("Service identity on every record" with OpenTelemetry naming, "Log destinations" inventory, Changes line), lifecycle.md (phase 1 ends with configuration_summary, phase 3 validates plugin slices and logs plugin_configuration_summary, Changes line), plugins.md and security.md Changes lines. Implementation checks the ADR text still matches what ships and adjusts it in the same PR. Cite: OWASP Logging Cheat Sheet (log start-ups, application identifier and version, exclude secrets), ASVS 5.0 V16 16.2.5 and 16.3.2 (sensitive data by protection level, access recorded without the data), OpenTelemetry service.* and deployment.environment.name (stable), pydantic SecretStr, Spring Boot Actuator sanitisation. Note: ASVS 16.3.3 is about attempts to bypass controls at request time, not boot configuration; the WARNING rests on the OWASP start-up guidance (OQ9).
S2 contracts/configuration.py: is_env_only(field) helper (bin/generate_env_example.py:_env_only reuses it), slice recording, built_slices(). 
S3 server/configuration/summary.py (+ __init__ export).
S4 identity.py ServiceIdentity; infrastructure/logging/setup.py static_fields processor in both chains; delete add_app_info, its export (logging/__init__.py) and its test class.
S5 host_configuration.py: identity wiring, service_identity and configuration_summary events, warn_on_weakened_security; HostConfiguration drops identity, logging and files if rg shows no other reader (only lifespan.py:259-266 read them); lifespan.py: delete _list_configs_from_sections (lifespan.py:64-92), the configuration_files_loaded block, the issuer warning, now-unused imports; add plugin_configuration_summary after plugin boot.
S6 Secret typing (AC3): Slack four fields to SecretStr (bot_token default SecretStr(""), app_token/signing_secret SecretStr | None, the empty-is-absent validator kept), Google service_account_key to SecretStr; the six production readers above; env_only sources per S1.6; update the ~19 test files that assert plain values (SlackSettings(...) construction still accepts str).
S7 bin/deploy-checks.zsh (dev tooling): delete the old contract task check (header lines 13-16, TASK_CHECKS, the block at 158-195) and add task check summary (post only): per running task, configuration_summary present since the rollout, service.instance.id distinct per task, config_hash identical across tasks (drift shows as FAIL), security_setting_weakened count printed (informational), and no token-shaped value (xox[abpeur]-, xapp-, -----BEGIN) in any boot line (reuses mask() patterns). Checks: zsh -n, usage run, ruff on bin python.
S8 Gates: ruff, lint-imports, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make env-example drift test, check_settings_key_ownership, bin tests.

## AC traceability and tests (intended names under app/tests)
- AC1 -> S1; review by human (no test).
- AC2 -> S2-S5: tests/unit/contracts/test_contracts_configuration_built_slices.py (records successful builds only, fresh on install, sorted); tests/unit/server/configuration/test_server_configuration_summary_build.py (every slice built in the phase is present, no hand list: a ConfigurationSlice subclass added in the test appears; record shapes; nested and list recursion; withheld by env_only and by SecretStr value; set/unset by truthiness; tail only for a non-public value of twelve or more characters, never for a SecretStr; hash stable across ordering, changes on a non-secret value, unchanged by a secret value); tests/integration/server/test_server_configuration_phase_logging_render.py extended (production JSON pipeline: configuration_summary parses as JSON, files are names, a canary secret appears nowhere in stdout/stderr and a canary non-public id only as its last four characters, unauthorized_errors survives unredacted); tests/unit/server/configuration/test_server_configuration_service_identity.py (service.name equals the distribution name, instance id is a UUID v4 and differs per build); tests/unit/infrastructure/logging/test_logging_setup_static_fields.py (identity on structlog and foreign records, survives clear_contextvars); lifespan test asserting plugin_configuration_summary lists only slices built after plugin boot; the old test_lifespan_list_configs_logs_settings is deleted with the function.
- AC3 -> S6: tests/unit/infrastructure/configuration/test_configuration_slices_secret_typing.py walks every ConfigurationSlice subclass and nested BaseModel: (a) any env_only field whose name contains token, secret, password or key is SecretStr/SecretBytes (the heuristic lives in the test only), (b) every SecretStr/SecretBytes field is env_only (no secret can sit in a reviewed file), (c) with a canary set for each such field through the environment, no slice repr or model_dump_json contains it. Slack/Google tests updated for get_secret_value; empty means unset still holds.
- AC4 -> S5: tests/unit/server/test_server_security_weakened_warning.py (local with bypass logs the WARNING naming security.dev_bypass_enabled; ci likewise; production with bypass still raises, no warning; empty issuers warns in all three; configured issuers and bypass off log none; the event never carries a value).
- AC5 -> S8. Boundary/failure cases: invalid slice still logs only configuration_invalid and emits no summary; an unbuildable slice is not recorded; empty-string credential counts as unset in the summary.
- Coverage fix (S6) -> tests/unit/bin/test_bin_audit_env_coverage_classify.py extended; env-checks re-run by the human: Slack names no longer flagged.

## Size gate
Estimate: ~330 production LOC net (new summary.py ~110, contracts ~30, identity ~25, setup.py ~20, host_configuration ~50, lifespan -45/+15, Slack/Google settings and six readers ~30, deploy-checks -40/+35); ~15 production files (about half are one-to-five-line reader swaps or deletions), plus 4 ADRs and ~12 new/edited test files. Subsystems: app only (bin helper is dev tooling). LOC passes; file count exceeds ~10 only through mechanical swaps. Nothing must land before anything else, so one PR with a size exception. The SecretStr swap (S6) is a type change with behaviour preserved; if the reviewer wants it isolated it is a clean first PR (S6 + S1.3 wording) with the rest following, at the cost of a second deploy.

## Merge order and conflicts
Merge TASK-172 (#1809) and TASK-173 (#1810) first, then branch 156 from main. No semantic dependency: 156 reads only built slices and adds nothing to the plugin hooks. Textual conflicts if 156 goes first: 173 rewrites the get_google_workspace_settings() line in _validate_slices (156 does not touch getter lines, so rebasing is trivial); 172 edits lifespan._serve (load_plugins/resolve_plugin_requirements neighbourhood, where 156 adds plugin_configuration_summary after register_feature_integrations) and decisions/plugins.md/configuration.md Changes tails (append conflicts only). 172's plugin_boot_failed uses the field name setting; the new security_setting_weakened event uses the same field name, never the forbidden words.

## Pins
No new run switch and no new environment-only name, so pyproject.toml pytest-env gets no new line; the existing SLACK__ and GOOGLE_WORKSPACE__ blanks cover the retyped fields. The real-pipeline integration test sets canaries itself with monkeypatch.

## Assumptions and doubts (verify during implementation)
1. No slice is built before install_configuration_files (the base fails closed), so recording from install covers the whole phase - verify with the existing "built earlier fails" tests.
2. Tests that assert on the summary clear slice caches (the existing _clear_caches pattern); a cached getter is not rebuilt and so not recorded. Production builds each slice once.
3. Nothing else constructs a slice with constructor arguments in production code (a recorded override would mislead) - rg "Settings\(" outside tests.
4. HostConfiguration.identity/logging/files have no reader besides lifespan.py:259-266 and no test reads them - rg incl. tests before deleting.
5. packages/access and incident scribe settings that are plain BaseSettings (not ConfigurationSlice) are outside the summary until TASK-166 moves them onto the files; no secret among them (authn_token in access/config/settings.py:28 is a group-slug default, not a credential).
6. Log volume: one ~10-15 KB event per task start; under CloudWatch's 256 KB event limit - measure in the integration test and assert a size bound.
7. SecretStr is masking, not protection: get_secret_value() still returns the plain value in memory; third-party SDK calls receive plain strings.

## Blast radius and rollback
A wrong SecretStr swap breaks Slack/Google at first use or boot (sdk receives a SecretStr instead of str): covered by the reader tests and by the existing slack_up and google checks in post. The summary is log-only; a bug there could abort boot (exception in the phase) - the builder must not raise on odd values (default=str in JSON, tests with odd types). One git revert restores behaviour; no terraform, no new environment names, no config file changes, no data. Deploy order: none. After deploy (human): zsh bin/deploy-checks.zsh post summary; make env-checks (Slack names clean); regenerate/review app/.env.example.

## Decisions (human, 2026-10-29, each assessed against the ADRs, doc-11 and current guidance)
OQ1 Host configuration_summary in phase 1 plus one plugin_configuration_summary after plugin boot, a section per plugin (OWASP start-up logging; Spring Boot collates per-component configuration). configuration.md Fail fast fixed: plugin slices validate in plugin boot, only when enabled.
OQ2 Slices recorded at construction.
OQ3 configuration.md line 45 kept: non-public values not logged in full; the summary shows set plus the last four characters (twelve or more characters), secrets set/unset only (ASVS 5.0 16.2.5, 14.2.4; Spring Boot 3 masks by default). observability.md records the log destinations (CloudWatch /ecs/sre-bot-app 30 days, no subscription filter; Sentinel audit events only), ASVS 16.2.3. Non-public values stay str; model_dump_json shows them, accepted.
OQ4 Hash over shown values only; withheld values never hashed (Helm checksum/config; OWASP Password Storage).
OQ5 Chain processor, flat dotted OpenTelemetry resource names; observability.md: field names follow OpenTelemetry conventions where one exists. AC1 wording: carried on every record.
OQ6 UUID v4 per process (OpenTelemetry recommendation; no new platform name, configuration.md closed list; deploy-checks already separates tasks by log stream).
OQ7 service.name from the distribution metadata, no setting; OTEL_SERVICE_NAME is the SDK's override if an OpenTelemetry SDK is adopted later (TASK-150).
OQ8 SLACK__SIGNING_SECRET and SLACK__USER_TOKEN env_only source "local"; the human regenerates app/.env.example with make env-example and reviews the diff.
OQ9 Cite the OWASP start-up guidance and ASVS 16.2.5 (and 16.2.3 for the inventory), not 16.3.3.
OQ10 One PR with a size exception.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-29 planning: OQ1-OQ10 decided by the human after an ADR, doc-11 and online-guidance assessment (see the plan's Decisions). The ADR amendments are written on main's working tree (configuration.md, observability.md, lifecycle.md, plugins.md, security.md) and ride on this task's branch. The description's identity 'bound as context' is superseded: identity is carried on every record by a chain processor (observability.md). Branch after #1809 and #1810 merge, or from main with a small rebase.

2026-10-29: small fix riding here (TASK-156 touches both ADRs): observability.md line 16 and plugins.md Boot failure policy still say plugin_boot_failed names 'the configuration key'; since TASK-172 the field is `setting`. Reword both to 'the setting at fault (`setting` field)'.

2026-10-29 implementation: summary builder (server/configuration/summary.py), slice recorder + is_env_only (contracts/configuration.py), per-plugin attribution (server/plugins/boot.py attribute_built_slices around each plugin hook call), identity processor in both chains, security_setting_weakened, SecretStr for Slack and Google credentials, deploy-checks 'summary' check. Deviations: plugin_configuration_summary lists only plugins that built a slice (configuration.md reworded); service_identity event documented in observability.md; mypy still reports 41 errors in 14 files none touched here (i18n, legacy modules, slack/channels.py). Human: review app/.env.example diff, re-run make env-checks, run 'zsh bin/deploy-checks.zsh post summary' after deploy.

2026-10-29 (human review of the first local boot): the summary is regrouped per slice: one section per table holding values (a list of plain values stays one value; nested models and lists of models get dotted names), set, unset and partial (non-public tails), matching Spring Boot configprops and Backstage config:print. The service_identity event and the duplicate environment field are dropped, since every record carries the identity. Shown names are dict keys, so the key-name redaction masks four names: aws.unauthorized_codes, openai.max_output_tokens, slack.unauthorized_errors and the whole notify_api_key_leak section. This fails safe, the hash still covers them, and a unit test over every slice pins the set. ADR text updated in configuration.md and observability.md. Gates, each run once at the end: ruff clean; mypy 41 errors in the same 14 untouched legacy files; pytest 5931 passed; import contracts 13 kept; key ownership OK. Production diff: 16 files, +192 -152, plus the new summary.py (143 lines).

2026-10-29: the three @contextmanager functions annotated -> Iterator[...] now return Generator[...]. Current typeshed deprecates the Iterator form, and the editor flagged it. The three are server/plugins/boot.py attribute_built_slices (new in this task), features/incident/comms/entrypoints/slack.py _incident_scope and tests/factories/services.py _scope. An AST scan found no other @contextmanager or @asynccontextmanager with an Iterator or AsyncIterator return. Checks: ruff and mypy clean on the three files; 490 targeted tests passed.
<!-- SECTION:NOTES:END -->
