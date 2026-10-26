---
id: TASK-111.10.2
title: >-
  Move the Google Workspace slice onto the files; the delegation subject becomes
  a non-public value
status: To Do
assignee: []
created_date: '2026-10-26T18:29:00Z'
updated_date: '2026-10-26T18:54:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.10.1
references:
  - decisions/configuration.md
parent_task_id: TASK-111.10
type: feature
ordinal: 446000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Google Workspace slice (integrations/google_workspace/settings.py) reads [google_workspace] (api_num_retries, api_timeout_seconds) and its tenant entry from [google_workspace.tenant] customer_id, with the service-account key as GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY and the delegation subject (today's SRE_BOT_EMAIL) as GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL, a non-public value (decisions/configuration.md, 2026-10-26), optional as today. production.toml and local.toml name the tenant, ci.toml none; the test run blanks both variables. google_delegated_admin_email (no reader) is deleted, and the unused Authlib and google-auth-oauthlib dependencies (left from the pickle-string OAuth admin user) are removed. GOOGLE_RESOURCES is not touched (TASK-111.10.3). Which principal and scopes each Google caller should use is TASK-169's; this task only moves names. GCP_SRE_SERVICE_ACCOUNT_KEY_FILE and the sre-bot-config lines stay deployed for the rollback image until TASK-111.15.1 and 111.15.2. Split from TASK-111.10 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Google slice reads its non-secret values, the tenant customer_id included, from the files, its key only as GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY and its delegation subject only as GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL; no configuration file holds a key, an email or a Drive id
- [ ] #2 A tenant entry missing the key, or the key or the delegated user set without a tenant entry, fails boot naming the key; a blank or my_customer customer_id fails boot; no message or log line carries the key or the delegated user's value
- [ ] #3 production.toml's customer_id equals the sre-bot-config value; the two SecureStrings equal the gcp_sre_service_account_key parameter and the SRE_BOT_EMAIL line (pre google: both MATCH)
- [ ] #4 The old names (GOOGLE_DELEGATED_ADMIN_EMAIL, SRE_BOT_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE, GOOGLE_API_NUM_RETRIES, GOOGLE_API_TIMEOUT_SECONDS) are no longer read from the environment or .env; google_delegated_admin_email is deleted
- [ ] #5 Authlib and google-auth-oauthlib are removed from the dependencies (imported nowhere)
- [ ] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployed; zsh bin/deploy-checks.zsh post google PASS and the manual checks recorded
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.10.2 (Google Workspace slice onto the configuration files). Split from TASK-111.10 on 2026-10-26 and narrowed the same day (human): GOOGLE_RESOURCES left for TASK-111.10.3 (after TASK-167 rules on document ids); Drive ids and the delegation subject are non-public values (decisions/configuration.md, 2026-10-26); the credential model itself is TASK-169's. Written against the task-112.4-scheduler tree (3eec058b); branch from main after TASK-111.10.1 merges, its tf_apply and deploy pass and H-A1 has set the delegated user's value; re-run every rg below first.

== Size ==
~11 prod files incl. TOML, workflow, helpers and the generated uv.lock (~+150/-120 LOC), plus configuration.md Changes and doc-14 status. One subsystem (the Google vendor slice). Passes the gate.

== Context (verified 2026-10-26) ==
- integrations/google_workspace/settings.py GoogleWorkspaceSettings: BaseSettings (env_file .env, extra=ignore, no prefix): google_delegated_admin_email (no reader), sre_bot_email, google_workspace_customer_id, gcp_sre_service_account_key_file, google_api_num_retries, google_api_timeout_seconds; tenant derived; one after-validator. GoogleResourcesConfig stays as it is (111.10.3).
- Readers: integrations/google_workspace/client.py:135-169 (tenant, sre_bot_email as the default delegation subject, google_api_*; the not-configured message at :140 names old keys), infrastructure/directory/factory.py:53-57 (tenant, sre_bot_email), packages/talent/adapters/google_drive.py (sre_bot_email, read at use after 111.10.1), server/configured_systems.py:51-59 (tenant.customer_id), server/configuration/host_configuration.py:152.
- Accounts (checked 2026-10-26, kinds only): SRE_BOT_EMAIL and GOOGLE_DELEGATED_ADMIN_EMAIL are cds-snc.ca Workspace users; the key belongs to a GCP service account in project cdssnc that impersonates SRE_BOT_EMAIL through domain-wide delegation for every call unless a caller passes another subject. This task moves names only; TASK-169 decides the principals.
- Production: sre-bot-config lines GOOGLE_WORKSPACE_CUSTOMER_ID, SRE_BOT_EMAIL, GOOGLE_DELEGATED_ADMIN_EMAIL; GOOGLE_API_* unset; /sre-bot/GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY set (111.4) and /sre-bot/GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL set by H-A1 (111.10.1), both injected.
- Development: Codespaces secrets with the old names, plus GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL (111.10.1 H-A1).
- CI: ci_code.yml:79 passes the Actions secret SRE_BOT_EMAIL; pyproject pytest env sets the old key and customer id. Verified: blanking both, 5778 passed (no test needs a tenant).
- Verified empirically: the nested env key deep-merges with [google_workspace.tenant] from the file; pydantic's own errors name the wrong keys and an empty key builds a half tenant, hence the slice's before-validator.
- Pickle-era leftovers: Authlib and google-auth-oauthlib in pyproject dependencies, imported nowhere in app/.

== Chosen approach ==
- GoogleWorkspaceSettings(ConfigurationSlice), toml_table_header=("google_workspace",), env_prefix="GOOGLE_WORKSPACE__", extra=forbid, no alias: api_num_retries, api_timeout_seconds (gt=0), tenant: GoogleWorkspaceTenant | None = None.
- GoogleWorkspaceTenant (frozen, extra=forbid): customer_id (file; stripped; blank or "my_customer" fails), delegated_user_email (env only, non-public; optional as today, empty counts as unset; TASK-169 may replace it with per-role principals, so nothing new requires it), service_account_key (env only, repr=False).
- One mode="before" validator on the slice, messages name the key, never a value: empty env values count as unset; a tenant (customer_id) without the key -> "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY is required when [google_workspace.tenant] is set"; the key or the delegated user set without customer_id -> "GOOGLE_WORKSPACE__TENANT__<FIELD> is set but [google_workspace.tenant] customer_id is not".
- google_delegated_admin_email deleted (no reader).

== Steps (TDD, red first) ==
B1 Tests (red): T-B1..T-B7.
B2 integrations/google_workspace/settings.py as above (GoogleResourcesConfig untouched); docstrings rewritten.
B3 Readers: client.py (tenant.delegated_user_email as the default subject; api_*; not-configured message names [google_workspace.tenant] customer_id and GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY), infrastructure/directory/factory.py:57, packages/talent/adapters/google_drive.py (tenant's delegated_user_email, None when unconfigured, as today).
B4 app/config/base.toml: [google_workspace] api_num_retries = 3, api_timeout_seconds = 10.0, with a comment naming the tenant entry's keys: customer_id in the deployment's file, delegated_user_email and service_account_key from GOOGLE_WORKSPACE__TENANT__<FIELD> (non-public value and secret). production.toml and local.toml: [google_workspace.tenant] customer_id (G2 / H1). ci.toml: nothing.
B5 app/pyproject.toml: pytest env lines become "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY=" and "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL=" under the Slack blanks' comment; dependencies drop Authlib and google-auth-oauthlib (uv lock regenerates uv.lock).
B6 .github/workflows/ci_code.yml:79: delete the SRE_BOT_EMAIL line.
B7 Helpers. app/bin/audit_env_names.py HINTS: SRE_BOT_EMAIL -> secret GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID -> [google_workspace.tenant] customer_id, GOOGLE_API_NUM_RETRIES -> [google_workspace] api_num_retries, GOOGLE_API_TIMEOUT_SECONDS -> [google_workspace] api_timeout_seconds (GOOGLE_DELEGATED_ADMIN_EMAIL is a plain retired name). bin/deploy-checks.zsh: task check google, the first with a pre part. pre: the blob's GOOGLE_WORKSPACE_CUSTOMER_ID (printed: it goes in the files), MATCH or DIFFER for the key (sha256 of /sre-bot/GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY vs gcp_sre_service_account_key) and for the delegated user (sha256 of the parameter vs the blob's SRE_BOT_EMAIL value), never printing either; names of GOOGLE_DELEGATED_ADMIN_EMAIL and GOOGLE_API_* where set. post: configured_systems_built lists google on every task; zero google_workspace_not_configured, invalid_credentials_json, RefreshError, invalid_grant, unauthorized_client lines since the deploy; the blob lines still present (inert until 111.15.2). Usage line: task checks run with post, and with pre when they have a pre part. The scheduler check is deleted (TASK-112.4 Done).
B8 Docs: configuration.md :15 and :21 current-state lines (the stale "in use when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set ... my_customer" sentence), the two Google tolerated items closed, Changes line; doc-14 status for rows GOOGLE_DELEGATED_ADMIN_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID, SRE_BOT_EMAIL, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE; the Google README if it names old keys.

== Tests ==
T-B1 tests/unit/integrations/google_workspace/test_google_workspace_settings_load.py (rewrite on installed tmp files): tuning from [google_workspace]; customer_id from [google_workspace.tenant]; key and delegated user from GOOGLE_WORKSPACE__TENANT__* in env and .env; the old names (GOOGLE_DELEGATED_ADMIN_EMAIL, SRE_BOT_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE, GOOGLE_API_*) in env and .env ignored (AC #1, #4).
T-B2 tests/unit/integrations/google_workspace/test_google_workspace_settings_tenant_validate.py (replaces ..._customer_id_validate.py): tenant without key; key without tenant; delegated user without tenant; empty key and empty delegated user count as unset; blank or my_customer customer id; unknown key in [google_workspace] and [google_workspace.tenant]; messages name the key; no message or log line carries the key or the delegated user's value (AC #2).
T-B3 tests/unit/infrastructure/configuration/test_configuration_files_google.py: production's customer_id equals the recorded value (G2); local has a tenant; ci none; no file holds a key, an email or a Drive id (AC #1, #3; configuration.md Checks).
T-B4 tests/integration/server/test_lifespan_vendor_slice_validation.py: an invalid Google entry fails load_host_configuration naming the key; an absent entry boots unconfigured.
T-B5 pin file tests/unit/infrastructure/configuration/test_configuration_settings_production_names.py: Google rows to the new names; old names asserted unread (AC #4).
T-B6 call sites and client: GoogleWorkspaceSettings(google_workspace_customer_id=..., gcp_sre_service_account_key_file=..., sre_bot_email=...) -> tenant=GoogleWorkspaceTenant(...); google_api_* -> api_*; the client, directory factory and talent adapter delegate as the tenant's delegated_user_email (rg on 3eec058b: test_google_workspace_client.py, test_server_configured_systems_read.py, test_server_services_configured_systems_resolve.py, test_lifespan_security_settings_validation.py, test_server_configuration_phase_logging_render.py, the talent adapter, scribe, scheduling, spreadsheets and spending tests).
T-B7 tests/unit/bin/test_bin_audit_env_names_classify.py: the four HINTS classify with their destination.
AC -> step -> test: #1 B2,B3,B4 / T-B1,T-B3,T-B6 ; #2 B2 / T-B2,T-B4 ; #3 B4,B7 / T-B3 + G2 ; #4 B2,B5,B6 / T-B1,T-B5 ; #5 B5 / uv lock, gates ; #6 gates.

== Doubts ==
(a) the dotenv source with prefix GOOGLE_WORKSPACE__ ignores blob lines such as SRE_BOT_EMAIL under extra=forbid -> T-B1. (b) the ownership check accepts [google_workspace.tenant] as part of [google_workspace] -> make check-settings-key-ownership. (c) Authlib or google-auth-oauthlib imported transitively at runtime by something else -> uv lock diff and the full suite. (d) development and production customer ids differ -> H1 records the development one.

== Blast radius and rollback ==
Every Google-backed path (incident documents and folders, list sheet, retro calendar, Meet, talent folders, AWS spending sheet, directory and groups). A missing key fails boot and the circuit breaker rolls back; a wrong delegated user or customer id fails at use, so post google and the manual checks decide rollback. The previous image reads the unchanged blob and GCP_SRE_SERVICE_ACCOUNT_KEY_FILE (both stay until 111.15.1/111.15.2); one git revert restores.

== Merge gates (human) ==
G1 111.10.1 merged, tf_apply passed, deployed, post PASS; H-A1 done (delegated user's parameter set).
G2 zsh bin/deploy-checks.zsh pre google from this branch: key MATCH and delegated user MATCH (a DIFFER blocks: put-parameter the right value first); the agent copies the customer id into production.toml. Re-run pre at merge for the rollback tag.
G3 Gates from app/: ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership.
G4 Codespaces secret GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY from the current GCP_SRE_SERVICE_ACCOUNT_KEY_FILE value (gh secret set GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY --app codespaces -R cds-snc/sre-bot, pasted at the prompt); app/.env.example Google lines name the two GOOGLE_WORKSPACE__TENANT__ variables only.
G5 zsh bin/env-checks.zsh --all GOOGLE_ GCP_ SRE_BOT_EMAIL from this branch: both GOOGLE_WORKSPACE__TENANT__ names none in Codespaces and SSM; the old Codespaces names delete (GOOGLE_RESOURCES none: still read until 111.10.3); blob lines none.
H1 local.toml customer_id: the agent reads GOOGLE_WORKSPACE_CUSTOMER_ID from the Codespace environment (the only value read; no key, email or id).

== Post-deploy ==
zsh bin/deploy-checks.zsh post google. Manual: /incident product list shows the product folders (Drive read through the key and the delegated user), and /incident declare opens with the handbook link. Rollback on FAIL: build_and_deploy with image_tag=<G2 tag> (docs/runbooks/roll-back-a-deployment.md), then revert.

== Cleanup (after the post-deploy PASS) ==
- Codespaces: gh secret delete GCP_SRE_SERVICE_ACCOUNT_KEY_FILE, GOOGLE_DELEGATED_ADMIN_EMAIL, GOOGLE_WORKSPACE_CUSTOMER_ID, SRE_BOT_EMAIL (--app codespaces -R cds-snc/sre-bot); GOOGLE_RESOURCES stays until 111.10.3. Confirm with env-checks.
- Actions: gh secret delete SRE_BOT_EMAIL -R cds-snc/sre-bot. GCP_SRE_SERVICE_ACCOUNT_KEY_FILE stays (tf_plan.yml:14, tf_apply.yml:17) until 111.15.2.
- SSM: no edit; the blob lines and gcp_sre_service_account_key go in 111.15.1/111.15.2.

== Decisions (2026-10-26) ==
D1 GOOGLE_RESOURCES is not in this task: 111.10.3 gives each id its own key once TASK-167 rules on document ids (human); never one JSON again.
D2 google_delegated_admin_email deleted (no reader; as 111.7 and 112.3).
D3 The delegation subject is the tenant's delegated_user_email, a non-public value from GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL (human approved the non-public rule; configuration.md amended), optional as today so TASK-169's per-role principals do not revert it. Sources: Google domain-wide delegation guide and best practices (https://developers.google.com/workspace/cloud-search/docs/guides/delegation, https://knowledge.workspace.google.com/admin/apps/domain-wide-delegation-best-practices).
D4 Production values through the versioned script (pre part of the google check; only the customer id is printed, the key and the delegated user are compared by hash); the development customer id from the Codespace environment.
D5 Authlib and google-auth-oauthlib, leftovers of the pickle-string OAuth admin user, are removed here (pyproject is touched anyway); the workflow TF_VAR line and GOOGLE_PICKLE_STRING go in 111.15.2.
<!-- SECTION:PLAN:END -->
