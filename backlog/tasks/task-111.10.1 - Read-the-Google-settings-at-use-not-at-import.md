---
id: TASK-111.10.1
title: Read the Google settings at use, not at import
status: In Progress
assignee: []
created_date: '2026-10-26T18:29:00Z'
updated_date: '2026-10-26T19:50:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-112.4
references:
  - decisions/configuration.md
parent_task_id: TASK-111.10
type: feature
ordinal: 445000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Nine modules (modules/incident x5, modules/role, modules/dev, features/incident/drive and packages/talent adapters) call get_google_resources_config() or get_google_workspace_settings() at import time. server.server imports them before create_app() installs the configuration files, so once TASK-111.10.2 moves the Google slice onto the files (a slice built before install fails closed) every boot and test collection would fail. Each read moves to its use; module constants go; the unused INCIDENT_LIST in modules/dev is deleted. Also the expand step for the Google delegation subject, a non-public value (decisions/configuration.md, 2026-10-26): terraform creates /sre-bot/GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL and the task definition injects it, unread until 111.10.2; the human sets its value after the apply. No app behaviour change; deploys alone. Split from TASK-111.10 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No module calls a Google settings provider at import time: importing server.server, the legacy incident, role and dev modules and both Google adapters succeeds with both providers raising
- [x] #2 Every reader gets the same ids and delegation email as before (module tests repatched on the providers, assertions unchanged); the unused INCIDENT_LIST in modules/dev/incident.py is deleted
- [x] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #4 The delegation subject's parameter /sre-bot/GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL exists (terraform, placeholder) and is injected by the task definition, unread; the non-public value rule is in decisions/configuration.md and doc-14 names the new destinations
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployed; zsh bin/deploy-checks.zsh post PASS and the manual checks recorded: /sre incident product list shows the product folders; /incident with no text opens the creation modal with the folders and the handbook link, then cancelled
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.10.1 (read the Google settings at use, not at import). Split from TASK-111.10 on 2026-10-26 (human approved). Mechanical app change, no configuration or behaviour change, plus the expand step of the non-public delegated user (one terraform line, decided 2026-10-26); deploys alone. Written against the task-112.4-scheduler tree (3eec058b); branch task-111.10.1-lazy-google-reads from main once #1790 (TASK-112.4) has merged; re-run every rg below first.

== Why ==
TASK-111.10.2 moves GoogleWorkspaceSettings and GoogleResourcesConfig onto the configuration files. A ConfigurationSlice fails closed when built before the app factory installs the files (contracts/configuration.py:162), and server/server.py imports server/lifespan.py, which imports modules.incident, modules.role and modules.dev (lifespan.py:34-44), before create_app() runs. Nine modules call a Google settings provider at import time, so once the slices move every boot and every test collection fails. CLAUDE.md already bans import-time side effects; the providers are lru_cached, so a read at use costs one cache lookup.

== Size ==
10 prod files (9 readers + terraform/ssm.tf), ~+46/-45 LOC, plus decisions/configuration.md and doc-14 (written 2026-10-26 in the working tree, ride in this PR); 4 test files repatched, 1 new. The terraform line is an expand step with no reader, not a behaviour change, so the gate's mixing rule holds.

== Steps (TDD, red first) ==
A1 Tests: T-A1 (red today), then T-A2.
A2 Replace each import-time read with a provider call at use, and delete the module constant or module-level object:
- modules/incident/incident_folder.py:22-24 (SRE_INCIDENT_FOLDER, INCIDENT_LIST; 4 INCIDENT_LIST call sites :281, :315, :339, :377, plus the folder uses)
- modules/incident/incident.py:23-26 (INCIDENT_HANDBOOK_ID)
- modules/incident/schedule_retro.py:19-21 (CALENDAR_ID)
- modules/incident/incident_document.py:18-19 (INCIDENT_TEMPLATE, :37)
- modules/incident/incident_helper.py:34-35 (SRE_INCIDENT_FOLDER)
- modules/role/role.py:12-23 (nine talent constants)
- features/incident/drive/adapters/google_drive.py:24 (INCIDENT_TEMPLATE, :138)
- packages/talent/adapters/google_drive.py:15 (BOT_EMAIL, :28 and :48)
A3 modules/dev/incident.py:4,7: delete the unused INCIDENT_LIST and its import (dead code).
A4 Expand: terraform/ssm.tf sre_bot_secret_names gains "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL" (the Google delegation subject, a non-public value: decisions/configuration.md 2026-10-26). tf_apply on merge creates /sre-bot/GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL with the placeholder (value_wo) and a task-definition revision whose secrets: carry it; nothing reads it until TASK-111.10.2. Human after the apply (this plan says so): put-parameter the SRE_BOT_EMAIL blob value (H-A1).
A5 Docs (already in the working tree): decisions/configuration.md (non-public values rule, the Slack-credentials paragraph's Google sentence, tolerated GOOGLE_RESOURCES item, Checks, Changes), doc-14 (rows GOOGLE_DELEGATED_ADMIN_EMAIL, GOOGLE_RESOURCES, GOOGLE_WORKSPACE_CUSTOMER_ID, SRE_BOT_EMAIL, GCP_SRE_SERVICE_ACCOUNT_KEY_FILE; the twelfth parameter).

== Tests ==
T-A1 tests/unit/server/test_server_app_import_settings_lazy.py: in a subprocess, replace get_google_resources_config and get_google_workspace_settings with functions that raise, then import server.server, the six legacy modules and both adapters: the import succeeds. Red today (nine import-time calls). Stays valid after 111.10.2.
T-A2 Repatch the tests that patch the deleted constants (rg on 3eec058b: tests/modules/role/test_role.py 12, tests/modules/incident/test_incident_folder.py 10, tests/modules/incident/test_incident_document.py 1, tests/unit/packages/talent/adapters/test_talent_drive_adapter.py 2): patch the provider in the module under test; assertions unchanged.

AC -> step -> test: #1 A2,A3 / T-A1 ; #2 A2 / T-A2 ; #3 gates ; #4 A4 / terraform validate, tf_plan comment (1 to add, task definition changed), env-checks after H-A1.

== Doubts ==
(a) a test imports a deleted constant by name -> the red run after A2 lists them. (b) a provider reached inside a hot loop -> none found (each call site is one Slack command or one job run).

== Blast radius and rollback ==
Terraform: one new SecureString with the placeholder and one more secrets: entry; a deploy that registers the new revision starts fine (the parameter exists from the apply; its value is unread). An attribute slip in a legacy incident, role or talent path raises at use (each call site is covered by T-A2's tests); an import slip fails boot and the ECS circuit breaker rolls back. No value or name changes, so the previous image is fully compatible; one git revert restores.

== Merge gate and checks ==
H-A1 (human, after tf_apply succeeds): aws ssm put-parameter --region ca-central-1 --name /sre-bot/GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL --type SecureString --overwrite --value '<the SRE_BOT_EMAIL value from sre-bot-config>' (with the core-services profile, as for the 111.4 values); confirm: zsh bin/env-checks.zsh GOOGLE_WORKSPACE__ shows the parameter set, not placeholder. Also: Codespaces secret GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL from the current SRE_BOT_EMAIL Codespaces value (gh secret set ... --app codespaces -R cds-snc/sre-bot).
Gates from app/: ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership. zsh bin/deploy-checks.zsh pre at merge for the rollback tag. After deploy: zsh bin/deploy-checks.zsh post (generic: rollout, boot errors, Slack up, HTTP); no task check. Manual: /sre incident product list shows the product folders (a Drive read of incident_folder_id at use; the safe read, since /incident takes its text as a new incident title); /incident with no text opens the creation modal with the product folders and the handbook link, then cancel it (nothing is created until submit).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-26 on main 736d57bd (#1790 merged); plan approved by the human the same day.
- Readers moved to use: modules/incident/{incident_folder,incident_helper,incident,schedule_retro,incident_document}.py, modules/role/role.py (one local read per role submission), features/incident/drive/adapters/google_drive.py, packages/talent/adapters/google_drive.py. Dead INCIDENT_LIST and its import deleted from modules/dev/incident.py.
- Expand: terraform/ssm.tf adds GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL to sre_bot_secret_names (placeholder through value_wo, injected, unread). terraform validate OK; tflint shows only existing warnings.
- Docs riding here: decisions/configuration.md (non-public value rule, the Google sentence, tolerated GOOGLE_RESOURCES item, Checks, Changes), doc-14 (five Google rows, the twelfth parameter).
- Tests: new tests/unit/server/test_server_app_import_google_settings_lazy.py (fresh interpreter, both provider caches empty after importing server.server and every reader; red at 1 1 before the change). test_role, test_incident_folder, test_incident_document and test_talent_drive_adapter now patch the providers; the talent tests assert a concrete delegation email instead of the module constant.
- Gates: ruff check and format clean; mypy 47 = baseline (the two in touched files, role.py locale and incident.py chat_getPermalink, are on unchanged lines); pytest 5779 passed; import contracts 13 kept; key ownership OK.
- Found and queued: import-time settings reads in the Trello, OpsGenie, Sentinel and Notify clients (AC added to 111.12) and in modules/incident core.py and incident.py (AC added to 111.14).
- AC #4 waits on production evidence: tf_apply on merge, then H-A1 (put-parameter of the SRE_BOT_EMAIL value, Codespaces secret).

Merge gate 2026-10-26 19:28Z: pre run, rollback image_tag 736d57bda3e2e5c48943878528b4bd24170f5f3d-2026-10-26 (sre-bot-task:48, rollout COMPLETED, configured_systems slack and google); env-checks GOOGLE_WORKSPACE__ shows the delegated user's parameter missing, as expected before tf_apply.
<!-- SECTION:NOTES:END -->
