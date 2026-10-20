---
id: TASK-24.4
title: >-
  Move the Google Workspace settings to
  integrations/google_workspace/settings.py
status: Done
assignee: []
created_date: '2026-10-19 17:19'
updated_date: '2026-10-20 15:06'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
parent_task_id: TASK-24
priority: medium
ordinal: 402000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-24. A pure move of app/infrastructure/configuration/integrations/google.py: GoogleWorkspaceSettings (with its customer-id validator) and GoogleResourcesConfig (GOOGLE_RESOURCES, feature resource IDs, tolerated there until TASK-111 splits it into feature slices) to app/integrations/google_workspace/settings.py. Deletes the emptied infrastructure/configuration/integrations/ package and IntegrationSettings. Consumers: infrastructure/directory/factory.py, integrations/google_workspace/client.py, packages/talent/adapters/google_drive.py, features/incident drive and scribe adapters, server/lifespan.py, server/configured_systems.py (its Google TenantSource row), seven legacy modules/ files, and five import-linter ignores in pyproject.toml. Env names, defaults and validation unchanged.

Merge order: cut from main after #1722, #1723 and #1728 (Stack K layers 5 to 7) merged, because server/configured_systems.py imports the old path; all three are merged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GoogleWorkspaceSettings and GoogleResourcesConfig live in app/integrations/google_workspace/settings.py (the vendor-package contract allows only __init__.py, client.py and settings.py); app/infrastructure/configuration/integrations/ and IntegrationSettings are deleted
- [x] #2 Every consumer (server/configured_systems.py included) and test points at the new homes; env names, defaults and the customer-id validator are unchanged and covered by tests under tests/unit/integrations/google_workspace/
- [x] #3 The five import-linter ignores for infrastructure.configuration.integrations.google are removed and lint-imports passes
- [x] #4 decisions/configuration.md and decisions/outbound-clients.md name the new homes; GOOGLE_RESOURCES in the Google package is recorded as tolerated until TASK-111 splits it into feature slices
- [x] #5 ruff, mypy (no new errors in touched files), every CI freeze check (make check-*) and make test pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decisions (human, 2026-10-20):
- GoogleResourcesConfig (GOOGLE_RESOURCES) is feature data (inc/tal/aws/cal document IDs), not vendor config. Interim home: app/integrations/google_workspace/settings.py, beside the vendor slice, so features/packages adapters import it under contract (e) and five import-linter ignores go. Revised 2026-10-20 after CI on #1733: a separate resources.py broke the vendor-package contract freeze check (bin/check_vendor_package_contract.py allows only __init__.py, client.py and settings.py, and its baseline must not grow). Recorded as an ADR tolerance; the split into feature slices rides with TASK-111.
- The emptied app/infrastructure/configuration/integrations/ package is deleted here (it holds only google.py and its barrel); TASK-24.5 drops that item.
- IntegrationSettings (infrastructure/configuration/base.py) has no other subclass and is deleted. The new modules use BaseSettings with their own SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore"), like integrations/slack and integrations/trello (contract (d): integrations import nothing from infrastructure).
- Checked and dropped: non-dict GOOGLE_RESOURCES JSON is already rejected with a ValidationError (pydantic-settings decodes the dict field before _parse_resources), so there is no parse bug to fix.

Size gate: about 24 production files, but 17 of them are one-line import rewrites; about 270 LOC moved, net LOC slightly negative; one concern (settings location), no behavior change. Over the ~10-file guideline by mechanical count only; splitting would need a re-export shim that the next slice deletes. Kept as one PR.

Steps (TDD):
1. Tests first (fail on import):
   - tests/unit/integrations/google_workspace/test_google_workspace_settings_load.py: provider is a cached singleton; model_config env_file/case_sensitive/extra; reads GOOGLE_DELEGATED_ADMIN_EMAIL, SRE_BOT_EMAIL, GOOGLE_API_NUM_RETRIES, GOOGLE_API_TIMEOUT_SECONDS from env; defaults (customer id my_customer when the key file is unset, retries 3, timeout 10.0); timeout <= 0 rejected. Takes over the google cases of tests/unit/infrastructure/configuration/test_integration_settings_singletons.py and test_settings_structure.py.
   - tests/unit/integrations/google_workspace/test_google_workspace_settings_customer_id_validate.py: moved from tests/unit/infrastructure/configuration/ (same cases, new import).
   - tests/unit/integrations/google_workspace/test_google_workspace_resources_load.py: cached singleton; JSON env read maps to properties (incident_drive_id etc.); missing key returns ""; outer-quoted JSON accepted; non-dict JSON rejected.
2. Create app/integrations/google_workspace/settings.py (GoogleWorkspaceSettings and its validator, GoogleResourcesConfig, and both cached providers). Bodies are moved as they are: same aliases, defaults, validators, properties; docstring examples point at the new path; the stale "TASK-24 migrates" comment is dropped.
3. Delete app/infrastructure/configuration/integrations/ (google.py, __init__.py) and IntegrationSettings in infrastructure/configuration/base.py.
4. Repoint consumers: infrastructure/directory/factory.py, server/lifespan.py, server/configured_systems.py, integrations/google_workspace/client.py (sibling import), packages/talent/adapters/google_drive.py, features/incident/drive/adapters/google_drive.py, features/incident/scribe/adapters/google_docs.py, modules/aws/spending.py, modules/dev/incident.py, modules/role/role.py, modules/incident/{incident,incident_folder,schedule_retro,incident_helper,incident_document}.py.
5. Repoint tests in place: tests/integration/server/test_lifespan_security_settings_validation.py, test_lifespan_vendor_slice_validation.py, tests/unit/server/test_server_configured_systems_read.py, test_server_services_configured_systems_resolve.py, tests/unit/integrations/google_workspace/test_google_workspace_client.py, and monkeypatch string targets in test_factory.py, test_google_spreadsheet_provider.py, test_incident_scribe_draft_adapter.py (test_spending_handler.py patches modules.aws.spending.*, unchanged). Trim test_settings_structure.py of the google and IntegrationSettings cases; delete test_integration_settings_singletons.py and the old validator test.
6. app/pyproject.toml: remove the five ignores (contracts (a) and (d): integrations.google_workspace.client -> infrastructure.configuration.integrations.google; contract (b): incident drive, incident scribe, talent -> infrastructure.configuration.integrations.google); remove the dead pytest env GOOGLE_WORKSPACE__GCP_SRE_SERVICE_ACCOUNT_KEY_FILE (no slice reads that name).
7. ADRs: decisions/configuration.md Context (Google lives in integrations/google_workspace/settings.py) and Migration (replace the Google tolerance with: GOOGLE_RESOURCES feature resource IDs in integrations/google_workspace/settings.py until TASK-111 splits them into feature slices; dated Changes line); decisions/outbound-clients.md:75 updated.
8. Gates: ruff, mypy (0 in touched files), every CI freeze check (make check-*), make test, pytest tests --ignore=tests/smoke; rg for "configuration.integrations" and "IntegrationSettings" returns nothing under app/ and decisions/.

AC traceability: #1 -> steps 2-3, tests in step 1; #2 -> steps 4-5, step 1 tests (env names, defaults, validator); #3 -> step 6, lint-imports; #4 -> step 7; #5 -> step 8.

Blast radius and rollback: import-only change. A missed consumer fails at import, which pytest and mypy catch; module-level reads in legacy modules are unchanged. Env names, defaults and validation are unchanged, so no terraform/SSM change. One git revert restores it. Merge order: none beyond main (24.2 and 24.3 merged); TASK-24.5 builds on this.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented as planned, as a pure move; behaviour is unchanged.

- GoogleWorkspaceSettings and GoogleResourcesConfig are both in app/integrations/google_workspace/settings.py. A separate resources.py failed CI's vendor-package contract freeze check (only __init__.py, client.py and settings.py are allowed, and the baseline must not grow), so the resources config sits in the vendor module, documented as tolerated until TASK-111. Both classes use BaseSettings with their own SettingsConfigDict (env_file .env, case_sensitive, extra ignore), like the other vendor slices. app/infrastructure/configuration/integrations/ and IntegrationSettings (base.py) are deleted.
- 17 consumers were repointed with one-line import changes. The five import-linter ignores for infrastructure.configuration.integrations.google are removed from contracts (a), (b) and (d); lint-imports: 12 kept, 0 broken.
- Tests: new test_google_workspace_settings_load.py and test_google_workspace_resources_load.py, and test_google_workspace_settings_customer_id_validate.py moved, all under tests/unit/integrations/google_workspace/. test_integration_settings_singletons.py is deleted (its cases now live in the new files), and the Google cases are removed from test_settings_structure.py.
- Malformed GOOGLE_RESOURCES JSON fails with a pydantic-settings SettingsError naming the field 'resources', because the variable is decoded before the validator runs. A JSON list fails with a ValidationError naming GOOGLE_RESOURCES. Both are existing behaviour and are now pinned by tests.
- Dead pytest env entries removed from app/pyproject.toml: GOOGLE_WORKSPACE__GCP_SRE_SERVICE_ACCOUNT_KEY_FILE plus the AWS__*, SENTINEL__*, ATIP__* and TRELLO__* names. No settings class uses those prefixes, and the flat names they map to are still set.
- Stale ratchet entry modules/incident/incident_folder.py removed from bin/baselines/aws_platform_seam_consumers.txt. It was already stale on main: the file no longer imports packages.aws_platform.
- ADRs: configuration.md Context, Migration tolerance and a dated Changes line; outbound-clients.md closes the settings divergence.
- Sibling tasks synced: TASK-24.5 renamed, with the package deletion dropped and AC#4 reworded; TASK-111 now includes the GOOGLE_RESOURCES split.

Gates (every CI step run locally): make lint-ci and fmt-ci: pass (980 files formatted). check-sdk-typing, check-vendor-package-contract, check-aws-platform-seam, check-runtime-imports and check-fake-coverage: OK. check-import-contracts: 12 kept, 0 broken. make test: 4603 passed and 772 passed. pytest tests --ignore=tests/smoke: 5375 passed. mypy: 48 errors repo-wide, 0 new in touched files. Two pre-existing errors sit in touched legacy files, away from the changed import line: modules/role/role.py:322 [index] and modules/incident/incident.py:121 [no-any-return]. Both are on HEAD at the same lines and were left as they are.
<!-- SECTION:NOTES:END -->
