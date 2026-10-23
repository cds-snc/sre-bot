---
id: TASK-112.1
title: >-
  Move the Slack transport switches to [slack_transport] in server/slack/;
  cross-slice Slack rules in the configuration phase
status: In Progress
assignee: []
created_date: '2026-10-23T19:20:00Z'
updated_date: '2026-10-23T22:26:00Z'
labels:
  - plugin-architecture
  - configuration
  - slack
milestone: m-7
dependencies: []
references:
  - decisions/configuration.md
  - decisions/transport-slack.md
  - decisions/platform-transports.md
  - decisions/plugins.md
parent_task_id: TASK-112
priority: medium
type: feature
ordinal: 439000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-112. The Slack transport slice gains enabled (replacing SLACK_ENABLED; production.toml and local.toml set it true) and socket_mode (replacing SLACK_SOCKET_MODE; default true in base.toml, set nowhere else), and moves from infrastructure/slack/settings.py to server/slack/settings.py (infrastructure/ is hosting only, decisions/plugin-architecture.md). The host builds it in the configuration phase and installs a contracts fact, SlackTransportInfo(command_prefix) in contracts/slack/transport.py, modelled on HostInfo; the five legacy modules read the prefix from it, so nothing below server/ imports the slice. The Slack provider receives enabled, socket_mode and command_prefix from lifespan as constructor arguments and stops importing the slice (the integrations.slack.provider -> infrastructure.slack.settings ignore entry goes from both import contracts). The cross-slice Slack rules move from integrations/slack/settings.py into server/configuration/host_configuration.py: transport on requires the Slack tenant entry and the bot token; Socket Mode requires the app token; HTTP Events mode requires the signing secret; Socket Mode without the signing secret logs slack_signing_secret_not_set_in_socket_mode at info. Production runs Socket Mode with no signing secret and must keep booting. The SLACK_ENABLED exception leaves bin/check_settings_key_ownership.py. One PR with a file-gate exception (human 2026-10-23: ~17 production files, ten of them TOML or one-line import swaps, behaviour-preserving).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 server/slack/settings.py holds the transport slice with enabled, socket_mode and command_prefix in [slack_transport]; base.toml sets enabled false and socket_mode true, production.toml and local.toml set enabled true, and no other file sets socket_mode; app/infrastructure/slack/ no longer exists
- [x] #2 SLACK_ENABLED and SLACK_SOCKET_MODE are no longer read from the environment or .env (test)
- [x] #3 The configuration phase fails boot naming the key when the transport is on without the Slack tenant entry or the bot token, in Socket Mode without the app token, or in HTTP Events mode without the signing secret; with the transport off none is required (tests)
- [x] #4 Socket Mode without a signing secret boots and logs slack_signing_secret_not_set_in_socket_mode once at info; raised and logged text carries no credential value (test with the production shape)
- [x] #5 contracts/slack/transport.py holds SlackTransportInfo, installed by the host in the configuration phase; the legacy modules read command_prefix from it and nothing outside server/ imports server/slack/settings.py
- [x] #6 The Slack provider takes enabled, socket_mode and command_prefix as constructor arguments from lifespan and imports no settings slice; the provider ignore entry is gone from both import-linter contracts and make check-import-contracts passes
- [x] #7 bin/check_settings_key_ownership.py has no vendor-switch allowlist and make check-settings-key-ownership passes
- [x] #8 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Written against main 0fd872ea. Re-run the rg searches below on the tree before editing. TDD: S0 red first.

Size gate: file-gate exception approved by the human 2026-10-23 (~17 production files, ~250 LOC; ten are TOML files, one-line import swaps or pyproject lines). One subsystem (Slack transport configuration), behaviour-preserving in production; one git revert restores service.

## Steps
S0. Tests first (matrix below), red.
S1. contracts/slack/transport.py (new): @dataclass(frozen=True) SlackTransportInfo(command_prefix: str); install_slack_transport_info / uninstall_slack_transport_info / slack_transport_info(), the last raising ConfigurationError when not installed. Same form and module-state comment as contracts/configuration.py:50-98. Only command_prefix: the legacy modules are its only readers; enabled and socket_mode stay host-only. Not registered in the service registry (no reader there).
S2. server/slack/__init__.py (empty docstring only) and server/slack/settings.py: move infrastructure/slack/settings.py here unchanged in shape (ConfigurationSlice, [slack_transport], SLACK_TRANSPORT__ prefix, extra forbid) and add enabled: bool = False and socket_mode: bool = True with Field descriptions. Delete app/infrastructure/slack/.
S3. config/base.toml [slack_transport]: enabled = false, socket_mode = true, command_prefix = "". production.toml: new [slack_transport] with enabled = true. local.toml: enabled = true beside command_prefix = "dev-". ci.toml unchanged.
S4. server/configuration/host_configuration.py: HostConfiguration gains slack_transport: SlackTransportSettings. _validate_slices builds get_slack_transport_settings() after get_slack_settings(), runs validate_slack_transport(transport, slack) and installs SlackTransportInfo(command_prefix) next to install_host_info. validate_slack_transport raises ConfigurationError naming the key, never a value:
  - transport off: nothing required;
  - on: slack.tenant is not None (reads only .tenant, so TASK-157's enterprise-id entry passes) and bot_token non-empty;
  - socket_mode true: app_token required; socket_mode false: signing_secret required;
  - socket_mode true and no signing secret: info slack_signing_secret_not_set_in_socket_mode (same event, detail names [slack_transport] socket_mode), never fails. This is production.
  Key names in messages come from one module-level constants block (SLACK_TEAM_ID, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET today) so TASK-111.9 renames them in one place.
S5. integrations/slack/settings.py: delete enabled, socket_mode and _validate_transport_credentials except the blank-team-id check; rewrite the module docstring (transport keys in [slack_transport], rules in host_configuration.py). extra stays "ignore", so a stale SLACK_ENABLED or SLACK_SOCKET_MODE in the blob or .env is inert. Nothing else changes (TASK-111.9 rewrites the slice).
S6. integrations/slack/provider.py: drop the infrastructure.slack.settings import (:24). __init__ gains socket_mode: bool = True beside the existing enabled and command_prefix; reads of settings.enabled / settings.socket_mode (:245-246, :279, :282, :290, :317, :329, :505, :507) use the stored values; :306 calls LegacySlackBootstrap().create_app(socket_mode=self._socket_mode). get_slack_provider (:1139) takes keyword-only enabled, socket_mode, command_prefix and passes them through.
S7. integrations/slack/bootstrap.py: create_app(self, socket_mode: bool = True) on both classes; request_verification_enabled = not socket_mode. Callers in modules/ops/notifications.py keep the default (same as production today).
S8. server/lifespan.py:279: get_slack_provider(enabled=..., socket_mode=..., command_prefix=...) from configuration.slack_transport.
S9. Legacy modules aws/aws.py:14,54, secret/secret.py:12,23, role/role.py:6,36, atip/atip.py:12,37, incident/incident.py:11,37: import slack_transport_info from contracts.slack.transport and read .command_prefix.
S10. app/pyproject.toml: remove "integrations.slack.provider -> infrastructure.slack.settings" from the layers and integrations-leaf ignore lists; remove the pytest env line SLACK_ENABLED=false (:136).
S11. bin/check_settings_key_ownership.py: delete ALLOWED_VENDOR_SWITCHES (:66) and its clause (:481); update the module and find_vendor_switches docstrings. Confirm the table-ownership check maps [slack_transport] to server/slack/settings.py.
S12. ADRs and docs (decisions taken 2026-10-23): transport-slack.md (:14 current state, :29, :67 home now server/slack/settings.py + SlackTransportInfo, Changes line), platform-transports.md:16 and platform-entrypoints.md:22 current state, configuration.md (:21, :88, :102 interim SLACK_ENABLED wording becomes shipped state), plugins.md (:89, :101), lifecycle.md (:83, :90), backlog/docs/doc-14:68.

Human edits (agent cannot read): app/.env.example:26 delete '# SLACK_ENABLED=true [codespaces]'; app/.env the same line if present.

## AC -> steps -> tests
- AC1 (slice in server/slack, files, infrastructure/slack gone): S2, S3 -> test_slack_transport_settings.py (moved), file pin tests.
- AC2 (old names unread): S5 -> test_slack_transport_settings.py, test_configuration_settings_production_names.py.
- AC3 (rules fail naming the key): S4 -> test_server_configuration_slack_transport_rules.py, test_lifespan_vendor_slice_validation.py.
- AC4 (production shape, notice, no leak): S4 -> test_server_configuration_slack_transport_rules.py, test_server_configuration_phase_logging_render.py.
- AC5 (contract, legacy readers): S1, S4, S9 -> test_slack_transport_info_install.py, the five *_command_registration tests.
- AC6 (provider kwargs, ignore entry gone): S6-S8, S10 -> test_slack_provider.py, test_slack_bootstrap.py, make check-import-contracts.
- AC7 (no allowlist): S11 -> test_bin_settings_key_ownership_check.py, make check-settings-key-ownership.
- AC8 gates: all.

## Test matrix
- tests/unit/server/slack/test_slack_transport_settings.py (moved from tests/unit/infrastructure/slack/): defaults (enabled false, socket_mode true); ci false, local true, production true (pins the real file: guards the silent-off risk); socket_mode set only in base.toml (tomllib scan of all four files); SLACK_TRANSPORT__ENABLED overrides the file; SLACK_ENABLED and SLACK_SOCKET_MODE in env and .env are ignored; unknown key fails naming it.
- tests/unit/server/configuration/test_server_configuration_slack_transport_rules.py (new): off with no tenant boots; off with partial credentials boots; on without tenant / without bot token fails naming the key; Socket Mode without app token fails naming the key; HTTP mode without signing secret fails naming the key; HTTP mode complete passes; production shape (tenant, bot and app tokens, Socket Mode, no signing secret) passes and logs the notice exactly once at info; error text and log lines carry no token value; enterprise-id-only tenant passes (TASK-157).
- tests/unit/contracts/slack/test_slack_transport_info_install.py (new): reading before install fails; install then read; uninstall clears. tests/conftest.py installs SlackTransportInfo(command_prefix="") beside HostInfo and uninstalls after.
- tests/integration/server/test_lifespan_vendor_slice_validation.py: transport on without tenant fails the real lifespan in the configuration phase (SLACK_TRANSPORT__ENABLED=true, cache_clear); absent entries still boot with no network call.
- tests/integration/server/test_server_configuration_phase_logging_render.py (:65,97,98,157): drive the notice through [slack_transport] in the tmp files; JSON render assertion unchanged.
- tests/integration/server/test_lifespan_security_settings_validation.py:35 and the env rows in test_configuration_settings_production_names.py (:82,246,284), test_server_configured_systems_read.py (:76,90): drop SLACK_ENABLED / SLACK_SOCKET_MODE.
- tests/unit/integrations/slack/test_slack_settings.py, test_slack_settings_team_id_validate.py: remove enabled/socket_mode cases (moved to the rules test); keep blank-team-id.
- tests/unit/integrations/slack/test_slack_bootstrap.py (:107,122,138): create_app(socket_mode=...) sets request verification.
- tests/unit/integrations/slack/test_slack_provider.py and conftest (:51,57,83): get_slack_provider passes the three values; disabled provider skips init; HTTP mode skips the Socket Mode handler.
- tests/unit/modules/{aws,secret,role,atip,incident}/test_*_command_registration.py: install SlackTransportInfo(command_prefix="dev-") and assert the prefixed command; drop the transport-settings patching.
- tests/unit/bin/test_bin_settings_key_ownership_check.py:292: a SLACK_ENABLED field in integrations/ now fails the vendor-enabled rule; the real tree passes.
- Every test file that patches infrastructure.slack.settings (rg) moves to the new path or the contract.

## Assumptions and doubts (verify)
- The table-ownership check (TASK-111.3) finds the owner by scanning slice classes; confirm it accepts server/slack/settings.py (run make check-settings-key-ownership after S2).
- Tests and factories that build the provider with SimpleNamespace(enabled=..., socket_mode=...) settings rely on settings for behaviour: a full red run after S6 lists them; fix each with constructor kwargs.
- Legacy module registration runs after the configuration phase installs SlackTransportInfo (lifespan order); the legacy_surface conftest and test_lifespan_sre_single_registration.py may need the install.
- ConfigurationError from a host rule goes through the existing _log_invalid CRITICAL path (host_configuration.py:79-90); the integration test confirms.
- SLACK__COMMAND_PREFIX in terraform/templates/sre-bot.json.tpl:65 stays inert (prefix is SLACK_TRANSPORT__); TASK-111.9 removes it.

## Blast radius and rollback
- production.toml missing enabled = true: the app boots healthy with Slack off (slack_disabled_skipping_init) and the circuit breaker does not catch it. Guards: the production file pin test; post-deploy checks for slack_app_initialized, the socket-mode notice, configured_systems_built listing slack, and no slack_disabled_skipping_init.
- A rule rejecting the production shape fails boot; the circuit breaker rolls back. Guarded by the production-shape test.
- Legacy command names change if the prefix contract is wrong: production prefix "" (/sre, /aws...). Guarded by the registration tests and the TASK-36 legacy surface suite.
- One git revert restores service: the previous image reads SLACK_ENABLED from the blob, which stays until TASK-111.15.1/111.15.2.

## Deploy order and human steps
- Before merge: nothing in AWS or SSM; do not touch the blob SLACK_ENABLED line (the rollback image needs it). Run zsh /workspace/tmp/deploy-checks.zsh pre at merge for the rollback image tag.
- After deploy: post-deploy checks as above (extend deploy-checks.zsh: no slack_disabled_skipping_init; socket-mode notice still once per task; legacy /sre answers, manual). After PASS: delete the Codespaces secret SLACK_ENABLED; edit app/.env.example:26.
- After merge: refresh the TASK-111.9 plan (B4, B5, B8 interim enabled wording, T-B6, the constants block) and TASK-26.2 (transport settings already in server/slack/, infrastructure/slack/ already gone).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-23 implemented (TDD). The [slack_transport] slice moved to server/slack/settings.py with enabled (false in base, true in production.toml and local.toml) and socket_mode (true, base only); app/infrastructure/slack/ is deleted. The configuration phase builds the slice, runs validate_slack_transport (server/configuration/host_configuration.py) and installs SlackTransportInfo (contracts/slack/transport.py, HostInfo pattern); the five legacy modules read the prefix from it. Rule messages name keys through a SlackKey StrEnum (constants named *_TOKEN_KEY tripped ruff S105), which TASK-111.9 renames. The provider takes enabled, socket_mode and command_prefix from lifespan (get_slack_provider is keyword-only) and passes socket_mode to LegacySlackBootstrap.create_app(socket_mode=...); its import-linter ignore entry left contracts (a) and (d), and infrastructure.slack left contract (k)'s source list. SlackSettings keeps only the blank-team-id check; a stale SLACK_ENABLED or SLACK_SOCKET_MODE is inert (extra=ignore). The vendor-switch allowlist is gone. Not done from the plan: the enterprise-id-only tenant test, because SlackTenant has no enterprise_id until TASK-157 (the rule reads only slack.tenant). Test churn: stale enabled/socket_mode attributes dropped from SimpleNamespace test doubles; the root conftest installs SlackTransportInfo per test. ADR current-state text updated (transport-slack, platform-transports, platform-entrypoints, configuration, plugins, lifecycle) and doc-14 row SLACK_ENABLED. Gates: ruff All checks passed; make check-import-contracts 12 kept, 0 broken; make check-settings-key-ownership OK; pytest tests --ignore=tests/smoke 5686 passed; mypy 47 errors in 18 files, none on a changed line (touched files modules/role/role.py:322 and modules/incident/incident.py:121 are pre-existing). Developer note: local.toml now runs the transport, so a Codespace without Slack credentials sets SLACK_TRANSPORT__ENABLED=false in app/.env. Human after deploy PASS: delete the Codespaces secret SLACK_ENABLED, remove app/.env.example:26.

2026-10-23 deployed: #1786 (abfcd82a) on sre-bot-task:44; post-transport PASS (/workspace/tmp/deploy-checks/post-transport-20261023T222227Z.txt). Codespaces secret SLACK_ENABLED deleted.
<!-- SECTION:NOTES:END -->
