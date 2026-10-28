---
id: TASK-111.14
title: >-
  Move the feature values production sets into the files; delete the dead atip
  and groups slices
status: In Progress
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-28T18:18:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.13.3
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1747
parent_task_id: TASK-111
type: feature
ordinal: 420000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Production sets INCIDENT_CHANNEL, SLACK_SECURITY_USER_GROUP_ID, SLACK_NOTIFY_MGMT_USER_GROUP_ID and SRE_OPS_CHANNEL_ID, and runs AWS_ADMIN_GROUPS on its code default (sre-ifs@cds-snc.ca, organisation content in code). Their slices (infrastructure/configuration/features/incident.py, sre_ops.py and aws_ops.py) become ConfigurationSlice subclasses with their own table and case_sensitive=False, read from the files under lower snake_case keys (base.toml empty, production.toml the real values); per-field aliases are dropped, since a slice on the files reads only <TABLE>__ names (bin/check_settings_key_ownership.py env-naming). Field names stay until each package move, which standardises the keys (no table-name repeat), renames fields and prefixes and sets extra=forbid: incident in TASK-111.15.1, sre_ops in TASK-40, aws_ops in TASK-88. The legacy AtipSettings (ATIP_ANNOUNCE_CHANNEL) was never wired: modules/atip/atip.py posts the kickoff and the request text to C033L7RGCT0, the SRE test channel, written in code. It is replaced by an [atip] slice beside the module (modules/atip/settings.py, announce_channel_id: production the blob's value, local and ci the test channel), read at use (human, 2026-10-28). GroupsFeatureSettings (GROUP_DOMAIN, GROUP_PROVIDERS) lost its last reader with the groups and commands framework (#1178) and is deleted with its tests and pytest env entries. AWS_OPS_GROUP_NAME was never set in production, so /aws groups ops, modules/aws/ops_group_assignment.py and the adapters only it calls are dead code and are deleted. One PR (human, 2026-10-28; file-gate exception). The sre-bot-config values stay for the rollback image until TASK-111.15.2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every live feature value in the inventory is read from the files under its current slice's table, with production resolving the same values
- [x] #2 AtipSettings and GroupsFeatureSettings, their getters, exports, tests and env entries are deleted
- [x] #3 No feature value remains needed from the SSM parameters
- [x] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #5 Every reader of the incident feature slice builds it at use, not at import (found 2026-10-26 in TASK-111.10.1: modules/incident/core.py:22 and modules/incident/incident.py:22 read get_incident_settings() at import, and a slice on the files fails closed before the app factory installs them); a fresh-interpreter import test proves the provider cache stays empty
- [x] #6 The aws_ops slice reads aws_admin_groups from [cloud_operations] (base.toml empty, production.toml ["sre-ifs@cds-snc.ca"]; AWS_* names are the SDK's, so not [aws_ops]), and the default leaves the code
- [x] #7 AWS_OPS_GROUP_NAME, /aws groups ops, modules/aws/ops_group_assignment.py and the adapters only it called are deleted with their tests
- [x] #8 ATIP announcements go to [atip] announce_channel_id (modules/atip/settings.py), not a channel id written in code; production resolves the ATIP_ANNOUNCE_CHANNEL blob value, local and ci the test channel
- [x] #9 Incident channel links are Slack's deep link (https://slack.com/app_redirect?channel=<id>&team=<[slack.tenant] team_id>), not a workspace host written in code, and the incident list reader takes both the new link and the archive URLs older rows hold
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PROPOSED, AWAITING APPROVAL. Planned 2026-10-28 against main 4c914688 plus the TASK-111.13.3 tree (PR #1803). Revised the same day after the human's answers: one PR, aws_ops in scope, keys standardised at each package move, ids researched. Implementation starts after #1803 merges, because the two share app/config/base.toml, the app/pyproject.toml pytest-env pins, HINTS in app/bin/audit_env_names.py, host_configuration.py and doc-14.

## Findings
Searched with rg over app/, terraform/, .github/, .devcontainer/ and bin/. app/.env* are denied to the agent.

- **Readers of the live incident and sre_ops values**
  - SRE_OPS_CHANNEL_ID: server/configuration/host_configuration.py:19,62,157,174, where _validate_slices builds it. server/lifespan.py:18,73,87,248,316-318, the startup message. modules/ops/notifications.py:4,19, read at call.
  - INCIDENT_CHANNEL, SLACK_SECURITY_USER_GROUP_ID and SLACK_NOTIFY_MGMT_USER_GROUP_ID:
    - modules/incident/core.py:12,22-25 reads them at import and uses them only in initiate_resources_creation (:447, 555, 570-582).
    - modules/incident/incident.py:11,22-24 reads them at import and never uses them: dead.
- **aws_ops (AWSFeatureSettings)**
  - AWS_ADMIN_GROUPS gates the legacy /aws commands through modules/permissions.is_user_member_of_groups: modules/aws/groups.py:55,97,128 and modules/aws/users.py:52, read at call.
  - Production sets neither name. doc-14 has no row for either, and neither is in the 2026-10-20 key list of the blobs. Production therefore runs on the code default ["sre-ifs@cds-snc.ca"], which is organisation content in code (organisation-content.md Draft :16, :78).
  - AWS_OPS_GROUP_NAME defaults to "", and production never set it. So `/aws groups ops` (groups.py:38-39, request_groups_ops :126-160) always answers "feature is disabled" in production, and modules/aws/ops_group_assignment.py never runs past its guard.
  - That branch is the only caller of packages/aws_platform/adapters/sso_admin.py (build_sso_admin_adapter) and of IdentityCenterAdapter.get_group_id (identity_center.py:164).
  - All of it is dead in production. Under the standing dead-code rule it is deleted in this task, the one that touches aws_ops.py.
- **Dead slices**
  - AtipSettings (features/atip.py) and GroupsFeatureSettings (features/groups.py, which also holds the reconciliation, circuit-breaker and justification fields) have no reader outside their own modules, features/__init__.py and two test files.
  - The pytest-env pins at pyproject.toml:169-172 set SLACK_SECURITY_USER_GROUP_ID, SLACK_NOTIFY_MGMT_USER_GROUP_ID, ATIP_ANNOUNCE_CHANNEL and GROUP_PROVIDERS.
- **Pattern to follow**
  - 111.13.3's AuditSettings: a ConfigurationSlice with toml_table_header and env_prefix, an lru_cache provider, registered in _validate_slices.
  - Probed 2026-10-28: an UPPER_CASE field reads a lower_case TOML key (case_sensitive=False), so field names can stay frozen.
- **Are these ids public? (Q4, researched 2026-10-28)**
  - The repository is public.
  - Slack ids open nothing without a token. Secret scanners treat tokens and webhook URLs as the secrets, not ids, and workspace ids are discoverable without credentials (Vault Radar slack scan, Xygeni Slack webhook detector, Slack Watchman).
  - decisions/configuration.md (Non-public values) already keeps a Slack workspace or channel id in the files.
  - production.toml already commits a channel id ([server] sre_test_channel_id, [notify_api_key_leak] channel_id) and a user-group id ([notify_api_key_leak] oncall_group_id = "S0BNW0G8CFK").
  - The four incident and sre_ops ids are therefore deployment configuration in production.toml, with no change.
  - The admin group address sre-ifs@cds-snc.ca is a Google group address whose membership is the control. Knowing the address grants nothing, and it is already in the public history. It is not the "account that holds domain privileges" the non-public rule names (that is the delegation subject, which can be impersonated), so it goes in production.toml too. configuration.md gets one clause saying an authorisation group's address is an identifier, not a non-public value.

## Decisions
- **D1: one PR (human, 2026-10-28).** It trips the file gate (about 20 production files, mostly deletions). The exception is recorded as for row 9.9b.1.
- **D2: aws_ops is in scope (human, 2026-10-28).**
  - AWSFeatureSettings becomes a ConfigurationSlice with table [aws_ops] and prefix AWS_OPS__. The AWS_ADMIN_GROUPS field name stays, so its key is aws_admin_groups.
  - base.toml: aws_admin_groups = []. With the empty base, local and ci deny every /aws admin command, which is the safe default. A developer sets AWS_OPS__AWS_ADMIN_GROUPS='["..."]' in app/.env.
  - production.toml: aws_admin_groups = ["sre-ifs@cds-snc.ca"], so production's behaviour is unchanged.
  - Deleted as dead code: AWS_OPS_GROUP_NAME, modules/aws/ops_group_assignment.py, the `ops` case and request_groups_ops in modules/aws/groups.py, sso_admin.py, IdentityCenterAdapter.get_group_id, and their tests. Also deleted: the ops_group_assignment line in bin/baselines/aws_platform_seam_consumers.txt and any fake-coverage, import-linter or fake entries naming them.
  - Once nothing inherits FeatureSettings (base.py), it is deleted if nothing else imports it.
  - TASK-88 AC #7 still deletes AWS_ADMIN_GROUPS when the AWS surfaces declare permissions under authorization.md.
- **D3: tables and keys.**
  - [incident] holds incident_channel, slack_security_user_group_id and slack_notify_mgmt_user_group_id. [sre_ops] holds sre_ops_channel_id. [aws_ops] holds aws_admin_groups.
  - The keys repeat their table only because field names stay frozen until each package move. That is tolerated against configuration.md's "a key does not repeat its table name".
  - Each move standardises its own keys, and each task now carries this as an AC (human, 2026-10-28): incident in TASK-111.15.1, sre_ops in TASK-40, aws_ops in TASK-88.
- **D4: base.toml declares every key with an empty value** ("" or []), so each table stays reviewable.
  - production.toml holds the real values. local.toml and ci.toml hold none, because local shares the production Slack workspace T2G2S06PM.
  - Per-field aliases are dropped.
  - _validate_slices gains get_incident_settings() and get_aws_feature_settings() next to get_sre_ops_settings() (:157), so a bad table fails boot. Readers still build their settings at use.
- **D5: the AC #5 fix.**
  - core.py: delete the constants at :22-25. initiate_resources_creation calls get_incident_settings() once at its top.
  - incident.py: delete :11 and :22-24.
  - tests/modules/incident/test_incident_core.py patches modules.incident.core.get_incident_settings instead of the constants (:47, 468, 606, 672, 725, 756, 794, 823, 830, 871).
  - Tests that relied on the removed SLACK_* pytest-env pins patch explicitly instead.
- **D6: expand and contract.**
  - One deploy. No new parameter, no terraform change and no SSM edit.
  - The blobs keep their old lines, unused by the new image, so the previous image still reads them on a rollback. They go with the blobs in TASK-111.15.2.
  - The risk is a mistyped id, which boots fine and announces to the wrong place. The pre-merge MATCH check is the gate.

## Steps, tests first
1. **Tests (red).** Names follow testing-standards.
   - tests/unit/infrastructure/configuration/test_incident_settings_load.py, test_sre_ops_settings_load.py and test_aws_ops_settings_load.py:
     - the table is read from the files, and an <TABLE>__<FIELD> env override wins;
     - the old flat names are not read, and an unknown key raises ConfigurationError;
     - building the slice before the files are installed raises ConfigurationError;
     - an empty base means not configured.
   - tests/unit/infrastructure/configuration/test_configuration_files_features.py, shaped like test_configuration_files_vendors.py:
     - production loads the four Slack ids in shape (^C[A-Z0-9]+$ and ^S[A-Z0-9]+$), and aws_admin_groups == ["sre-ifs@cds-snc.ca"];
     - local and ci load none of them;
     - base.toml declares the three tables with empty values, and no file names an atip or groups table.
   - tests/unit/server/test_server_app_import_feature_settings_lazy.py, copied from test_server_app_import_vendor_settings_lazy.py (fresh interpreter):
     - import server.server, modules.incident.core, modules.incident.incident, modules.ops.notifications, modules.aws.groups and modules.aws.users;
     - all three provider caches stay at 0 (AC #5).
     - Also add those modules to _MODULES in test_server_import_builds_no_settings.py.
   - tests/integration/server/test_lifespan_feature_slice_validation.py, copied from test_lifespan_vendor_slice_validation.py: an unknown key in [incident], [sre_ops] or [aws_ops] stops startup and names the key.
   - test_settings_structure.py: the features package has no atip or groups slice.
   - tests/unit/modules/aws/test_groups_command_handler.py: `/aws groups ops` is no longer a known operation and falls to the default branch.
   - tests/unit/bin/test_bin_audit_env_names_classify.py:
     - the four Slack names classify as "delete" with their file destination, and AWS_ADMIN_GROUPS goes to [aws_ops] aws_admin_groups;
     - AWS_OPS_GROUP_NAME, ATIP_ANNOUNCE_CHANNEL, GROUP_DOMAIN, GROUP_PROVIDERS and the RECONCILIATION_*, CIRCUIT_BREAKER_*, REQUIRE_JUSTIFICATION and MIN_JUSTIFICATION_LENGTH names classify as "nothing (deleted)".
2. **Delete the dead code.**
   - features/atip.py, features/groups.py and their features/__init__.py exports.
   - modules/aws/ops_group_assignment.py, the `ops` case and request_groups_ops in groups.py, sso_admin.py, IdentityCenterAdapter.get_group_id, and their tests: test_ops_group_assignment_handler.py, test_aws_platform_sso_admin_provider.py and test_aws_platform_sso_admin_operations.py, plus the get_group_id cases in test_aws_platform_identity_center_operations.py.
   - The seam baseline line, and the stale singleton and structure tests.
3. **Move the slices.** incident.py, sre_ops.py and aws_ops.py become ConfigurationSlice subclasses with their aliases dropped, and their docstrings list the [table] keys. host_configuration.py: _validate_slices gains incident and aws_ops. Apply the D5 fix to core.py and incident.py.
4. **Configuration files.**
   - base.toml gets [incident], [sre_ops] and [aws_ops], with comments: ids are deployment configuration, never a secret; empty means not configured.
   - production.toml gets the four Slack ids, copied from the `pre features` output (human step H1), and aws_admin_groups = ["sre-ifs@cds-snc.ca"].
   - pyproject.toml loses the pins at 169-172.
5. **HINTS.** Rows for every retired name in bin/audit_env_names.py, as listed in step 1.
6. **bin/deploy-checks.zsh: new task check "features"** (TASK_CHECKS and PRE_CHECKS).
   - pre: for INCIDENT_CHANNEL, SLACK_SECURITY_USER_GROUP_ID, SLACK_NOTIFY_MGMT_USER_GROUP_ID and SRE_OPS_CHANNEL_ID, print the blob's value and production.toml's value, then MATCH or DIFFER.
     - Printing is allowed because these ids are public under configuration.md, as the Notify API host already is.
     - It reports AWS_ADMIN_GROUPS and AWS_OPS_GROUP_NAME as "in: none" (expected), and the atip and groups lines as inert.
   - post: no configuration_invalid naming incident, sre_ops or aws_ops; configuration_loaded is present.
   - The check is deleted when 111.14 is Done.
7. **Docs.**
   - doc-14: the four Slack rows become "no longer read (TASK-111.14); file [incident] ...", using the FILE_DESTINATION syntax. Add AWS_ADMIN_GROUPS (file [aws_ops] aws_admin_groups) and AWS_OPS_GROUP_NAME (deleted). One line covers the unlisted groups-slice names.
   - decisions/configuration.md:
     - line 16 and the tolerated item: atip and groups are gone; incident, sre_ops and aws_ops are on the files, with keys standardised at their moves (111.15.1, TASK-40, TASK-88);
     - the authorisation-group-address clause (Q4);
     - a Changes entry.
   - authorization.md: amend any mention of the AWS_ADMIN_GROUPS default.
   - The doc-11 row.

## AC traceability
- #1: steps 1, 3 and 4 (load and files tests).
- #2: steps 1 and 2.
- #3: steps 4 and 6 (pre MATCH; the blob lines stay unused until 111.15.2).
- #4: the gates.
- #5: step 1 (fresh-interpreter test) and step 3.
- #6: steps 1 to 4 (aws_ops load and files tests, groups-handler test).
- #7: step 2, and the rg gate below.

## Human steps
- **H1, during implementation, after step 6 is on the branch:** run `zsh bin/deploy-checks.zsh pre features` from the branch. It prints the four blob values, which are ids. The agent copies them from tmp/deploy-checks/pre-features-*.txt into production.toml. No manual SSM lookup is needed.
- **H2, before merge:** run `pre features` again. All four must show MATCH. Keep the printed image_tag as the rollback target.
- **H3, after the deploy:** run `post features`. The "SRE Bot has started up" message arriving in the ops channel proves sre_ops is live. Optionally, have an sre-ifs member run `/aws groups list` to prove aws_ops.
- **H4, developers:** run make env-checks, then delete the retired names from Codespaces and app/.env. Edit app/.env.example (the agent is denied that file). Developers set INCIDENT__*, SRE_OPS__* or AWS_OPS__AWS_ADMIN_GROUPS when they need them in dev.

## Gates (run from app/)
ruff; mypy (no new errors in touched files); pytest tests --ignore=tests/smoke; make check-import-contracts; make check-settings-key-ownership; make check-fake-coverage; make check-aws-platform-seam. Then confirm that rg -n "get_atip_settings|get_groups_settings|AtipSettings|GroupsFeatureSettings|AWS_OPS_GROUP_NAME|ops_group_assignment|build_sso_admin_adapter" app returns nothing.

## Blast radius and rollback
- **A wrong Slack id:** the bot silently announces to the wrong channel, or skips the group invite. Gated by pre MATCH.
- **A bad table:** boot fails, and the ECS circuit breaker returns to the previous revision.
- **`/aws groups ops`:** it disappears. It only ever answered "disabled" in production.
- **The /aws admin commands:** unchanged in production. Local and ci deny them unless configured.
- **Rollback:** git revert restores the code, and the previous image reads the untouched blob lines.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-28 implemented on task-111.14-feature-values from main 0995888b (111.13.3 merged), one PR.
- Slices: IncidentFeatureSettings [incident], SreOpsSettings [sre_ops] and AWSFeatureSettings [cloud_operations] are ConfigurationSlice subclasses. The field names are frozen, the aliases are dropped and extra=forbid is inherited. All three are validated in _validate_slices.
- Planned [aws_ops] became [cloud_operations]: AWS_OPS__ is under the SDK's AWS_* namespace, which the key-ownership check refuses (sdk-namespace rule). cloud_operations is the product area (plugins.cloud_operations).
- base.toml holds the keys empty. production.toml holds [cloud_operations] aws_admin_groups = ["sre-ifs@cds-snc.ca"]. The four Slack ids are pending the human's pre features output.
- Import-time reads gone (AC #5): core.py reads the settings inside initiate_resources_creation, and incident.py's unused constants are deleted. A fresh-interpreter test shows all three caches empty after importing the app and readers.
- Deleted (AC #2, #7):
  - code: atip.py, groups.py, the FeatureSettings base (base.py), the uncalled docs_generator.py, ops_group_assignment.py with the /aws groups ops case and request_groups_ops, sso_admin.py, IdentityCenterAdapter.get_group_id;
  - their tests, the 4 pytest-env pins and the seam baseline line.
  - Kept: integrations/aws keeps the sso-admin client overload and role map (generic client capability).
- HINTS: the 5 moved names point at their keys; AWS_OPS_GROUP_NAME, ATIP_ANNOUNCE_CHANNEL and 13 groups names are 'nothing (deleted)'.
- The email guard in test_configuration_files_google_tenant cuts out the aws_admin_groups line (a group address is an identifier, configuration.md).
- bin/deploy-checks.zsh gains task check 'features':
  - pre prints the four blob ids beside production.toml with MATCH/DIFFER, and expects AWS_ADMIN_GROUPS and AWS_OPS_GROUP_NAME in no blob;
  - post counts configuration_invalid naming the tables.
- Docs: doc-14 rows; configuration.md line 16, the tolerated item, the identifier clause and the Changes entry; authorization.md tolerated line; organisation-content.md Tolerated line (Draft); TASK-88 AC #7 and TASK-159 description reworded for [cloud_operations].
- Gates:
  - ruff clean;
  - mypy 41 errors (baseline 43; 2 lived in the deleted docs_generator.py; incident.py:114 is pre-existing, shifted lines);
  - pytest 5894 passed, 1 failed (test_production_resolves_the_values_production_ran_on, waiting on the four ids);
  - contracts 13 kept, key ownership OK, fake coverage OK, aws-platform seam OK.
- Open: ACs #1, #3 and #4 wait on the ids (human runs pre features).

2026-10-28 follow-up (human): the legacy AtipSettings was never wired; modules/atip/atip.py posted to C033L7RGCT0 in code. Now:
- New [atip] slice in modules/atip/settings.py (announce_channel_id), read at use in atip_view_handler; an empty channel skips both announcements. It is validated at boot and is in the lazy-import probe.
- base.toml empty; local and ci C033L7RGCT0 (behaviour unchanged there); production gets the blob value via pre features. HINTS ATIP_ANNOUNCE_CHANNEL -> [atip] announce_channel_id. The deploy check now compares five ids. AC #8 added.
- Confirmed the groups slice was unneeded: its last readers (packages/groups and the commands framework) went in #1178 (8e3e9700, 2026-05-05). Access checks group domains through its own policy, and its reconciliation_enabled is its own field.
- Hard-coded deployment values found by a scan:
  - gcdigital.slack.com workspace URL at modules/incident/core.py:189,256,425 (open question to the human);
  - sre-bot.cdssandbox.xyz in modules/slack/webhooks_create.py and webhooks_list.py (note on TASK-37);
  - encrypted-message.cdssandbox.xyz in modules/secret/secret.py (note on TASK-39).
- Gates: ruff clean; mypy 41; pytest 5902 passed, 2 failing until the production ids land; contracts 13 kept, key ownership, fake coverage and seam OK.

2026-10-28 follow-up (human: fix in this PR): the three gcdigital.slack.com archive URLs in modules/incident/core.py are replaced by core.channel_url().
- channel_url() builds Slack's documented deep link, https://slack.com/app_redirect?channel=<id>&team=<team_id>, with the team id read at call time from [slack.tenant]. With no tenant the team parameter is left out.
- The incident list sheet, the record and the report boilerplate store the new link for new incidents.
- The sheet reader parsed channel ids with a gcdigital regex. incident_folder.channel_id_from_link now reads both forms: any *.slack.com/archives/<id> and slack.com/app_redirect?channel=<id>.
- AC #9 added and checked. Gates: pytest 5910 passed, 2 failing until the production ids land; ruff and format clean; mypy 41; contracts 13 kept, key ownership, fake coverage and seam OK.

2026-10-28 production values: pre features (tmp/deploy-checks/pre-features-20261028T172634Z.txt, 17:26Z) printed the five blob ids, now in production.toml:
- INCIDENT_CHANNEL CUYR73ESX, SLACK_SECURITY_USER_GROUP_ID S057X3XB5FX, SLACK_NOTIFY_MGMT_USER_GROUP_ID S0BC6L00PUG, SRE_OPS_CHANNEL_ID C0388M21LKZ;
- ATIP_ANNOUNCE_CHANNEL C033L7RGCT0, the same test channel the code had hard-coded, so production ATIP behaviour is unchanged.
AWS_ADMIN_GROUPS and AWS_OPS_GROUP_NAME are in no blob and not in the task definition, so production ran on the code default. Rollback tag at that run: 0995888b958034f520dd99e324827e93937daeb0-2026-10-28. Tests pin the literal ids.
Gates: ruff and format clean; mypy 41 (baseline 43); pytest 5912 passed; contracts 13 kept, key ownership OK, fake coverage OK, aws-platform seam OK. ACs 1-9 checked. Before merge: the human reruns pre features for MATCH on all five.

2026-10-28 merge gate and audit commands:
- pre features 17:51Z: all five ids MATCH, RESULT features_pre PASS. Rollback tag 0995888b958034f520dd99e324827e93937daeb0-2026-10-28.
- env-checks 17:50Z: 56 delete and 3 check rows.
- Following the human's question, audit_env_names.py now ends its report with the commands that apply its delete and rename rows. bin/env-checks.zsh passes REPO_SLUG.
  - Env-file lines: one sed per file. A line whose value moves to a new name is renamed in place, not deleted.
  - Codespaces, Actions, Dependabot and environment secrets and variables: gh under the user's own login.
  - A retired Codespaces secret whose value moves is copied from the running Codespace (printenv into gh secret set) before the delete, unless the new name already exists. Without that, the old 'delete' rows would have lost NOTIFY_SRE_*, TRELLO_* and the AWS role values, since GitHub never returns a value.
  - No command for SSM or organization-level names.
- Tests: tests/unit/bin/test_bin_audit_env_names_fix_commands.py.
- Gates: pytest 5928 passed, ruff clean, mypy 41, contracts 13 kept, key ownership OK, fake coverage OK, seam OK.

2026-10-28 env-checks plan/apply (human). Like terraform, make env-checks only plans:
- It writes tmp/env-checks/<UTC>.plan.sh beside the report and changes nothing.
- zsh bin/env-checks.zsh apply <plan> (make env-checks-apply PLAN=<plan>) prints that saved plan and its age, and asks for 'yes'.
- It then runs the plan line by line, logs ok/FAILED to <plan>.applied.txt, renames the plan to .applied.sh so it cannot run twice, and exits 1 on any failure.
- Verified: smoke tests for cancel, apply, empty and bad paths; bin tests 310 passed; ruff clean. The full app gates were not rerun: dev tooling only (human).
<!-- SECTION:NOTES:END -->
