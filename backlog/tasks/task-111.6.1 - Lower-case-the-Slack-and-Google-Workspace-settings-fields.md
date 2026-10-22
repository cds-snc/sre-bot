---
id: TASK-111.6.1
title: Lower-case the Slack and Google Workspace settings fields
status: Done
assignee: []
created_date: '2026-10-21T21:01:00Z'
updated_date: '2026-10-22T12:49:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.6
references:
  - decisions/configuration.md
parent_task_id: TASK-111.6
ordinal: 427000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical, first of two PRs for TASK-111.6. SlackSettings, GoogleWorkspaceSettings and GoogleResourcesConfig (integrations/slack/settings.py, integrations/google_workspace/settings.py) get case_sensitive=False and lower snake_case fields; every reader follows. Environment names do not change: an alias equal to the upper-cased field name is dropped (all Google Workspace field aliases), an alias that differs is kept (every Slack alias, and GOOGLE_RESOURCES) for 111.9 and 111.10 to delete when they move the slice onto the files. Rows for the slice's doc-14 production names are added to the existing pin file.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 SlackSettings, GoogleWorkspaceSettings and GoogleResourcesConfig declare lower snake_case fields with case_sensitive=False and read the same environment names as before; only aliases equal to the upper-cased field name are dropped
- [x] #2 No behaviour change: existing tests pass with attribute renames only (stand-ins and Mock/SimpleNamespace attributes follow the rename)
- [x] #3 test_configuration_settings_production_names.py gains a row for every Slack and Google Workspace environment name in doc-14 and the deploy interface, each set to a non-default sentinel that reaches the renamed field
- [x] #4 No reader in app/, bin/, terraform/ or .github/ uses an old attribute name (rg check recorded in the notes)
- [x] #5 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.6.1 (Slack + Google Workspace, mechanical, one PR). Gate: 9 production files, ~110 changed production LOC, one subsystem (integrations plus 3 reader files in packages/infrastructure, names only), no behaviour change. In gate. Line numbers re-verified 2026-10-21 on main (TASK-111.5.1 is merged).

== Dependency on 111.5.1 (decided) ==
No Waits-on. 111.5.1 is merged: InfrastructureSettings is already case_sensitive=False and test_configuration_settings_production_names.py exists. This slice EXTENDS that file. The base flip is NOT a prerequisite for the code here: SlackSettings, GoogleWorkspaceSettings and GoogleResourcesConfig (and every other vendor slice) inherit pydantic_settings.BaseSettings directly with their own model_config (case_sensitive=True today), not InfrastructureSettings or FeatureSettings. The flip therefore widened none of them; each slice flips its own model_config line here. Verified by reading integrations/*/settings.py (all 9 files).

== Call sites (path:line) ==
Slack (SlackSettings, integrations/slack/settings.py; all 13 fields upper-case, ALL aliases differ from the name, so none dropped):
- settings.py:56 model_config case_sensitive=True -> False; fields :59-92 (ENABLED, SOCKET_MODE, TEAM_ID, BOT_TOKEN, USER_TOKEN, APP_TOKEN, SIGNING_SECRET, REQUEST_TIMEOUT_SECONDS, RETRY_MAX_ATTEMPTS, TRANSIENT_RETRY_AFTER_SECONDS, UNAUTHORIZED_ERRORS, NOT_FOUND_ERRORS, TRANSIENT_ERRORS); property tenant :112-114; field_validator("TEAM_ID") :118 (string key: must be renamed with the field, a stale name raises PydanticUserError at class creation); model_validator body :122-133 (error text keeps SLACK_* env spelling).
- integrations/slack/client.py:40,55 retry_max_attempts; :42,57 user_token/bot_token; :43,58 request_timeout_seconds; :77,79,81 the three error lists; :86 transient_retry_after_seconds
- integrations/slack/provider.py:245,246 socket_mode/enabled; :279,282,290,297,317,320,329,505,507 socket_mode/enabled/app_token/bot_token
- integrations/slack/bootstrap.py:59,79 socket_mode; :61,81 bot_token
- packages/oncall_sync/adapters/slack.py:140 get_slack_settings().user_token
Google Workspace (integrations/google_workspace/settings.py; all 6 aliases equal the upper-cased field name, ALL dropped):
- :64 model_config; fields :68-80 (GOOGLE_DELEGATED_ADMIN_EMAIL, SRE_BOT_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE, GOOGLE_API_NUM_RETRIES, GOOGLE_API_TIMEOUT_SECONDS gt=0 kept); tenant property :88-95; field_validator("GOOGLE_WORKSPACE_CUSTOMER_ID") :98 (string key, rename); model_validator :103-114 (messages keep env spelling). Docstring :43-45 usage example reads settings.GOOGLE_DELEGATED_ADMIN_EMAIL: update.
- GoogleResourcesConfig :213 model_config case_sensitive=True -> False; field `resources` keeps alias GOOGLE_RESOURCES (differs: kept for TASK-111.10, which turns it into a table; TASK-158 deletes the class). Its 17 properties are already lower case. Note getattr(self, "resources", {}) in _get_resource is a string key of a field NOT renamed.
- integrations/google_workspace/client.py:151 sre_bot_email; :166 google_api_timeout_seconds; :169 google_api_num_retries
- infrastructure/directory/factory.py:57 workspace_settings.sre_bot_email
- packages/talent/adapters/google_drive.py:15 sre_bot_email
- No production reader of GOOGLE_DELEGATED_ADMIN_EMAIL / GOOGLE_WORKSPACE_CUSTOMER_ID / GCP_SRE_SERVICE_ACCOUNT_KEY_FILE as attributes (server/configured_systems.py:58-59 passes the object and reads tenant).
- GoogleResourcesConfig readers (get_google_resources_config, 11 prod files, features/incident/*, modules/*) use the lower-case properties: untouched.
Per-vendor counts: Slack 4 reader files / 28 reads; Google 3 reader files / 6 reads; settings self-refs Slack 22, Google 25.
Sweep results (app/, app/bin/, terraform/, .github/): no model_copy, getattr/setattr, patch.object or model_dump-key use of these fields in production code. terraform/ and .github/ contain only ENV NAMES (GCP_SRE_SERVICE_ACCOUNT_KEY_FILE via ecs.tf:31, ci_code.yml:84 SRE_BOT_EMAIL), unchanged. app/bin/check_settings_key_ownership.py is AST-based and already case-folds (claims lower-cased :424,:429); it derives env names from alias or field name, so dropped Google aliases fold to the same key; ALLOWED_VENDOR_SWITCHES {"SLACK_ENABLED"} :66 and the vendor-enabled rule :481 key on the alias, which is kept. No checker edit.
String-key / stand-in forms in TESTS that must follow (they would hide or break, R1-style):
- tests/unit/integrations/slack/conftest.py:~42-52 MockSlackSettings sets self.ENABLED/SOCKET_MODE/APP_TOKEN/BOT_TOKEN/SIGNING_SECRET -> lower-case attrs (this stand-in is what makes a missed provider rename fail loudly).
- SimpleNamespace(ENABLED=..., SOCKET_MODE=..., APP_TOKEN=..., BOT_TOKEN=...): tests/integration/legacy_surface/conftest.py:163; tests/integration/server/test_lifespan_sre_single_registration.py:29; tests/unit/server/plugins/test_server_plugins_slack_listener_scoping.py:74; tests/unit/integrations/slack/test_slack_provider_{reply_views:34,scope_opener:19,listener_registration:57,reply_classifies_errors:41}.py; tests/unit/features/incident/comms/test_incident_comms_status_update_dispatch.py:32 (vendor Slack stand-in; confirm).
- tests/unit/integrations/google_workspace/test_google_workspace_client.py:427 SimpleNamespace(SRE_BOT_EMAIL, GOOGLE_API_NUM_RETRIES); tests/unit/infrastructure/directory/test_factory.py:123 lambda SimpleNamespace(SRE_BOT_EMAIL="").
- tests/unit/integrations/google_workspace/test_google_workspace_settings_load.py:19-24 string field-name list (getattr form): read and lower-case the attribute side only.
- tests/unit/integrations/slack/test_slack_settings.py:224 negative hasattr on INCIDENT_CHANNEL / SLACK_SECURITY_USER_GROUP_ID: leave (env-spelling names of absent fields; stays meaningful).
Other test files with attribute reads (rename reads only; setenv names, alias kwargs such as SlackSettings(SLACK_ENABLED=False) and match= error text stay): unit/integrations/slack/{test_slack_settings.py (29), test_slack_provider.py (11), test_slack_settings_team_id_validate.py (4), test_slack_auto_registration.py (4), test_slack_bootstrap.py:36, slack/conftest.py}; unit/integrations/google_workspace/{test_google_workspace_settings_load.py (22), test_google_workspace_client.py (15), test_google_workspace_settings_customer_id_validate.py (11)}; integration/server/test_lifespan_vendor_slice_validation.py (9); unit/server/test_server_configured_systems_read.py (7); unit/packages/oncall_sync/test_oncall_sync_providers.py (6); tests/factories/slack_bolt.py (5); integration/modules/sre/conftest.py (5); unit/infrastructure/configuration/test_settings.py (4); unit/bin/test_bin_settings_key_ownership_check.py (4; re-derives SlackSettings against pydantic at :527-552, must still pass, aliases unchanged).

== Widened env reads (checked) ==
No field on these classes is a lower-case name without an alias today (all 19 are upper-case; Slack all aliased, Google aliased), so unlike 111.5.1's startup_preload_groups nothing begins reading a NEW name. What widens is case only: aliases and names now match in any case (e.g. slack_enabled, sre_bot_email, google_workspace_customer_id). Probed (pydantic-settings, case_sensitive=False, alias kept): SLACK_ENABLED read; slack_enabled read; the bare field-name env ENABLED is NOT read; a field-name keyword (enabled=True) is NOT accepted (same as today). Dropped-alias Google fields: the upper-case env name is read, upper-case constructor keyword accepted. Conclusion: no new required name; collision risk is only an env var differing in case from a vendor name; rg of terraform/.github/entry scripts found none.

== Ordered steps ==
1. (failing first) Extend app/tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py (imports SlackSettings, GoogleWorkspaceSettings, GoogleResourcesConfig). Add PRODUCTION_NAMES rows (settings class, env name, attribute, raw, expected), non-default sentinel of the right type:
   Slack (doc-14 production names first): SLACK_TEAM_ID "TSENTINEL1" -> team_id; SLACK_BOT_TOKEN "xoxb-sentinel" -> bot_token; SLACK_USER_TOKEN "xoxp-sentinel" -> user_token; SLACK_APP_TOKEN "xapp-sentinel" -> app_token. Deploy-interface names not set in production: SLACK_SOCKET_MODE "false" -> socket_mode False (default True); SLACK_SIGNING_SECRET "sentinel-secret" -> signing_secret; SLACK_REQUEST_TIMEOUT_SECONDS "17" (default 10); SLACK_RETRY_MAX_ATTEMPTS "5" (default 2); SLACK_TRANSIENT_RETRY_AFTER_SECONDS "41" (default 30); SLACK_UNAUTHORIZED_ERRORS '["sentinel_unauth"]'; SLACK_NOT_FOUND_ERRORS '["sentinel_missing"]'; SLACK_TRANSIENT_ERRORS '["sentinel_transient"]'.
   Google (doc-14): GOOGLE_DELEGATED_ADMIN_EMAIL "admin@sentinel.example" -> google_delegated_admin_email; SRE_BOT_EMAIL "bot@sentinel.example" -> sre_bot_email. Deploy interface: GOOGLE_API_NUM_RETRIES "7" (default 3); GOOGLE_API_TIMEOUT_SECONDS "12.5" (default 10.0). GOOGLE_RESOURCES '{"inc":{"d":"sentinel-drive"}}' on GoogleResourcesConfig -> resources == {"inc": {"d": "sentinel-drive"}} (alias kept).
   Dedicated tests (the table is one env var per row, these need companions, so they do not fit it): (a) SLACK_ENABLED "true" together with SLACK_TEAM_ID and SLACK_APP_TOKEN -> enabled True (the transport validator needs the pair; docstring says why); (b) GOOGLE_WORKSPACE_CUSTOMER_ID "C0sentinel" together with GCP_SRE_SERVICE_ACCOUNT_KEY_FILE '{"type":"service_account"}' -> both fields set and tenant not None (the validator rejects either alone); (c) lower-case env spelling accepted for one Slack alias (slack_bot_token) and one Google name; (d) the old bare-name env (ENABLED) is not read. Update the module docstring: add which of these names production sets (SLACK_APP_TOKEN, SLACK_BOT_TOKEN, SLACK_ENABLED, SLACK_TEAM_ID, SLACK_USER_TOKEN, GOOGLE_DELEGATED_ADMIN_EMAIL, GOOGLE_RESOURCES, GOOGLE_WORKSPACE_CUSTOMER_ID, SRE_BOT_EMAIL, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE per doc-14 and ecs.tf:31). Run: renamed-attribute rows fail with AttributeError until steps 2-4 (red state). No task ids in docstrings.
2. integrations/slack/settings.py: case_sensitive=False; rename the 13 fields to lower snake_case, keep every alias; field_validator("team_id"); property and validator bodies read the lower-case attrs; error text keeps SLACK_* spelling; module docstring env names stay.
3. integrations/google_workspace/settings.py: GoogleWorkspaceSettings case_sensitive=False, 6 fields renamed, `alias=` removed where equal to the upper-cased name (keep gt=0 and description kwargs); field_validator("google_workspace_customer_id"); tenant and validator bodies; docstring example. GoogleResourcesConfig: case_sensitive=False only (field and alias unchanged).
4. Readers: slack/client.py, slack/provider.py, slack/bootstrap.py, packages/oncall_sync/adapters/slack.py:140, google_workspace/client.py:151,166,169, infrastructure/directory/factory.py:57, packages/talent/adapters/google_drive.py:15. Nothing else in those files.
5. Existing tests, attribute renames only (see lists above). Stand-ins and Mock attrs lower-cased; setenv names, alias kwargs, match= strings unchanged. Read each file before editing.
6. Gates from /workspace/app: uv run ruff check .; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (no new errors in touched files; pydantic plugin accepting alias kwargs is unchanged); uv run pytest tests --ignore=tests/smoke; make check-import-contracts; make check-settings-key-ownership.
7. AC4 sweep recorded in notes: rg -n '\.(ENABLED|SOCKET_MODE|TEAM_ID|BOT_TOKEN|USER_TOKEN|APP_TOKEN|SIGNING_SECRET|REQUEST_TIMEOUT_SECONDS|RETRY_MAX_ATTEMPTS|TRANSIENT_RETRY_AFTER_SECONDS|UNAUTHORIZED_ERRORS|NOT_FOUND_ERRORS|TRANSIENT_ERRORS|GOOGLE_DELEGATED_ADMIN_EMAIL|SRE_BOT_EMAIL|GOOGLE_WORKSPACE_CUSTOMER_ID|GCP_SRE_SERVICE_ACCOUNT_KEY_FILE|GOOGLE_API_NUM_RETRIES|GOOGLE_API_TIMEOUT_SECONDS)\b' over app/ plus quoted getattr/model_copy/patch.object/monkeypatch.setattr string forms, with terraform/ .github/ app/bin/; remaining hits must be AWS/other-class collisions (RETRY_MAX_ATTEMPTS, TRANSIENT_RETRY_AFTER_SECONDS, AWS_REGION belong to AWSSettings/RetrySettings, 111.6.2), env strings, docstrings, kwargs.
8. Final --notes: files, test counts, rg output, post-deploy checklist, rollback.

== AC -> step -> test (and back) ==
AC1 -> steps 2-4 -> pin rows + dedicated tests, test_slack_settings.py, test_google_workspace_settings_load.py.
AC2 -> step 5 -> the existing suites listed.
AC3 -> step 1 -> test_configuration_settings_production_names.py (red first).
AC4 -> step 7. AC5 -> step 6.
Reverse: 2-4 -> AC1; 5 -> AC2; 1 -> AC3; 6 -> AC5; 7 -> AC4. No unmapped step.

== Test matrix ==
Happy: every doc-14 and deploy-interface Slack/Google name reaches its field. Default: unset env keeps defaults (existing). Boundary: lower-case spelling accepted; bare field-name env not read; dropped-alias Google uppercase keyword accepted. Failure: SLACK_ENABLED without team id / app token, signing secret missing in HTTP mode, blank team id, customer id my_customer or key missing, GOOGLE_API_TIMEOUT_SECONDS<=0 still raise with env-spelled messages (existing). Wiring guard: MockSlackSettings/SimpleNamespace stand-ins with lower-case attrs make a missed reader rename an AttributeError in provider/bootstrap/client tests; test_lifespan_vendor_slice_validation proves boot validation still names the env variables. Authorization/idempotency: n/a.
Files: tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py (extended) plus the edits above.

== Validation against ADRs and downstream rows ==
decisions/configuration.md: lower snake_case fields equal the TOML keys, no per-field aliases as end state; this PR removes only aliases equal to the name and adds none. Kept aliases and the row that deletes each:
- 111.9 (Slack): ALL 13 Slack aliases (SLACK_ENABLED, SLACK_SOCKET_MODE, SLACK_TEAM_ID, SLACK_BOT_TOKEN, SLACK_USER_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET, SLACK_REQUEST_TIMEOUT_SECONDS, SLACK_RETRY_MAX_ATTEMPTS, SLACK_TRANSIENT_RETRY_AFTER_SECONDS, SLACK_UNAUTHORIZED_ERRORS, SLACK_NOT_FOUND_ERRORS, SLACK_TRANSIENT_ERRORS). 111.9 moves the slice to env_prefix SLACK__ / [slack] and [slack.tenant], renaming team_id into the tenant entry; secrets arrive as SLACK__BOT_TOKEN etc. from TASK-111.4 SSM parameters.
- 111.10 (Google): GOOGLE_RESOURCES alias on GoogleResourcesConfig.resources. 111.10 makes it the [google_resources] table. 111.10 also renames the dropped-alias fields to the TOML keys delegated_admin_email and customer_id (doc-14 destinations [google_workspace] delegated_admin_email, [google_workspace.tenant] customer_id); because no alias remains it renames fields and moves env names in one step, as it must anyway.
Settings partitioning respected (no aggregator growth), import boundaries unchanged. 111.9 and 111.10 depend on 111.6.1 (rewired 2026-10-21, human approved).

== Assumptions (verify) ==
A1 Vendor slices do not inherit InfrastructureSettings: verified by reading all nine settings.py (each declares BaseSettings + own model_config).
A2 Alias match is case-insensitive under case_sensitive=False, the bare field name is not read: probed 2026-10-21 (pydantic-settings, this repo's venv); the pin tests assert it.
A3 Production sets only the doc-14 names; verify before merge with aws ecs describe-task-definition (environment/secrets names) and the .env keys in the SSM parameters sre-bot-config and sre-bot-config-infrastructure. GCP_SRE_SERVICE_ACCOUNT_KEY_FILE arrives via task-definition secrets (terraform/ecs.tf:31).
A4 Upper-case constructor kwargs for dropped-alias fields remain valid (111.5.1 probe A1); pinned.
A5 test_google_workspace_settings_load.py:19-24 list is a field-name list used with getattr: verify by reading before editing; if it is an env-name list nothing changes.
A6 test_incident_comms_status_update_dispatch.py:32 SimpleNamespace is a Slack settings stand-in: verify by reading.
A7 No log consumer or metric filter keys on these field names (111.5.1 comment #2: filters match error/exception/warning text only; these slices are not logged via model_dump, only SlackSettings fields via the provider bind socket_mode= which is a log key and unchanged).

== Blast radius and rollback ==
Merging to main deploys. No ECS deployment circuit breaker and the :latest image until TASK-111.16, so nothing rolls back automatically. Failure modes: (1) a missed reader raises AttributeError on first use. The Slack provider does it at transport start (loud: plugin boot or slack listener fails), but several reads are lazy and do NOT fail boot: slack/client.py error classification and timeouts, oncall_sync user_token (job runs later), google_workspace/client.py retries/timeout, directory factory sre_bot_email, talent google_drive sre_bot_email. (2) a stale field_validator name fails at import (loud). (3) a dropped Google alias that no longer matches would silently fall back to defaults: customer id/key -> tenant None, admin/sre_bot email "" (quiet; pin tests are the guard). Rollback: one git revert restores code but needs merge+deploy; faster is the manual retag of the previous <sha>-<date> image as latest and a forced new ECS deployment. No terraform or env change, no ordering constraint; ships alone, before 111.9/111.10.

== Post-deploy checklist (also goes in the notes) ==
1. build_and_deploy posts its Slack success message.
2. aws ecs describe-services: exactly one PRIMARY deployment, rolloutState COMPLETED.
3. /ecs/sre-bot-app after the new task starts: no plugin_boot_failed, no ERROR level in the first minutes.
4. Slack (boot would succeed even if a read were wrong only for lazy paths): the slack transport logs its socket-mode start (provider socket_mode bind) with no slack_* warning; one Slack slash command in the test channel responds (exercises bot_token, request timeout, error classification).
5. Slack user token path: trigger or wait for the oncall sync job (or invoke the sync adapter) and confirm no AttributeError and no slack unauthorized; /ecs/sre-bot-app shows no 'user_token' error.
6. Google: one action that uses the Google client (a directory/group lookup or the access sync that calls the workspace directory) returns data, proving sre_bot_email, delegated credentials, retries and timeout are read; the logs show no 'AttributeError' or google authorization error. Also confirm GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_WORKSPACE_CUSTOMER_ID are still present in the task definition/SSM so the tenant entry is non-None (log line for the configured systems at lifespan).
7. Talent drive adapter and GOOGLE_RESOURCES readers (incident drive/folder) are unchanged code: spot check only if an incident flow runs.
Rollback on any failure: retag the previous <sha>-<date> image as latest and force a new ECS deployment; then revert the merge.

== Decisions (human, 2026-10-21) ==
D1 GoogleResourcesConfig flips to case_sensitive=False here: no impact (only a lower-case google_resources variable would newly match; nothing sets one in app/.env.example, terraform, .github or the SSM .env). Field and alias unchanged.
D2 Dependencies: 111.9 and 111.10 wait on 111.6.1; 111.11 and 111.12 on 111.6.2.
D3 AWSSettings.SERVICE_ROLE_MAP is renamed service_role_map in 111.6.2 (PEP 8: methods and instance attributes are lower_case; only constants are upper case). Not in this PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-21. 9 production files, no behaviour change; environment names unchanged.

Production files: integrations/slack/{settings,client,provider,bootstrap}.py, integrations/google_workspace/{settings,client}.py, infrastructure/directory/factory.py, packages/oncall_sync/adapters/slack.py, packages/talent/adapters/google_drive.py. Kept: all 13 Slack aliases (SLACK_*) for 111.9; GoogleResourcesConfig field resources and its GOOGLE_RESOURCES alias (case_sensitive=False only) for 111.10. Dropped: the six GoogleWorkspaceSettings aliases equal to the upper-cased field name (gt=0 and description kept). Both field_validator string keys renamed (team_id, google_workspace_customer_id). Validator messages, log labels and docstrings keep the environment spelling; the usage-example docstring reads settings.google_delegated_admin_email.

Tests: extended tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py: 16 new table rows (Slack 11 + Google 4 + GOOGLE_RESOURCES, each a non-default sentinel; SLACK_ENABLED covered by a dedicated test) and 5 dedicated tests (SLACK_ENABLED with team id and app token; Google customer id with key builds the tenant; lower-case spelling of slack_bot_token and sre_bot_email; bare ENABLED not read; upper-case SRE_BOT_EMAIL keyword accepted). Red first: 21 failed, 30 passed (AttributeError on renamed attributes). Green after: 51 passed. Existing tests: attribute renames only (SimpleNamespace/Mock/class stand-ins, model_construct keyword names, attribute reads) across 23 files; setenv/delenv names, SLACK_* alias kwargs, match= env strings unchanged. A5 resolved: the list in test_google_workspace_settings_load.py:19-24 is env names for delenv (unchanged); A6 resolved: test_incident_comms_status_update_dispatch.py:32 is a Slack settings stand-in (renamed).

Deviations from "attribute renames only" (3 assertions, all forced by the flip):
- test_google_workspace_resources_load.py and test_google_workspace_settings_load.py: the case_sensitive config assertion flipped True -> False (tests renamed ..._case_insensitively_...), as the plan decided (D1).
- test_google_workspace_settings_load.py test_a_non_positive_timeout_fails_naming_the_key: the pydantic field-constraint error now reports the field name (google_api_timeout_seconds) because the alias is dropped, so the message no longer contains the upper-case env spelling. match= made case-insensitive ((?i)GOOGLE_API_TIMEOUT_SECONDS). Operator-visible: that one validation error shows the lower-case name; env reading is case-insensitive so the variable is the same.
- test_slack_settings.py: the repr assertion "USER_TOKEN" not in repr became "user_token" (the field name in repr), otherwise it would pass vacuously.

Gates (from app/): ruff check . -> All checks passed!; pytest tests --ignore=tests/smoke -> 5553 passed; mypy . --exclude ... -> Found 47 errors in 18 files (same count as main, none in a touched file); make check-import-contracts -> Contracts: 12 kept, 0 broken; make check-settings-key-ownership -> OK: every settings key and configuration table has one owner, ...

AC4 sweep: rg for .NAME over app/ terraform/ .github/ (all 19 old names) returns only AWS collisions (integrations/aws/client.py:160,210 AWSSettings RETRY_MAX_ATTEMPTS/TRANSIENT_RETRY_AFTER_SECONDS; tests/unit/integrations/aws/test_aws_settings_fields.py:33,76,81; test_incident_core_status_update_store.py:513 get_aws_settings(); all 111.6.2) and env-name secrets in .github (ci_code.yml:84 SRE_BOT_EMAIL, tf_apply.yml:17 and tf_plan.yml:14 GCP_SRE_SERVICE_ACCOUNT_KEY_FILE). The quoted getattr/setattr/model_copy/patch.object/monkeypatch.setattr string-form rg returns nothing. Remaining upper-case tokens in tests are setenv/delenv names, match= strings, docstrings, module constants (TEAM_ID, BOT_TOKEN in tests/factories) and env-name lists.

Found during implementation: GoogleWorkspaceSettings constraint errors now name the lower-case field (see deviations). Nothing else; no checker edit (check_settings_key_ownership folds case).

Post-deploy checklist (merging to main deploys; no circuit breaker, :latest until TASK-111.16; macOS commands, region ca-central-1):
1. build_and_deploy posts its Slack success message.
2. aws ecs describe-services --cluster sre-bot-cluster --services sre-bot-service --region ca-central-1 --query 'services[0].deployments[].[status,rolloutState,runningCount]' --output text  -> exactly one PRIMARY, COMPLETED.
3. aws logs tail /ecs/sre-bot-app --since 15m --region ca-central-1 | grep -Ei 'plugin_boot_failed|"level": "error"|AttributeError'  -> no output.
4. Slack boot: aws logs tail /ecs/sre-bot-app --since 15m --region ca-central-1 | grep -Ei 'socket_mode|slack' | grep -Ei 'warn|error|unauthor'  -> no hits; then one Slack slash command in the test channel responds (exercises bot_token, timeout, error classification).
5. Slack user token path (lazy): trigger or wait for the oncall sync job, then aws logs tail /ecs/sre-bot-app --since 30m --region ca-central-1 | grep -Ei "user_token|AttributeError|not_authed|invalid_auth"  -> no hits.
6. Google (lazy): one action using the Google client (directory/group lookup or access sync) returns data; aws logs tail /ecs/sre-bot-app --since 30m --region ca-central-1 | grep -Ei "AttributeError|google.*(unauthorized|forbidden|invalid_grant)"  -> no hits. Confirm GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_WORKSPACE_CUSTOMER_ID are still present (tenant non-None in the configured-systems lifespan log).
7. Talent drive adapter and GOOGLE_RESOURCES readers are unchanged code: spot check only if an incident flow runs.
Rollback on any failure: retag the previous <sha>-<date> image as latest and force a new ECS deployment (aws ecs update-service --cluster sre-bot-cluster --service sre-bot-service --force-new-deployment --region ca-central-1); then revert the merge. No terraform or env change, no ordering constraint.

Review note 2026-10-21: the one operator-visible change, a GOOGLE_API_TIMEOUT_SECONDS constraint error now locating the field as google_api_timeout_seconds, is the same class of change the human accepted for 111.5.1 (lower-case field names in ValidationError locations, comment #2 there). Gates re-run independently after the last edits: ruff All checks passed; mypy 47 errors in 18 files (main baseline, none in touched files); pytest 5553 passed; import contracts 12 kept, 0 broken; settings key ownership OK.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-21T21:09:00Z

---

Plan approved by the human 2026-10-21: (1) SERVICE_ROLE_MAP renamed service_role_map in 111.6.2 (PEP 8), not here; (2) file-gate exception for 111.6.2 accepted; (3) 111.9/111.10 depend on 111.6.1, 111.11/111.12 on 111.6.2 (applied); (4) GoogleResourcesConfig flips to case_sensitive=False (no impact verified); (5) ACs of 111.6 and 111.6.2 updated to match.

---

created: 2026-10-21T21:14:00Z

---

Pre-merge name check (A3), 2026-10-21, human-run: task definition environment = CORS_ALLOWED_ORIGINS, BACKEND_URL, FORWARDED_ALLOW_IPS, SLACK__COMMAND_PREFIX, ENVIRONMENT; secrets = GCP_SRE_SERVICE_ACCOUNT_KEY_FILE plus the eleven 111.4 names (SLACK__APP/BOT/USER_TOKEN, GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY, OPENAI__API_KEY, NOTIFY__SRE_USER_NAME/CLIENT_SECRET, OPSGENIE__INTEGRATIONS_KEY, SENTINEL__SHARED_KEY, TRELLO__APP_KEY/TOKEN). All appear in doc-14. The new double-underscore names are not read by any slice yet (111.9/111.10 switch to them). Still pending: the Slack/Google keys in the SSM .env files sre-bot-config and sre-bot-config-infrastructure, which are what the slices read today.

---

created: 2026-10-21T21:20:00Z

---

Pre-merge name check (A3), SSM .env part, 2026-10-21 (human-run, names only): sre-bot-config = GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DELEGATED_ADMIN_EMAIL, GOOGLE_RESOURCES, GOOGLE_WORKSPACE_CUSTOMER_ID, SLACK_ENABLED, SRE_BOT_EMAIL; sre-bot-config-infrastructure = SLACK_NOTIFY_MGMT_USER_GROUP_ID, SLACK_TEAM_ID, SLACK_USER_TOKEN. Every name is in doc-14. Discrepancy: doc-14 also lists SLACK_APP_TOKEN, SLACK_BOT_TOKEN, SLACK_TOKEN and SLACK_SECURITY_USER_GROUP_ID under sre-bot-config, and the name extraction (^NAME=) did not find them. Pending a looser check (leading whitespace or other formatting). Not a blocker for 111.6.1: env names and the Slack aliases are unchanged here; it matters for 111.9 and 111.15.

---

created: 2026-10-21T21:22:00Z

---

Discrepancy resolved 2026-10-21: SLACK_TOKEN, SLACK_BOT_TOKEN, SLACK_APP_TOKEN and SLACK_SECURITY_USER_GROUP_ID are in sre-bot-config, written with a space before '=' ('NAME =...'), which the ^NAME= extraction skipped. The only reader of .env is pydantic-settings (python-dotenv, entry.sh writes it, nothing shell-sources it), and python-dotenv accepts the space: probed with SlackSettings(_env_file=...) reading 'SLACK_BOT_TOKEN =xoxb-a' and 'SLACK_APP_TOKEN = xapp-b' correctly. doc-14 inventory confirmed complete for Slack and Google.

---
<!-- COMMENTS:END -->
