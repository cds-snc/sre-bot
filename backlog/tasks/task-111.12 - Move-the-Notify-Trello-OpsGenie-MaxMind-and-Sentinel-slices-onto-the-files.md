---
id: TASK-111.12
title: Move the Notify, Trello, OpsGenie, MaxMind and Sentinel slices onto the files
status: Done
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-28T13:13:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.2
  - TASK-111.16
  - TASK-111.17
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1745
parent_task_id: TASK-111
type: feature
ordinal: 418000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Notify, Trello, OpsGenie, MaxMind and Sentinel slices (integrations/<vendor>/settings.py) move onto the files, one table each ([notify], [trello], [opsgenie], [maxmind], [sentinel]). The fields lose their vendor prefix to match the doc-14 rename map (notify_api_url -> api_url). Non-secret values (Notify API URL, Trello ATIP board, Sentinel customer id and log type) go in production.toml, the MaxMind database path default in base.toml. Credentials are read only under the published SecureString names: NOTIFY__SRE_USER_NAME, NOTIFY__SRE_CLIENT_SECRET, TRELLO__APP_KEY, TRELLO__TOKEN, OPSGENIE__INTEGRATIONS_KEY, SENTINEL__SHARED_KEY (no terraform change). extra=forbid. The unread OPSGENIE_KEY and MAXMIND_KEY names are not migrated. Ride-along (2026-10-23, TASK-112 AC #3 scoping): integrations/notify/client.py:115 skips the revoke call when ENVIRONMENT is not production; once api_url is set only in production.toml the existing 'api_url missing' branch already stops the call elsewhere, so the ENVIRONMENT check is deleted (decisions/configuration.md: ENVIRONMENT is identity only).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Notify, Trello, OpsGenie and MaxMind each read their non-secret values from the files and their credentials from <SLICE>__<FIELD> names (Trello's as TRELLO__TENANT__<FIELD>); Sentinel follows TASK-171 and is not moved here
- [x] #2 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #3 integrations/opsgenie/ no longer has create_alert (no caller since the Notify key-revocation change): the function, its export and its tests are deleted
- [x] #4 Every reader of the four slices builds them at use, not at import (integrations/trello/client.py:7, opsgenie/client.py:10, notify/client.py:15 today); a fresh-interpreter import test proves the provider caches stay empty, as tests/unit/server/test_server_app_import_google_settings_lazy.py does
- [x] #5 Each of the four slices is validated at boot: a half-configured tenant entry or an unknown key fails boot naming the key; no entry boots with the vendor not configured and no network call, and its client reports not configured at use
- [x] #6 Notify's revoke no longer reads ENVIRONMENT: without [notify.tenant] it returns error and logs revoke_api_key_not_configured with no HTTP call
- [x] #7 Before merge, pre vendors PASSES (six parameters MATCH their blob lines, the Notify URL recorded); after deploy, post vendors PASSES; the google, aws and openai deploy checks are deleted
- [x] #8 The configuration files hold no credential or non-public value; production.toml carries [notify.tenant], [opsgenie.tenant] and [maxmind.tenant], local.toml [maxmind.tenant]
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.12 (Notify, Trello, OpsGenie and MaxMind onto the files; Sentinel follows TASK-171). Rewritten 2026-10-27 against main 1270ea35 after the human's answers. Modelled on 111.11.2, 111.11.1 and 111.10.2 (secret from the environment, boot-validated vendor slice, helpers, pins). Re-run every rg below first.

== Decisions ==
D0 (human 2026-10-27) ONE PR, size-gate exception: the four vendor moves are the same change repeated. Sentinel is not moved: TASK-171 rules first (rebuild or delete) and owns its end state; TASK-25.7 now depends on 171.
D1 (PROPOSED, ADR gap found in review; approve with this plan) decisions/configuration.md "Vendor enablement" replaces "The entry carries the vendor's real tenant id ...; a vendor with no tenant id ... is identified by the endpoint it reaches" with: The entry holds what this deployment needs to reach its tenant and act in it: the vendor's tenant id where it has one (workplace-systems.md rule 3), an endpoint or location only where the deployment chooses one (a regional or self-hosted API host, a model gateway, a local database file), and the credentials. A value the vendor or its SDK fixes, such as a single public API host, is not configuration. Where only the credentials identify the tenant, the credentials are the entry, read from the environment as <VENDOR>__TENANT__<FIELD>, as Google's and AWS's entries are environment-only (PagerDuty's Backstage backend plugin configures a pagerDuty block holding only apiToken: https://support.pagerduty.com/main/docs/backstage-integration-guide). Where an entry holds non-secret values, credentials stay fields of the slice (Slack, OpenAI). Changes line dated 2026-10-27. Backstage's integrations carry a host because GitHub, GitLab and Bitbucket can be self-hosted; a single-host SaaS plugin has no endpoint key.
D2 Shapes under D1:
- Notify: [notify] timeout_seconds = 60.0 (today client.py:95); [notify.tenant] api_url (the deployment chooses its GC Notify host), production.toml only; credentials on the slice under their published names NOTIFY__SRE_USER_NAME, NOTIFY__SRE_CLIENT_SECRET.
- OpsGenie: [opsgenie] timeout_seconds (no timeout today: urlopen at client.py:121 waits forever; outbound-clients.md requires one); [opsgenie.tenant] api_url (api.opsgenie.com or api.eu.opsgenie.com, a regional choice: https://docs.opsgenie.com/docs/european-service-region), production.toml; OPSGENIE__INTEGRATIONS_KEY on the slice. The client and factory contract stay TASK-25.6's; TASK-146's re-cut replaces Opsgenie before 2027-04-05.
- Trello: the SDK fixes the host, so the credentials are the entry: TRELLO__TENANT__APP_KEY and TRELLO__TENANT__TOKEN (environment only, new parameters: expand PR first, below). atip_board stays on the slice as TRELLO__ATIP_BOARD, tolerated until TASK-39 AC #9 (configuration.md tolerated list, added 2026-10-27). [trello] in base.toml holds no key, only the comment (verify the ownership check accepts an empty table; else the table is named in the comment of [plugins.workplace_utilities] — ask first). TASK-25.9 keeps its place (C1); nothing here waits on it.
- MaxMind: no credential and no tenant id; the deployment chooses the database file, so [maxmind.tenant] database_path in production.toml and local.toml (the image and the devcontainer both use ./geodb/GeoLite2-City.mmdb); boot checks the shape only (non-empty); the file's presence is the healthcheck's (lifecycle.md, outbound-clients.md: no I/O check aborts boot). MAXMIND_KEY stays unread (deleted in 111.15); TASK-57 keeps the source model.
D3 Requirements are the consumers' (TASK-172): oncall_sync (OpsGenie), geolocate (MaxMind) and ATIP (Trello, legacy) state nothing here; with no entry each client reports not configured at use.
D4 Notify: the ENVIRONMENT check (client.py:115-117) is deleted; no [notify.tenant] means not configured. The unreachable `url is None` branch (:120, field default "") is replaced by the tenant check.
D5 Dead code deleted with the touched files: opsgenie create_alert and api_post_request (create_alert is its only caller; verify) and their exports and tests (AC #3).

== Expand first (human, terraform-only PR, no task, as #1792/#1796) ==
E1 terraform/ssm.tf +2 names: TRELLO__TENANT__APP_KEY, TRELLO__TENANT__TOKEN; merge, tf_apply, put-parameter each from /sre-bot/TRELLO__APP_KEY and TRELLO__TOKEN; Codespaces secrets under the new names if development uses Trello (env-checks TRELLO_). TRELLO__APP_KEY and TRELLO__TOKEN become unread here and go in 111.15. The audit_env_coverage rules follow doc-14 (row updates ride in E1).

== Size ==
Production files 17: integrations/notify/{settings,client}.py, integrations/trello/{settings,client}.py, integrations/opsgenie/{settings,client,__init__}.py, integrations/maxmind/{settings,client}.py, server/configuration/host_configuration.py, config/base.toml, config/production.toml, config/local.toml, app/pyproject.toml, app/bin/audit_env_names.py, bin/deploy-checks.zsh, .github/workflows/ci_code.yml. Docs: decisions/configuration.md, doc-14 (oncall.md and the configuration.md tolerated item already edited 2026-10-27). ~350 production LOC, one pattern repeated four times. Exception approved (D0).

== Context (verified 2026-10-27, main 1270ea35) ==
- All four slices: BaseSettings, env_file .env, case_sensitive False, extra ignore, no prefix, plain str secrets; getters lru_cache: notify/settings.py:12-27, trello/settings.py:12-27, opsgenie/settings.py:12-25, maxmind/settings.py:12-25. No table in any file.
- Import-time reads: notify/client.py:15, trello/client.py:7, opsgenie/client.py:10 (each package __init__ re-exports its client). MaxMind reads at use (client.py:153-155).
- Readers: notify: modules/webhooks/patterns/aws_sns_notification/api_key_detected.py:66. trello: modules/atip/atip.py:499. opsgenie: modules/incident/on_call.py:33, packages/oncall_sync/adapters/opsgenie.py:18, jobs/scheduled_tasks.py:146 (healthcheck). maxmind: packages/geolocate/service.py:42, api/v1/routes/geolocate.py:15, jobs/scheduled_tasks.py:145; MaxMindClient.__init__ reads maxmind_db_path (client.py:57).
- OpsGenie hard-codes https://api.opsgenie.com at client.py:21, :47, :71, :100; the noqa S310 comments rely on the https scheme (the tenant validator keeps that true).
- Boot validation list: server/configuration/host_configuration.py:154-157.
- Production: blob lines NOTIFY_SRE_USER_NAME, NOTIFY_SRE_CLIENT_SECRET, NOTIFY_API_URL, TRELLO_APP_KEY, TRELLO_TOKEN, TRELLO_ATIP_BOARD, OPSGENIE_INTEGRATIONS_KEY (doc-14 :56-76); /sre-bot/ parameters NOTIFY__*, OPSGENIE__INTEGRATIONS_KEY, TRELLO__APP_KEY, TRELLO__TOKEN, TRELLO__ATIP_BOARD exist (terraform/ssm.tf:30-41). MAXMIND_DB_PATH unset (code default).
- pytest-env (pyproject.toml:159-169) sets SENTINEL_*, NOTIFY_SRE_*, TRELLO_* to their own names; ci_code.yml:76-78 sets NOTIFY_TEST_KEY, NOTIFY_SRE_USER_NAME, NOTIFY_SRE_CLIENT_SECRET, read by no test.
- Tests on old names (15 files): pins test, tests/unit/integrations/{notify,trello,opsgenie,maxmind}/test_*_settings_load.py, tests/integrations/{notify,trello,opsgenie}/test_*_client.py, tests/modules/webhooks/.../test_api_key_detected.py, tests/unit/modules/atip/test_atip.py, tests/unit/packages/oncall_sync/test_oncall_sync_opsgenie_adapter.py, tests/unit/infrastructure/services/test_narrow_slice_providers.py, tests/unit/integrations/maxmind/test_operation_client.py, tests/unit/bin/test_bin_audit_env_coverage_classify.py, tests/unit/bin/test_bin_settings_key_ownership_check.py.

== Steps (TDD, red first) ==
B1 Tests red: T-1..T-9.
B2 Four slices on ConfigurationSlice (toml_table_header, env_prefix <TABLE>__, extra=forbid, no aliases), each with a frozen extra=forbid tenant model and a model_validator naming the missing key, empty values unset, secrets SecretStr repr=False, and a docstring (keys, environment-only names, validated at boot, requirement is the consumer's):
 notify/settings.py: NotifyTenant(api_url https); NotifySettings(tenant, sre_user_name, sre_client_secret, timeout_seconds=60.0): an entry needs both credentials, either credential without an entry fails.
 opsgenie/settings.py: OpsGenieTenant(api_url https); OpsGenieSettings(tenant, integrations_key, timeout_seconds=30.0): entry and key go together.
 trello/settings.py: TrelloTenant(app_key, token: SecretStr, both required); TrelloSettings(tenant: TrelloTenant | None, atip_board: str = "" with a tolerated-until-TASK-39 comment): one of the two tenant variables without the other fails naming it (the AWS before-validator pattern), atip_board without a tenant fails.
 maxmind/settings.py: MaxMindTenant(database_path: str, min_length=1); MaxMindSettings(tenant).
B3 Clients read at use: notify/client.py (no module settings; create_authorization_header and post_event read get_notify_settings(); revoke_api_key: tenant None -> log revoke_api_key_not_configured, return "error"; url from tenant.api_url; timeout from the slice; host_info import removed). trello/client.py (get_trello_client reads the tenant, raises a not-configured error naming TRELLO__TENANT__APP_KEY when None; board from settings.atip_board). opsgenie/client.py (no OPSGENIE_KEY constant; one helper builds url from tenant.api_url and the auth header from the key; urlopen(timeout=settings.timeout_seconds); no tenant -> OpsGenieAPIError("Opsgenie is not configured"), healthcheck returns False and logs opsgenie_not_configured; create_alert and api_post_request deleted, opsgenie/__init__.py exports trimmed). maxmind/client.py: MaxMindClient takes the database path; get_maxmind_client() returns a client whose geolocate and healthcheck return a not-configured result (the existing permanent-error OperationResult with a registered code) when tenant is None.
B4 host_configuration.py: get_notify_settings(), get_trello_settings(), get_opsgenie_settings(), get_maxmind_settings() in _validate_slices (+ imports).
B5 base.toml: [notify] timeout_seconds, [opsgenie] timeout_seconds, [trello] and [maxmind] with comments naming their entries and environment-only names. production.toml: [notify.tenant] api_url = blob NOTIFY_API_URL (pre vendors prints it); [opsgenie.tenant] api_url = "https://api.opsgenie.com" (pre vendors confirms no EU host is used); [maxmind.tenant] database_path = "./geodb/GeoLite2-City.mmdb". local.toml: [maxmind.tenant] the same path; [opsgenie.tenant] only if env-checks shows a development key (H1). ci.toml: nothing.
B6 app/pyproject.toml pytest env: Sentinel lines unchanged; drop NOTIFY_SRE_*, TRELLO_*; add blanks NOTIFY__SRE_USER_NAME=, NOTIFY__SRE_CLIENT_SECRET=, TRELLO__TENANT__APP_KEY=, TRELLO__TENANT__TOKEN=, TRELLO__ATIP_BOARD=, OPSGENIE__INTEGRATIONS_KEY= (comment: likewise). ci_code.yml: delete the three NOTIFY_* lines.
B7 app/bin/audit_env_names.py HINTS: NOTIFY_SRE_USER_NAME, NOTIFY_SRE_CLIENT_SECRET -> secret NOTIFY__<FIELD>; NOTIFY_API_URL -> [notify.tenant] api_url; TRELLO_APP_KEY, TRELLO_TOKEN -> secret TRELLO__TENANT__<FIELD>; TRELLO_ATIP_BOARD -> secret TRELLO__ATIP_BOARD; OPSGENIE_INTEGRATIONS_KEY -> secret OPSGENIE__INTEGRATIONS_KEY; MAXMIND_DB_PATH -> [maxmind.tenant] database_path; NOTIFY_TEST_KEY retired.
B8 bin/deploy-checks.zsh: delete google, aws, openai (pre :124-198, post :259-300, header :13-22; helpers kept only if vendors uses them); add vendors. pre: prints the blob's NOTIFY_API_URL (public); hash-compares /sre-bot/NOTIFY__SRE_USER_NAME, NOTIFY__SRE_CLIENT_SECRET, OPSGENIE__INTEGRATIONS_KEY, TRELLO__TENANT__APP_KEY, TRELLO__TENANT__TOKEN, TRELLO__ATIP_BOARD with their blob lines (MATCH/DIFFER/MISSING, never printed); blob_where for MAXMIND_DB_PATH and any OPSGENIE host override (expected none); PASS on six MATCH and a URL. post: since the deploy, zero configuration_invalid lines naming notify, trello, opsgenie or maxmind; zero revoke_api_key_not_configured and opsgenie_not_configured; integration_healthcheck_result opsgenie and maxmind healthy. TASK_CHECKS=(vendors), PRE_CHECKS=(vendors).
B9 Existing tests moved off the old names (fixtures build real slices with tenants).
B10 Docs: configuration.md D1 amendment, current-state line :15 (four slices and their tables), Changes line (the four slices, names unread, ENVIRONMENT check gone), tolerated example :106 updated; doc-14 rows :55-76 (destinations, "no longer read (TASK-111.12); blob line inert until 111.15", TRELLO__APP_KEY and TRELLO__TOKEN -> TRELLO__TENANT__*).

== Tests ==
T-1 tests/unit/integrations/<vendor>/test_<vendor>_settings_load.py (four, rewritten): table keys from installed files; tenant from the files or the environment; secrets from <TABLE>__ names; repr/str/model_dump never show a secret; nothing set loads unconfigured; the old flat names in env and .env are ignored (AC 1).
T-2 tests/unit/integrations/<vendor>/test_<vendor>_settings_tenant_validate.py (four): half entries fail naming the key; empty is unset; non-https api_url fails (Notify, OpsGenie); empty database_path fails; unknown key fails naming it (AC 5).
T-3 tests/integrations/notify/test_notify_client.py: no tenant -> "error", revoke_api_key_not_configured, no POST; with a tenant posts to <api_url>/sre-tools/api-key-revoke with the slice timeout under ENVIRONMENT=ci; 201/200/other kept (AC 6).
T-4 tests/integrations/opsgenie/test_opsgenie_client.py: requests go to the tenant api_url with the timeout; no tenant -> OpsGenieAPIError and healthcheck False with no request; create_alert tests deleted (AC 3, 5).
T-5 tests/integrations/trello/test_trello_client.py and maxmind tests: not configured raises or returns not configured with no SDK call; configured paths unchanged (AC 5).
T-6 tests/unit/server/test_server_app_import_vendor_settings_lazy.py: a fresh interpreter imports server.server, modules.atip.atip, modules.incident.on_call, api_key_detected, packages.oncall_sync and packages.geolocate; the four getters' caches stay empty (AC 4).
T-7 tests/unit/infrastructure/configuration/test_configuration_files_vendors.py: base + each environment file validates (secrets supplied where an entry needs them); only the expected files carry each entry; no credential or non-public value in any file (AC 1, 8).
T-8 tests/integration/server/test_lifespan_vendor_slice_validation.py (extended): one half-configured case per vendor fails load_host_configuration naming the key; none configured boots (AC 5).
T-9 pins test_configuration_settings_production_names.py: rows to the new names, every retired name asserted unread; tests/unit/bin/test_bin_audit_env_names_classify.py: the new HINTS (AC 1, 7).
AC -> step -> test: #1 B2,B5,B6 / T-1,T-7,T-9; #2 gates; #3 D5,B3 / T-4; #4 B3 / T-6; #5 B2,B4 / T-2,T-4,T-5,T-8; #6 D4,B3 / T-3; #7 B8 / G1; #8 B5 / T-7.

== Assumptions and doubts ==
(a) The blob values match their parameters: pre vendors decides; put-parameter first on DIFFER/MISSING. (b) Production uses the US Opsgenie host (today's hard-coded URL proves it). (c) The settings ownership check accepts a table with no keys ([trello], [maxmind]); otherwise ask before adding a placeholder key. (d) create_alert is api_post_request's only caller (rg). (e) No development environment reaches Notify (the ENVIRONMENT check skipped it). (f) MaxMind's not-configured result uses a registered error code (contracts registry), no new literal.

== Blast radius and rollback ==
Boot: a malformed or half-configured entry for any of the four fails boot; the circuit breaker rolls back and the old tasks keep serving; pre vendors and the files test guard it. Runtime: leaked Notify key revocation, ATIP card creation, Opsgenie on-call reads (incident declare invites, oncall_sync) and geolocation; each degrades to not configured, never crashes the host. One git revert plus build_and_deploy with the pre image_tag restores; the old image reads the unchanged blob lines (kept until 111.15).

== Merge gates (human) ==
G0 Expand PR E1 merged, applied, the two Trello parameters put. G1 zsh bin/deploy-checks.zsh pre vendors PASS; pre at merge for the rollback tag. G2 gates from app/ incl. make check-import-contracts and make check-settings-key-ownership. H1 env-checks NOTIFY_ TRELLO_ OPSGENIE_ MAXMIND_; app/.env.example lines (agents are denied app/.env*).

== Post-deploy ==
post vendors PASS. Manual: /geolocate on a public IP returns a location (MaxMind); the next oncall_sync run updates its usergroups (OpsGenie). Rollback on FAIL: build_and_deploy with image_tag=<pre tag>, then revert.

== Cleanup (after PASS) ==
Actions secrets NOTIFY_TEST_KEY, NOTIFY_SRE_USER_NAME, NOTIFY_SRE_CLIENT_SECRET; Codespaces NOTIFY_*, TRELLO_*, OPSGENIE_*, MAXMIND_* old names (env-checks). SSM: blob lines and TRELLO__APP_KEY, TRELLO__TOKEN in 111.15.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-28 implementation (branch task-111.12-vendor-slices, from main 7315e957). Notify, Trello, Opsgenie and MaxMind are ConfigurationSlices: [notify] timeout_seconds 60 and [notify.tenant] api_url (production.toml, https://api.notification.canada.ca, to be confirmed by pre vendors against the blob's NOTIFY_API_URL); [opsgenie] timeout_seconds 30 (urlopen had none) and [opsgenie.tenant] api_url (production.toml and local.toml, https://api.opsgenie.com); Trello's entry TRELLO__TENANT__APP_KEY/TOKEN from the environment with TRELLO__ATIP_BOARD beside it (empty counts as unset; board without entry fails); [maxmind.tenant] database_path (production.toml and local.toml). Credentials SecretStr; half entries and unknown keys fail boot naming the key (host_configuration validates all four). Clients read at use: no module-level settings; Notify revoke without an entry logs revoke_api_key_not_configured and returns error, ENVIRONMENT check and host_info import gone; Opsgenie api_get_request(path) builds the tenant URL, raises OpsGenieAPIError when not configured, healthcheck logs opsgenie_not_configured; create_alert and api_post_request deleted with exports and tests; Trello raises TrelloNotConfiguredError; MaxMindClient(database_path) returns CONFIG_NOT_CONFIGURED without an entry. Retired names (flat NOTIFY_/TRELLO_/OPSGENIE_/MAXMIND_ and TRELLO__APP_KEY/TOKEN) pinned unread; pytest env and ci_code.yml moved off them; audit HINTS added. deploy-checks: google, aws, openai removed (tasks Done), vendors added. configuration.md D1 amendment, current state, tolerated list and Changes; doc-14 rows. Gates: ruff ok; mypy 47 errors = main baseline, none in touched files; pytest tests --ignore=tests/smoke 5999 passed; import contracts 13 kept; settings key ownership OK. AC #7 waits on pre vendors before merge and post vendors after deploy.

2026-10-28 pre vendors PASS (tmp/deploy-checks/pre-vendors-20261028T025350Z.txt): six parameters MATCH, Notify host MATCH (https://api.notification.canada.ca), no MAXMIND_DB_PATH or Opsgenie host line. Rollback image_tag 1270ea357ac6d0ce14c8b74e4895d130eb51b53b-2026-10-27. AC #7 waits on post vendors.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-27T11:26:00Z

---

2026-10-27 (TASK-111.11.1 session, human: create every parameter ahead of its reader): SENTINEL_CUSTOMER_ID and TRELLO_ATIP_BOARD are non-public values (decisions/configuration.md 2026-10-27). They are read as SENTINEL__CUSTOMER_ID and TRELLO__ATIP_BOARD from the environment only, never production.toml, so the description's 'Trello ATIP board, Sentinel customer id ... go in production.toml' is superseded. Their /sre-bot parameters are created by the standalone ssm PR before 111.11.1, with values put from the blob lines. Finding to assess in planning: Microsoft retired the Azure Monitor HTTP Data Collector API (customer id plus shared key) on 2026-09-14 (https://azure.microsoft.com/en-us/updates/azure-monitor-data-collection-api-retirement/); the replacement is the DCR-based Logs Ingestion API with Entra token auth. Check whether production Sentinel sends still succeed (the sentinel client's log events since 2026-09-14). If they fail, the slice is rebuilt on the Logs Ingestion API or deleted rather than moved, and SENTINEL__CUSTOMER_ID and SENTINEL__SHARED_KEY are removed in the contract.

---

created: 2026-10-27T11:45:00Z

---

2026-10-27: the Sentinel retirement finding is TASK-171 (doc-11 row Z2). This task's Sentinel part follows its ruling: rebuild on the Logs Ingestion API, or delete.

---

created: 2026-10-27T20:08:00Z

---

2026-10-27 planning (proposed, awaiting approval): the size gate trips, so TASK-111.12 becomes a coordinator over 111.12.1 Notify, 111.12.2 Trello, 111.12.3 OpsGenie and 111.12.4 MaxMind. AC changes are proposed here, nothing is removed: AC #1 'five slices' becomes the four, Sentinel's end state is TASK-171's (rebuilt on the files or deleted); AC #3 is checked by 111.12.3; AC #4 is checked per subtask, and the sentinel/client.py:15 import-time read goes with TASK-171; a new AC #5: every subtask is Done and the NOTIFY_*, TRELLO_*, OPSGENIE_* and MAXMIND_DB_PATH names it retires are unread.

---

created: 2026-10-27T20:34:00Z

---

2026-10-27 (human): one PR, size-gate exception (the four moves are the same change); Sentinel follows TASK-171. ACs #1 and #4 reworded to the four vendors, #5 to #8 added. Proposed with the plan: the configuration.md vendor-enablement amendment (D1).

---

created: 2026-10-27T20:53:00Z

---

2026-10-27: plan, ACs #1-#8 and the configuration.md D1 amendment approved (human). Expand PR prepared (ssm.tf +2 Trello tenant names, doc-14 rows); implementation starts after the expand is applied and env-checks NOTIFY_ TRELLO_ OPSGENIE_ MAXMIND_ is read (it decides whether local.toml gets [opsgenie.tenant]).

---

created: 2026-10-27T21:56:00Z

---

Expand PR #1798 merged 2026-10-27; tf_apply succeeded; both TRELLO__TENANT__* values set. env-checks 20261027T214259Z: Codespaces holds a development OPSGENIE_INTEGRATIONS_KEY, so H1 resolves: local.toml gets [opsgenie.tenant] api_url = "https://api.opsgenie.com". Notify stays unconfigured in development (no URL in local.toml), matching the removed ENVIRONMENT check.

---
<!-- COMMENTS:END -->
