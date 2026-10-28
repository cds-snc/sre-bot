---
id: TASK-111.10.3
title: Give each Google document id its own key; GOOGLE_RESOURCES is no longer read
status: In Progress
assignee: []
created_date: '2026-10-26T18:55:00Z'
updated_date: '2026-10-28T21:30:00Z'
labels:
  - configuration
  - security
milestone: m-7
dependencies:
  - TASK-111.10.2
  - TASK-167
references:
  - decisions/configuration.md
parent_task_id: TASK-111.10
type: feature
ordinal: 448000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GOOGLE_RESOURCES packs the incident, talent, spending and calendar ids into one JSON value, a workaround for an SSM size limit that no longer applies. Each id becomes its own key, never one JSON again.

TASK-167 ruled and the human decided on 2026-10-28 (decisions/configuration.md, Accepted):
- Each id is non-public deployment configuration: declared in base.toml with an empty default, value only from the environment under <SLICE>__<FIELD> through an SSM SecureString parameter (a Codespaces secret in development), never in a configuration file, never logged in full.
- A value moves once, to its end-state owner's table and package, created ahead of the rebuild; there is no interim home.
- A subdomain's slice is its own flat table, <feature>_<subdomain>.

End-state homes:
- [incident_core] (IncidentCoreSettings in features/incident/common/settings.py, moved onto the files here): folder_id, report_template_id, list_sheet_id.
- [incident_response] (features/incident/response/settings.py): handbook_id.
- [incident_postmortem] (features/incident/postmortem/settings.py): calendar_id.
- [cloud_operations_spending] (features/cloud_operations/spending/settings.py, the spending boundary pulled forward from TASK-88): sheet_id.
- [talent] (features/talent/settings.py): the nine folder and template ids.

incident_drive_id and the blob's rep.g have no reader and are not carried. GoogleResourcesConfig and [google_resources] are deleted, which absorbs TASK-158. The GOOGLE_RESOURCES blob line stays inert for the rollback image until TASK-111.15.2. The owning rebuilds (145.6, 145.7, 145.10, 145.12, 39, 88) state the ids as required when they register.

Two PRs. The split exists only because the parameters must exist and hold their values before the readers deploy.

Also carried here: the Google behaviour fixes (ACs #5 to #7), and the two dev-tooling fixes found in TASK-111.14: the generated app/.env.example (AC #8) and the evidence-based env-name audit (AC #9).

Split from TASK-111.10 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each Google document, folder, sheet and calendar id has its own key on its end-state slice ([incident_core] folder_id, report_template_id, list_sheet_id; [incident_response] handbook_id; [incident_postmortem] calendar_id; [cloud_operations_spending] sheet_id; [talent] nine ids), a non-public value supplied only from the environment; GOOGLE_RESOURCES is no longer read; incident_drive_id is deleted and rep.g is not carried
- [x] #2 No configuration file holds a Drive, document, sheet or calendar id
- [x] #3 Each production value equals the id in the sre-bot-config GOOGLE_RESOURCES line it replaces (compared without printing it)
- [x] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #5 /sre incident product list opens a loading modal before the Drive read and fills it with views.update, so a cold Google call no longer outlasts Slack's 3-second trigger_id (expired_trigger_id seen after the 111.10.1 deploy)
- [x] #6 A present Google tenant entry's GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY is shape-checked at boot with no network call (decisions/configuration.md: a present entry requires its secrets and is shape-checked at boot): it parses as strict JSON with type service_account, and google.oauth2.service_account.Credentials.from_service_account_info builds the credentials, which validates client_email, token_uri and the private key locally. Malformed JSON (a private_key with literal newlines, seen in a Codespaces secret 2026-10-27), a missing field or an unreadable key fails boot naming the variable, never its value. The parsed credentials are built once and reused by the client, not re-parsed per call; a test runs the check with sockets disabled
- [x] #7 No token is fetched and no Google API is called at boot: a revoked key, a key whose project was deleted, or a missing domain-wide delegation still surfaces at first use, as a logged error naming the cause (the token endpoint's error code) and a stable user-facing message, never the raw exception text or a credential
- [x] #8 app/.env.example is generated from the settings classes (make env-example): one commented line per environment-only name (secrets and non-public values), grouped by owning settings module, its comment from the field description and its source ([codespaces], [devcontainer], [local]) from field metadata; a test fails when the committed file differs from the generated output, and env-checks no longer plans edits to it
- [x] #9 The env-name audit plans a delete only with positive evidence of retirement (a retired app name, a HINTS or SUPERSEDED entry); a GitHub secret or variable no workflow references on the default branch, or a name nothing in the repository reads, is a check showing its last reference in git history, and never enters the plan; secrets: inherit or a dynamic secrets[...] or toJSON(secrets) reference turns every repo secret into none
- [x] #10 IncidentCoreSettings is a ConfigurationSlice reading [incident_core] from the files (lower snake_case fields, no aliases, extra=forbid, defaults in base.toml); its INCIDENT_CORE__* environment names are unchanged and production sets none of them
- [x] #11 GoogleResourcesConfig, get_google_resources_config, the [google_resources] table and their tests are deleted; rg finds no reader under app/; configuration.md no longer tolerates GOOGLE_RESOURCES (absorbs TASK-158)
- [x] #12 The new end-state packages hold only their settings.py (features/incident/response, features/incident/postmortem, features/cloud_operations/spending under an empty features/cloud_operations umbrella, features/talent), each slice built lazily (nothing reads settings at import); import-linter contract (i) lists response and postmortem, and contract (f) lists features.talent and features.cloud_operations; make check-import-contracts and make check-settings-key-ownership pass
- [ ] #13 The parameters land first: a terraform-only PR adds the 15 names to sre_bot_secret_names with their doc-14 rows and the pre-deploy check google_ids (which also deletes the features check); the reader PR merges only after tf_apply, the human's put-parameter for each name, and pre google_ids all MATCH
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Shape

Two PRs. The split exists only because terraform must create the parameters, and the human must set their values, before any reader deploys. PR 2 takes a size exception (human, 2026-10-28): about 35 production files, most of them one-line reader swaps or one-line field metadata.

Decided 2026-10-28 (human, decisions/configuration.md):
- A value moves once, to its end-state owner's table and package; there is no interim home.
- A subdomain's slice is the flat table <feature>_<subdomain>. Nested tables were considered and deferred.
- Spending's boundary is pulled forward from TASK-88: features/cloud_operations/spending.
- An empty id does not fail boot. Legacy code fails at first use; each rebuilt subdomain states the id as required when it registers (plugins.md, TASK-172).
- The .env.example generator lives in the repo, not a library.
- The audit deletes only with evidence of retirement.

## Placement (AC #1)

| Blob path | Slice and key | Environment name and SSM parameter |
|---|---|---|
| inc.f | [incident_core] folder_id | INCIDENT_CORE__FOLDER_ID |
| inc.t | [incident_core] report_template_id | INCIDENT_CORE__REPORT_TEMPLATE_ID |
| inc.l | [incident_core] list_sheet_id | INCIDENT_CORE__LIST_SHEET_ID |
| inc.h | [incident_response] handbook_id | INCIDENT_RESPONSE__HANDBOOK_ID |
| cal.sre | [incident_postmortem] calendar_id | INCIDENT_POSTMORTEM__CALENDAR_ID |
| aws.s | [cloud_operations_spending] sheet_id | CLOUD_OPERATIONS_SPENDING__SHEET_ID |
| tal.i | [talent] internal_folder_id | TALENT__INTERNAL_FOLDER_ID |
| tal.t | [talent] templates_folder_id | TALENT__TEMPLATES_FOLDER_ID |
| tal.s | [talent] scoring_guide_template_id | TALENT__SCORING_GUIDE_TEMPLATE_ID |
| tal.c | [talent] core_values_interview_notes_id | TALENT__CORE_VALUES_INTERVIEW_NOTES_ID |
| tal.tech | [talent] technical_interview_notes_id | TALENT__TECHNICAL_INTERVIEW_NOTES_ID |
| tal.int | [talent] intake_form_template_id | TALENT__INTAKE_FORM_TEMPLATE_ID |
| tal.ph | [talent] phone_screen_template_id | TALENT__PHONE_SCREEN_TEMPLATE_ID |
| tal.rec | [talent] recruitment_feedback_template_id | TALENT__RECRUITMENT_FEEDBACK_TEMPLATE_ID |
| tal.pan | [talent] panelist_guidebook_template_id | TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID |

- Each SSM parameter is /sre-bot/<NAME>.
- inc.d (incident_drive_id) and rep.g have no reader. They are not carried.
- Verify every blob path against integrations/google_workspace/settings.py:107-292 before PR 1.

## PR 1: terraform and the pre-deploy check (merges first)

**Commit 1** (human decision): the decision-record and task changes from TASK-167 and this planning.
- decisions/organisation-content.md, provisioned-content.md, managed-content.md, configuration.md, product-scope.md, README.md.
- The backlog/tasks files changed in the working tree.
- doc-11 is never committed.

**Commit 2:**
1. terraform/ssm.tf: add the 15 names to locals.sre_bot_secret_names. The same list creates each parameter with the write-only placeholder (ssm.tf:47), its secrets: entry (ecs.tf:38) and its IAM grant (iam.tf:35). Same shape as #1792. Never bump value_wo_version.
2. doc-14: one row per name, from GOOGLE_RESOURCES <path>, non-public. app/bin/audit_env_coverage.py needs a doc-14 row for every terraform name.
3. bin/deploy-checks.zsh:
   - Add a pre check, google_ids, to TASK_CHECKS and PRE_CHECKS.
   - Hoist line_hash out of the vendors section.
   - For each pair, compare param_hash /sre-bot/<NAME> with the sha256 of the jq-extracted GOOGLE_RESOURCES value (quotes stripped).
   - Print MATCH, DIFFER or MISSING by name only, never a value. PASS only if all 15 match.
   - Print one info line saying inc.d and rep.g are intentionally not compared.
   - Delete the features check: header lines 18-21, the tokens in lines 28-29, the pre block 151-177, the post block 255-261, both features guards. TASK-111.14 is Done.
4. Verify with zsh -n bin/deploy-checks.zsh and shellcheck where it applies. Dev tooling: no app gates.

**Blast radius:**
- tf_apply creates 15 placeholder parameters and grants.
- The next deploy injects the placeholders, but nothing reads them. Verified 2026-10-28: IncidentFeatureSettings and AWSFeatureSettings build with undeclared INCIDENT__* and CLOUD_OPERATIONS__* names set.
- Reverting PR 1 after put-parameter destroys the values.

**Human steps after PR 1:**
1. tf_apply succeeds.
2. put-parameter --overwrite --type SecureString for each name, from its GOOGLE_RESOURCES path. Do not print the values.
3. Set Codespaces secrets for the names used in development.
4. zsh bin/deploy-checks.zsh pre google_ids: all MATCH (AC #3).

## PR 2: readers, Google behaviour and dev tooling

**Step 1. End-state slices (ACs #1, #2, #10, #12)**
- features/incident/common/settings.py: IncidentCoreSettings becomes a ConfigurationSlice.
  - toml_table_header ("incident_core",), env_prefix INCIDENT_CORE__.
  - Fields: incidents_table, timeline_table, new_incident_system, plus folder_id, report_template_id, list_sheet_id (str, default "", described, env-only metadata). No aliases.
  - Callers updated: core/api.py:156, comms/entrypoints/slack.py:179.
- New packages, each an __init__.py with no hookimpls plus a settings.py with a ConfigurationSlice and an lru_cache getter:
  - features/incident/response/ (IncidentResponseSettings, [incident_response] handbook_id).
  - features/incident/postmortem/ (IncidentPostmortemSettings, [incident_postmortem] calendar_id).
  - features/cloud_operations/ (empty umbrella __init__.py) and spending/ (CloudOperationsSpendingSettings, [cloud_operations_spending] sheet_id).
  - features/talent/ (TalentSettings, [talent], nine fields).
- config/base.toml: the five tables. The non-public keys are "" with a comment ("non-public: set from the environment"). The [incident_core] table defaults stay as today.
- server/configuration/host_configuration.py _validate_slices: add the slices that legacy readers use (response, postmortem, spending, talent), as sre_ops is. Plugin-read slices follow plugins.md. Confirm at implementation.
- app/pyproject.toml import-linter:
  - Contract (i) layer list adds response | postmortem.
  - Contract (f) adds features.talent and features.cloud_operations.
- pytest-env pins: only if a test needs one.

**Step 2. Reader swaps (AC #1).** Each moves from get_google_resources_config() to the owner's getter:
- modules/incident/incident.py:231 (handbook)
- modules/incident/schedule_retro.py:339 (calendar)
- modules/incident/incident_folder.py:37, 44, 278, 312, 336, 389 (folder, list)
- modules/incident/incident_helper.py:352 (folder)
- modules/incident/incident_document.py:35 (template)
- features/incident/drive/adapters/google_drive.py:137 (template)
- features/incident/scribe/adapters/google_docs.py:1347 (folder)
- modules/aws/spending.py:215 (sheet)
- modules/role/role.py:192-272 (talent)

**Step 3. Delete (AC #11).**
- GoogleResourcesConfig and get_google_resources_config (integrations/google_workspace/settings.py:107-292).
- The [google_resources] table in the configuration files.
- tests/.../test_google_workspace_resources_load.py.
- configuration.md: delete the tolerated GOOGLE_RESOURCES item and add a Changes line.
- features/incident/README.md: list the response and postmortem settings packages.

**Step 4. Google behaviour (ACs #5 to #7).**
- #5: incident_helper.py:360 list -> incident_folder.list_folders_view (:42-54).
  - ack, then views_open with a loading view (as incident.py:63 does), then the Drive read, then client.views_update(view_id=...) with the folders.
  - An empty or failed read updates the modal to an error message.
  - The same applies to view_folder_metadata_modal (incident_helper.py:152).
- #6: validate_service_account_key in integrations/google_workspace.
  - Strict JSON, type == "service_account", Credentials.from_service_account_info. No network.
  - Run from the tenant model_validator (settings.py:89), so boot fails naming GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY, never the value.
  - Base credentials are built once with the tenant. client.py:129-160 applies .with_subject and .with_scopes per call.
- #7: client.py catches google.auth.exceptions.RefreshError at first token use.
  - Logs the OAuth error code (invalid_grant, unauthorized_client) as the cause, structured, with no key material or raw exception text.
  - Raises a stable domain error with a fixed user message.

**Step 5. Audit (AC #9).** app/bin/audit_env_names.py and bin/env-checks.zsh:
- delete only for a name with evidence of retirement: in ctx.retired, or a HINTS or SUPERSEDED entry that names it as retired.
- The no-reader default (:312) and unreferenced Actions secrets and variables (_actions :315-321) become check rows, with the last git reference.
- The reference comes from env-checks.zsh: git log main -1 -G "(secrets|vars)\.NAME\b" -- .github, retried with --all and marked "unmerged branch only". It is written as a name<TAB>ref file the audit reads, so the audit stays pure. Only check rows are looked up.
- If .github holds secrets: inherit, secrets[, toJSON(secrets) or fromJSON(secrets, every repo secret becomes none ("the scan is blind").
- HINTS (:146-163): the GOOGLE_RESOURCES rows name the 15 new names; inc.d and rep.g become SUPERSEDED.
- test_bin_audit_env_names_classify.py:86 updated.

**Step 6. Generated .env.example (AC #8).**
- contracts/configuration.py: env_only(description, source) returns a Field with json_schema_extra {"env_only": True, "source": "codespaces" | "devcontainer" | "local"}.
- Applied to every secret and non-public field: security, slack, openai, notify, opsgenie, trello, aws tenant, google tenant, and the 15 new ids.
- app/bin/generate_env_example.py, about 150 lines: imports the slice classes and walks model_fields. It writes one commented line per env-only name, grouped by owning module, with the comment from the description and the source tag. It cross-checks bin/check_settings_key_ownership.collect_env_claims so every claimed name is emitted or deliberately omitted.
- make env-example.
- env-checks stops planning .env.example edits (bin/env-checks.zsh:99-104, app/bin/audit_env_coverage.py).
- The agent never reads app/.env.example. The generator writes it, the drift test reads it at test time, and the human reviews its diff.

**Step 7. Gates.**
- ruff, mypy, pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership.
- The bin tests cover steps 5 and 6.

## AC -> step -> test

| AC | Step | Tests |
|---|---|---|
| #1, #2 | 1, 2 | test_incident_common_settings_load.py (extended); test_incident_response_settings_load.py; test_incident_postmortem_settings_load.py; test_cloud_operations_spending_settings_load.py; test_talent_settings_load.py (empty default, env override, extra key refused, no value in base/ci/local/production.toml); patches retargeted in test_incident_folder.py, test_role.py, test_spending_handler.py, test_incident_scribe_draft_adapter.py, test_incident_document.py; test_server_app_import_google_settings_lazy.py rewritten around the new getters |
| #3 | PR 1.3 | pre google_ids run by the human (no automated test for zsh helpers) |
| #4 | 7 | gates |
| #5 | 4 | test_incident_folder.py: open then update order, empty result, Drive failure |
| #6 | 4 | google_workspace tenant tests: malformed JSON names the variable, wrong type, missing field, socket.socket monkeypatched to raise at boot |
| #7 | 4 | client test: RefreshError logs its code, no key text in logs, stable message; no HTTP at boot |
| #8 | 6 | test_bin_generate_env_example_drift.py; test_bin_generate_env_example_render.py (grouping, source tag, every claim emitted) |
| #9 | 5 | test_bin_audit_env_names_classify.py (unreferenced secret is a check with its reference); test_bin_audit_env_names_fix_commands.py (no unevidenced delete in a plan); test_bin_audit_env_names_dynamic_refs.py |
| #10 | 1 | test_incident_common_settings_load.py, test_incident_core_api_build_incident_store.py |
| #11 | 3 | rg in review; deleted tests |
| #12 | 1 | make check-import-contracts; lazy-import test |
| #13 | PR 1 | human steps recorded in notes |

## Assumptions to verify

- The blob paths above match GoogleResourcesConfig's properties. Read settings.py:107-292 before PR 1.
- jq is available where the human runs deploy-checks.
- Nothing reads the blob properties through getattr. Check with rg after step 3.
- Which slices _validate_slices builds (step 1).
- Which HINTS entries count as evidence of retirement (step 5).
- The CI shape check accepts a package holding only __init__.py and settings.py, and an empty umbrella __init__.py.

## Blast radius and rollback (PR 2)

- The readers switch to the new names. A missing value fails the feature at first use (a Drive 404), not boot. pre google_ids MATCH before merge guards this.
- AC #6 adds a boot failure for a malformed service-account key. Production's key passed post google on 2026-10-27, and from_service_account_info is what client.py runs today.
- One git revert of PR 2 restores the GOOGLE_RESOURCES readers. The blob line stays until TASK-111.15.2.
- After deploy: post (generic), then the manual checks: /sre incident product list, a declare (cancelled), retro scheduling, the spending report, a role.
- Then the env-checks replan, apply, and replan clean. This also clears the 111.11.1, 111.12 and 111.13 leftovers.
- No terraform change in PR 2.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-28 (human, from TASK-111.14): two dev-tooling cleanups ride with this task, the next one touching app/.env.example.
- Generate app/.env.example from the settings classes. Prior art: settings-doc (dotenv output with Jinja2 templates) and pydantic-settings-export (.env.example from pyproject config). Assess both against a small in-repo generator built on bin/check_settings_key_ownership.collect_env_claims.
- The audit's delete rule was too broad. It planned deletes for unreferenced repo Actions secrets, such as SLACK_INTERNAL_SRE_ALERTS_WEBHOOK_URL, which build_and_deploy used briefly in Feb 2025 (46ce4a17) before #769 moved to the org SLACK_SUCCESS_WEBHOOK. It did the same for any name nothing reads. Absence of a reference is not evidence of retirement: workflows on other branches, secrets: inherit and dynamic references are invisible to the scan. The human holds the 2026-10-28 19:18Z plan until the fix.

- Correction 2026-10-28 (human check, git evidence): SLACK_INTERNAL_SRE_ALERTS_WEBHOOK_URL was never on main. Its only reference is 46ce4a17 (2025-02-21) on the unmerged branch origin/fix/update_webhook_url; #769 (a245812c) merged instead with SLACK_SUCCESS_WEBHOOK. The CI Slack workflow (pr_notify_slack.yml) reads SLACK_SRE_CHANNEL_WEBHOOK_URL. No secrets: inherit or dynamic secrets[...] in .github. Retirement is evidenced: the human may delete it ahead of the replan. The audit fix still applies to the other unreferenced names.

- 2026-10-28: carried in from TASK-111.14 once it is Done: delete the features check from bin/deploy-checks.zsh in this PR (it touches deploy-checks); after the audit fix, the human replans env-checks, applies and replans clean, which also clears the 111.11.1, 111.12 and 111.13 leftovers.

- 2026-10-28: plan approved (human). PR 1 implementation started in the working tree (the human creates the branch).

- 2026-10-28 PR 1 implemented (working tree): terraform/ssm.tf adds the 15 names (24 -> 39; ECS secrets and the IAM grant follow the same list); doc-14 GOOGLE_RESOURCES row reworded and a GOOGLE_RESOURCES ids table added (keys 'GOOGLE_RESOURCES <path>', the convention SUPERSEDED already used); app/bin/audit_env_coverage.py resolves such a key's blob line from its first word (test added); bin/deploy-checks.zsh: pre check google_ids (hash compare, never prints a value; offline-tested on a fake blob value), the vendors (111.12 Done) and features (111.14 Done) checks deleted. jq was already required by the script. Verified: ruff clean, ruff format clean, tests/unit/bin 311 passed, zsh -n, terraform fmt -check ssm.tf, doc-14 covers all 15 terraform names. AC #13 waits on the merge, tf_apply, put-parameter and pre google_ids MATCH.

- 2026-10-28: the human's put-parameter loop failed with jq 'Invalid numeric literal at line 1, column 2' for all 15 (nothing written: the put ran only after a successful jq). Cause: the sed over the blob line skipped python-dotenv's unescaping, which the app gets because entry.sh writes the blobs to .env. Fix in PR 1: app/bin/google_resources_json.py reads the concatenated blobs on stdin through python-dotenv and GoogleResourcesConfig's quote strip and JSON parse, and prints the mapping for jq (never a value on error); bin/deploy-checks.zsh pre google_ids uses it; tests/unit/bin/test_bin_google_resources_json.py covers escaped double quotes, single quotes, bare values, concatenation, a missing line, and an error that never holds the value. bin tests 317 passed, ruff and format clean, mypy clean on the helper.

- 2026-10-28: PR 1 merged (#1805, 22144270); Terraform Apply success; deploy registered sre-bot-task:66 with the 15 new secrets (names counted in pre's task-definition list); deploy job red only from the verify step's bake-time race (TASK-164: IN_PROGRESS at 20:50:05), sbom red from the trivy-db rate limit. Human set the 15 parameters with put-parameter (first loop failed in jq before any write: escaped quotes, fixed by app/bin/google_resources_json.py in PR 1) and the 15 Codespaces secrets (20:51Z). pre google_ids 20:48:14Z: all 15 MATCH, PASS (tmp/deploy-checks/pre-google_ids-20261028T204814Z.txt); AC #3 checked. Rollback tag for PR 2: 2214427001c69a461ccb95578f268ba519c45005-2026-10-28 (rerun pre at merge). AC #13 is checked when PR 2 merges. Pending human: post (generic) to confirm :66 COMPLETED; TASK-167 Done (records on main).

- 2026-10-28 20:53Z: post (generic) on sre-bot-task:66 all PASS (rollout COMPLETED 2/2, boot_errors, runtime_errors, slack_up, version 22144270; tmp/deploy-checks/post-20261028T205326Z.txt). PR 1 fully deployed. Codespaces secrets set; visible only after a Codespace restart (a window reload is not enough).

- 2026-10-28 PR 2 implemented (branch task-111.10.3-readers, working tree): [incident_core] (IncidentCoreSettings on the files, INCIDENT_CORE__* names unchanged, fields lower snake_case), [incident_response], [incident_postmortem], [cloud_operations_spending], [talent] slices in settings-only packages, built lazily and validated at boot in _validate_slices; base.toml declares the 15 ids empty; pytest-env blanks them; import-linter (i) adds postmortem | response, (f) adds features.cloud_operations and features.talent. Readers swapped (incident, schedule_retro, incident_folder, incident_helper, incident_document, drive and scribe adapters, spending, role). GoogleResourcesConfig, its getter and test deleted; configuration.md no longer tolerates GOOGLE_RESOURCES (Changes line added); incident README lists response and postmortem. AC #5: list_folders_view opens a loading modal, then views_update (empty or failed read shows a message; a raised error is logged by type only). AC #6: build_service_account_credentials (strict JSON, type, client_email/private_key/token_uri, from_service_account_info) runs in the tenant validator, credentials built once (tenant.credentials); tests with sockets disabled and a throwaway RSA key (tests/factories/google_service_account.py). AC #7: _TokenCheckedHttp turns RefreshError into GoogleCredentialsRefused (fixed message, cause = OAuth error code, logged as google_token_refused), classified UNAUTHORIZED. AC #8: contracts.configuration.env_only metadata on every secret and non-public field; bin/generate_env_example.py + make env-example; drift and render tests; env-checks no longer plans .env.example edits; generated file has 37 names (human reviews its diff: hand-written lines not tied to an env-only field are gone). AC #9: deletes only with evidence (ctx.retired, HINTS, SUPERSEDED); unreferenced names and Actions secrets/variables are check rows with their last git reference (env-checks.zsh computes it, name<TAB>ref file); dynamic secrets references make repo secrets none. Gates (app/): ruff check All checks passed; ruff format 1062 already formatted; mypy 41 errors in 14 files, none on a changed line (modules/incident/incident.py:114 and modules/role/role.py:309 pre-existing); pytest tests --ignore=tests/smoke 6045 passed; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK; generate_env_example --check OK. AC #13 checked at merge after pre google_ids all MATCH. Agent slip: git rm --cached staged the deleted test_google_workspace_resources_load.py.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-27T14:45:00Z

---

2026-10-27 (human: avoid the invalid-credentials error at first use without network calls for no reason). Added AC #6 and #7. Validation is split at the network boundary. Offline checks (JSON shape, required fields, the RSA key loading into a signer, all local in google-auth's _service_account_info.from_dict) run at boot and fail fast. Checks that need Google (token exchange, delegation, API enablement) stay lazy at first use, so boot and the health checks stay static (decisions/health-checks.md: every health check is static; decisions/configuration.md: shape-checked at boot with no network call). Found when /dev-sre incident product list failed with 'Invalid control character at line 5 col 48': the development secret had real newlines inside private_key.

---
<!-- COMMENTS:END -->
