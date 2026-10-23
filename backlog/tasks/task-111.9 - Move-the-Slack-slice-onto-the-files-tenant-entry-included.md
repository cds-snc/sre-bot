---
id: TASK-111.9
title: Move the Slack slice onto the files, tenant entry included
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-23T17:00:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.1
  - TASK-111.16
  - TASK-111.17
  - TASK-112
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1756
parent_task_id: TASK-111
type: feature
ordinal: 415000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Slack vendor slice (integrations/slack/settings.py) moves onto the configuration files. Non-secret values (timeouts, retry budget, error-code lists) are read from [slack]; the workspace ids from [slack.tenant] (production.toml: the production workspace; local.toml: the shared development workspace; ci.toml: none). The tokens and the signing secret stay fields of the slice, read as SLACK__<FIELD> (SLACK__BOT_TOKEN, SLACK__USER_TOKEN, SLACK__APP_TOKEN, SLACK__SIGNING_SECRET; the production SecureStrings exist, no terraform change), as a single-workspace Bolt app is configured (decisions/configuration.md). A present tenant entry requires the bot token, and any Slack secret set without a tenant entry fails boot naming the key. extra=forbid. The transport keys (enabled, socket_mode) are TASK-112's [slack_transport]; the optional enterprise id is TASK-157's. Production runs Socket Mode with no signing secret and keeps booting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Slack slice reads its non-secret values, the tenant ids included, from the files and its secrets from SLACK__<FIELD> names
- [ ] #2 A present tenant entry missing the bot token fails boot naming the key
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #4 A Slack secret set without a [slack.tenant] entry fails boot naming the key, and the production shape (tenant, bot and app tokens, Socket Mode, no signing secret) boots
- [ ] #5 production.toml [slack.tenant] team_id equals the sre-bot-config SLACK_TEAM_ID, local.toml's equals the development bot's auth.test team_id, and each SLACK__<FIELD> SecureString equals the blob token it replaces
- [ ] #6 The old SLACK_<FIELD> names and SLACK_TEAM_ID are no longer read from the environment or .env, and SLACK__COMMAND_PREFIX in the environment does not fail the Slack slice
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.9 (Slack slice onto the configuration files, tenant entry included). STATUS: PROPOSED; decisions Q1-Q4 settled by the human 2026-10-23 (Decisions, at the end); plan awaiting final review. Order: TASK-111.17, then TASK-112 (owns [slack_transport] enabled and socket_mode and the cross-slice Slack rules), then this task. Written against main 3d1f33bd; re-run every rg below on the post-112 tree before editing; line numbers are for the reviewer.

== Size gate (verdict after the 2026-10-23 split: PASSES) ==
AC #5 moved to TASK-111.17 (human-approved split 2026-10-23), which merges and deploys first; this plan is the former Part B: ~10 prod files incl. TOML/ini, ~150 LOC, one subsystem (the Slack vendor slice).

== Ownership of the overlap (TASK-28.2, TASK-115, TASK-156) ==
- 111.17 (AC #5): only WHEN the existing pipeline is configured: right after identity, file install and [logging], before every other slice. configure_logging takes the environment instead of HostInfo; lifespan stops reconfiguring. A boot failure inside the configuration phase is logged once as a JSON CRITICAL event (Q3).
- TASK-28.2: HOW non-structlog records render: uvicorn/uvicorn.access through ProcessorFormatter for the launch paths (--log-config or handler takeover), single exception rendering (its AC #6), health-check classification. Stays the owner of: uvicorn's own "Error loading ASGI app factory" traceback, the lines before create_app runs, and failures before [logging] loads (missing ENVIRONMENT, unreadable file). 111.17 does not touch handlers beyond what configure_logging already installs (root ProcessorFormatter handler exists today, setup.py:226-239).
- TASK-115: the mechanical move of infrastructure/logging/ to server/logging/. 111.17 edits setup.py in its current home; 115 moves it later (its description already orders it after the pipeline fixes). No change to 115.
- TASK-156: WHAT startup reports (identity event, generated configuration summary, SecretStr typing, WARNING for weakening settings). 111.17 makes 156's summary renderable in the configuration phase but adds no event; _list_configs_from_sections stays. Slack tokens stay str here (repr=False only); SecretStr is 156 AC #3.

== PART B: TASK-111.9 (Slack slice) ==
Context: integrations/slack/settings.py:50-142 SlackSettings is BaseSettings (env_file .env, extra="ignore") with 13 per-field aliases (SLACK_ENABLED, SLACK_SOCKET_MODE, SLACK_TEAM_ID, SLACK_BOT_TOKEN, SLACK_USER_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET, SLACK_REQUEST_TIMEOUT_SECONDS, SLACK_RETRY_MAX_ATTEMPTS, SLACK_TRANSIENT_RETRY_AFTER_SECONDS, SLACK_*_ERRORS x3); tenant is a property derived from team_id. Production (doc-14:66-85): SLACK_ENABLED, SLACK_TEAM_ID and the three tokens in the sre-bot-config blob (.env via entry.sh); SLACK__BOT_TOKEN/USER_TOKEN/APP_TOKEN already injected as task-definition secrets (terraform/ssm.tf:25-27, 111.4); SLACK_SIGNING_SECRET and SLACK_SOCKET_MODE unset (socket mode, default true); SLACK__COMMAND_PREFIX env read by [slack_transport] until 111.15.1.
Readers (field names unchanged, so no reader edit): integrations/slack/client.py:39-76, bootstrap.py:54-81, provider.py:177,245-329,505, server/configured_systems.py:45-58 (.tenant), packages/oncall_sync/adapters/slack.py:140 (.user_token).
Chosen approach:
- SlackSettings(ConfigurationSlice), toml_table_header=("slack",), env_prefix="SLACK__", extra=forbid (base). No per-field alias.
- tenant: SlackTenant | None = None, a real nested field read from [slack.tenant] (team_id; env SLACK__TENANT__TEAM_ID); team_id field and the property removed; SlackTenant strips and rejects a blank team_id. TASK-157 later adds enterprise_id here.
- Tokens bot_token, user_token, app_token, signing_secret stay slice fields, read as SLACK__<FIELD> (no terraform change), all repr=False; empty string counts as unset.
- enabled and socket_mode are not on this slice: TASK-112 moves them to [slack_transport] and the cross-slice rules (transport on needs the tenant entry and bot token; Socket Mode the app token; HTTP the signing secret; the socket-mode notice) to the host configuration phase. This task points those rules at the nested tenant field.
- Production runs Socket Mode with no signing secret anywhere (no blob line, no SSM parameter, no Codespaces secret); a later move to HTTP Events mode adds /sre-bot/SLACK__SIGNING_SECRET through terraform and [slack_transport] socket_mode = false. Nothing here may require it.
- Non-secret values (request_timeout_seconds, retry_max_attempts, transient_retry_after_seconds, three error-code lists) in base.toml [slack]; field defaults equal base.toml.
- Validators (one model_validator, messages name the key): tenant present without bot_token -> "SLACK__BOT_TOKEN is required when [slack.tenant] is set" (AC #2); any of the four secrets set without tenant -> "SLACK__<FIELD> is set but [slack.tenant] team_id is not" (AC #4, signing secret included so Slack is never half configured, Q4); the host rules from TASK-112 read slack.tenant (the nested field) and name SLACK__ keys; the socket-mode notice text names SLACK__SIGNING_SECRET (event name unchanged, Logs Insights keys on it).
Steps (TDD, red first):
B1 Tests (red): T-B1..T-B9.
B2 integrations/slack/settings.py as above; module docstring rewritten (files + SLACK__ names; TASK-112, TASK-157 pointers).
B3 app/config/base.toml: [slack] with the non-secret values (no tenant). production.toml: [slack.tenant] team_id = "<SLACK_TEAM_ID from the G2 output>". local.toml: [slack.tenant] team_id = "<the development bot's workspace id, from auth.test in a Codespace (human step H2)>": every development environment shares one Slack app whose tokens are repository Codespaces secrets. ci.toml: no tenant.
B4 app/pyproject.toml:136-139 pytest env: replace the four SLACK_ lines with SLACK__BOT_TOKEN=, SLACK__USER_TOKEN=, SLACK__APP_TOKEN=, SLACK__SIGNING_SECRET= (empty: overrides a developer's app/.env so the ci run is an unconfigured Slack) and drop SLACK_ENABLED.
B5 (none: TASK-112 empties the vendor-switch allowlist.)
B6 Messages naming old keys: packages/oncall_sync/adapters/slack.py:142 -> SLACK__USER_TOKEN; features/incident/comms/entrypoints/slack.py:23,134 setting="[slack.tenant] team_id"; both READMEs.
B7 Pin file tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py: Slack rows to SLACK__BOT_TOKEN/USER_TOKEN/APP_TOKEN/SIGNING_SECRET and file keys; old names asserted unread.
B8 decisions/configuration.md: :15/:19/:21 current-state lines; tolerated list :100-103 (Slack flat names and derived tenant closed); configuration.md "Values come from checked-in TOML files" gains: local.toml holds the values every development environment shares, the development Slack app's workspace id included; development secrets come from the repository's Codespaces secrets (app/.env off Codespaces) under the production <SLICE>__<FIELD> names; ci.toml configures no vendor tenant and the test run blanks the vendor secrets.; Changes "2026-10-2x: the Slack slice reads [slack] and [slack.tenant]; tokens SLACK__<FIELD>; enabled interim in [slack] (TASK-111.9)". doc-14 rows 66-85 status column.
Tests:
T-B1 tests/unit/integrations/slack/test_slack_settings.py (rewrite on installed tmp files): values from [slack]; tenant from [slack.tenant]; tokens from SLACK__ env; old SLACK_BOT_TOKEN/SLACK_TEAM_ID in env and .env are ignored (AC #1).
T-B2 same: tenant without SLACK__BOT_TOKEN fails naming SLACK__BOT_TOKEN (AC #2).
T-B3 same, parametrized over the four secrets: set without tenant fails naming the key (AC #4).
T-B4 same: unknown key in [slack] and in [slack.tenant] fails naming file, table and key (extra=forbid); blank team_id fails.
T-B5 same: SLACK__COMMAND_PREFIX in os.environ and in .env does not fail the Slack slice (production carries it until 111.15.1).
T-B6 same: the production shape (tenant, bot and app tokens, no signing secret, Socket Mode) boots and logs the notice naming SLACK__SIGNING_SECRET; the local shape (local.toml tenant + Codespaces-style SLACK__ tokens) boots; the host rules from TASK-112 still fail on the nested tenant field (test_slack_settings_team_id_validate.py folded in and deleted).
T-B7 tests/unit/infrastructure/configuration/test_configuration_files_slack_tenant.py: the real files give production tenant team_id equal to the recorded id, local tenant equal to the development id, ci no tenant; no file holds a token.
T-B8 tests/integration/server/test_lifespan_vendor_slice_validation.py: invalid Slack entry fails boot through load_host_configuration naming the key; absent entry with tokens absent boots.
T-B9 call-site tests that build SlackSettings(team_id=...) move to tenant=SlackTenant(...) (bootstrap, client factory, configured_systems, oncall_sync providers, incident comms, app_state, contracts slice load, key-ownership check).
AC -> step -> test: #1 B2,B3,B4 / T-B1,T-B7 ; #2 B2 / T-B2,T-B8 ; #3 all / gates ; #4 B2 / T-B3 ; #5 B3 / T-B7 + G2, H2 ; #6 B2,B4,B7 / T-B1,T-B5. T-B6 maps to #4. Every test above maps to an AC.
Doubts: (a) pydantic-settings env source with env_prefix SLACK__ + extra=forbid ignores a non-field SLACK__COMMAND_PREFIX -> T-B5 proves it. (b) the ownership check treats [slack.tenant] as part of [slack], as [[security.issuers]] is -> make check-settings-key-ownership. (c) some test silently relied on the pytest env tokens -> red run of the full suite after B4, fixed with explicit kwargs. (d) the SSM SLACK__ values equal the blob's -> G2 match lines; DIFFER blocks the merge.
Blast radius B: production Slack (socket mode connection, every command and incident flow) if a SLACK__ value or the team id is wrong; HTTP stays up and the ECS circuit breaker will not see it (health stays green), so V-slack checks and the manual Slack checks decide rollback. A boot failure (missing key) is caught by the circuit breaker and rolls back automatically. One git revert restores; the previous image reads the unchanged blob, so rollback is safe until 111.15.

== Merge gates (human; G2 and H2 before implementation) ==
H2 Development workspace id, in a Codespace (read-only auth.test with the shared dev bot token; prints no secret): curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test | jq '{ok, team_id, team, enterprise_id}' > /workspace/.claude-state/delivery/task-111.9/local-team.json  (the agent reads it into local.toml, B3).
G1 TASK-111.17 merged, deployed and checks.zsh post-logging PASS before this merges; the branch is cut from main after that merge.
G2 zsh /workspace/.claude-state/delivery/task-111.9/checks.zsh pre (I read the output file): SLACK_ENABLED true; SLACK_TEAM_ID value (goes into production.toml, B3); SLACK_SIGNING_SECRET/SOCKET_MODE and the tuning names unset; BOT/USER/APP "match" for blob vs /sre-bot/SLACK__<FIELD> (any DIFFER or MISSING blocks: set the SSM value through the 111.4 runbook path first); no /sre-bot/SLACK__SIGNING_SECRET; task definition carries the three SLACK__ secrets; baseline notice counts.
G3 Gates green from app/: uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (no new errors in touched files) ; uv run pytest tests --ignore=tests/smoke ; make check-import-contracts ; make check-settings-key-ownership.
G4 app/.env.example edited by the human in the PR (lines under Cleanup); SLACK__BOT_TOKEN and SLACK__APP_TOKEN Codespaces secrets created.
G5 Rollback tag re-read at merge: the pre output's image_tag (expected the sre-bot-task:42 image), recorded in the notes.
G6 Merge outside a running deploy; an admin able to start build_and_deploy from the Actions page is available for 30 minutes.

== Post-deploy checklist (read-only zsh script; output file read by the agent) ==
Run after the build_and_deploy run finishes (~3-4 min plus the alarm bake; the workflow waits up to 15 min; a red sbom job at "Docker generate SBOM" is the known trivy-db rate limit, judge build and deploy):
  zsh /workspace/.claude-state/delivery/task-111.9/checks.zsh post-slack
It writes /workspace/.claude-state/delivery/task-111.9/post-slack-<UTC>.txt: deploy jobs; rollout COMPLETED on a new revision; task-definition names; boot errors since the deployment (Logs Insights through jq, masked samples); non-JSON line count (uvicorn lines expected until 28.2); config_phase_json; Slack up (slack_app_initialized, socket session established, configured_systems_built lists slack, none of slack_disabled_skipping_init / initialization failed / app unavailable / incident_comms_registration_skipped / invalid_auth); /version matches the head sha, /health and / 200. /api/v1/* is not checked (WAF 403 until TASK-163).
Manual Slack checks (human, production workspace): /sre help answers; /sre version (or the incident command list) answers; a message shortcut or the incident declare modal opens. Record pass/fail in the notes.
Rollback on any FAIL: Actions page -> build_and_deploy -> Run workflow, image_tag=<G5 tag> (admin; docs/runbooks/roll-back-a-deployment.md), re-run the script, then revert the merge.

== Cleanup (per location, with timing) ==
- Codespaces secrets (repository-level, shared): BEFORE merge (the running code ignores the new names): gh secret set SLACK__BOT_TOKEN --app codespaces -R cds-snc/sre-bot and gh secret set SLACK__APP_TOKEN --app codespaces -R cds-snc/sre-bot, each value pasted at the prompt from the current SLACK_BOT_TOKEN/SLACK_APP_TOKEN (a running Codespace sees new secrets only after a restart). AFTER the post-deploy PASS: gh secret delete SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_TOKEN, APP_TOKEN, SLACK_DEV_MSG_CHANNEL (--app codespaces -R cds-snc/sre-bot; SLACK_TOKEN, APP_TOKEN and SLACK_DEV_MSG_CHANNEL have no reader in app/). SLACK_ENABLED is TASK-112's to delete. SLACK_WEBHOOK_URL, SLACK_SECURITY_USER_GROUP_ID and SLACK_NOTIFY_MGMT_USER_GROUP_ID belong to other slices (TASK-111.14). Confirm: gh secret list --app codespaces -R cds-snc/sre-bot | grep -E '^SLACK_(BOT|APP)_TOKEN|^APP_TOKEN|^SLACK_TOKEN' prints nothing.
- app/.env.example (agent-unreadable; human, in the PR before merge, G4): delete every SLACK_TEAM_ID, SLACK_BOT_TOKEN, SLACK_USER_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET, SLACK_SOCKET_MODE, SLACK_REQUEST_TIMEOUT_SECONDS, SLACK_RETRY_MAX_ATTEMPTS, SLACK_TRANSIENT_RETRY_AFTER_SECONDS and SLACK_*_ERRORS line; add none (the tenant id and tuning values live in app/config, the tokens come from Codespaces secrets). Confirm: rg -n 'SLACK_(TEAM_ID|BOT_TOKEN|USER_TOKEN|APP_TOKEN|SIGNING_SECRET|SOCKET_MODE|REQUEST_TIMEOUT|RETRY|TRANSIENT|UNAUTHORIZED|NOT_FOUND)' app/.env.example prints nothing.
- app/.env: no change expected (it holds no Slack secret); if a developer kept one there, the same renames apply.
- GitHub Actions secrets: none for the app slice (rg .github shows only SLACK_WEBHOOK_URL, SLACK_SUCCESS_WEBHOOK, SLACK_NOTIFY_WEBHOOK, SLACK_SRE_CHANNEL_WEBHOOK_URL: workflow notifications, unrelated). Nothing to delete. Confirm: gh secret list.
- SSM: blob sre-bot-config lines SLACK_ENABLED, SLACK_TEAM_ID, SLACK_BOT_TOKEN, SLACK_USER_TOKEN, SLACK_APP_TOKEN, SLACK_TOKEN: NO edit (the rollback image reads them); retired with the blob by 111.15.1/111.15.2. /sre-bot/SLACK__* SecureStrings: unchanged; no SLACK__SIGNING_SECRET parameter (create one through terraform only if HTTP mode is ever chosen).
- Task definition: no change in 111.9 (the SLACK__ secrets exist since 111.4). SLACK__COMMAND_PREFIX env goes in 111.15.1 (terraform/templates/sre-bot.json.tpl:65).

== Decisions (settled by the human 2026-10-23) ==
Q1 TASK-112 moves ahead of this task as a whole (it needed nothing from 111.9: the tenant entry exists today, derived from SLACK_TEAM_ID), so no interim key is written and undone: [slack_transport] holds enabled, socket_mode and command_prefix (configuration.md:53), and the cross-slice rules run in the host configuration phase (lifecycle.md:29).
Q2 No per-developer configuration exists: development runs in Codespaces whose secrets are repository-level and shared (gh secret list --app codespaces: SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_ENABLED, no SLACK_TEAM_ID or SLACK_USER_TOKEN). So the development workspace id is a shared non-secret and goes in local.toml, like production's in production.toml; the tokens become SLACK__BOT_TOKEN and SLACK__APP_TOKEN Codespaces secrets. ci.toml has no tenant and the pytest env blanks SLACK__BOT_TOKEN, SLACK__USER_TOKEN, SLACK__APP_TOKEN, SLACK__SIGNING_SECRET, because Codespaces inject the tokens into every process, the test run included (without the blanks AC #4 would fail every ci-environment test in a Codespace). ADR gap closed by the B8 sentence (where development secrets come from).
Q3 (TASK-111.17) accepted.
Q4 All four secrets count for AC #4; the signing secret is absent everywhere today and production keeps booting without it (T-B6 production shape).
Leak found 2026-10-23 (affects this task's tests; fixed in TASK-111.17): a failing model_validator renders input_value={...} with every field, the tokens included, and ConfigurationSlice.__init__ (contracts/configuration.py:151-157) re-raises or chains (from error) that ValidationError, so uvicorn's boot traceback would carry a Slack token to CloudWatch (reproduced with pydantic 2.14.1). T-B2, T-B3 and T-B8 assert the raised text and every log line contain no token value.
<!-- SECTION:PLAN:END -->
