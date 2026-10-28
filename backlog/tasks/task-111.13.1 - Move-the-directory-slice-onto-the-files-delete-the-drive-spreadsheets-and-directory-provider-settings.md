---
id: TASK-111.13.1
title: >-
  Move the directory slice onto the files; delete the drive, spreadsheets and
  directory provider settings
status: In Progress
assignee: []
created_date: '2026-10-28T13:46:00Z'
updated_date: '2026-10-28T14:15:00Z'
labels:
  - configuration
milestone: m-7
dependencies: []
references:
  - decisions/configuration.md
  - decisions/workplace-systems.md
parent_task_id: TASK-111.13
type: feature
ordinal: 455000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice A of TASK-111.13. DirectorySettings becomes a ConfigurationSlice on [directory]; vendor choice is data, never a provider setting (decisions/workplace-systems.md), so the provider fields go and DriveSettings and SpreadsheetSettings with them; the unread directory keys are dead (decisions/lifecycle.md: no warmups; decisions/authorization.md owns the decision lifetime).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 DirectorySettings is a ConfigurationSlice reading [directory] with extra=forbid and the DIRECTORY__ prefix, require_startup_warmup its only key with its default in base.toml; the old flat DIRECTORY_* names are no longer read
- [x] #2 DIRECTORY_PROVIDER, DRIVE_PROVIDER and SPREADSHEET_PROVIDER are deleted, not moved; each factory builds the Google adapter directly and the entra_id path is gone; DriveSettings and SpreadsheetSettings are deleted and no file has a [drive] or [spreadsheets] table
- [x] #3 The Google directory, drive and spreadsheet adapters take no settings argument, and the unread cache_ttl_seconds, startup_warmup_timeout_seconds and startup_preload_groups are deleted
- [x] #4 An unknown or deleted key in [directory] fails boot naming it
- [ ] #5 Every retired name is in the env audit HINTS and app/.env.example holds none
- [x] #6 ruff, mypy (no new errors), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-10-28 against main 83f895ab from the TASK-111.13 plan (slice A); split, dead-code deletion and AC wording approved by the human 2026-10-28.

Findings (verified on main): production sets none of the DIRECTORY_*, DRIVE_PROVIDER or SPREADSHEET_PROVIDER names (doc-14, terraform, .github, .devcontainer); the only repo hit is a commented app/.env.example:52. Only require_startup_warmup is read (server/lifespan.py:174); cache_ttl_seconds, startup_warmup_timeout_seconds and startup_preload_groups have no reader and contradict lifecycle.md (no warmups) and authorization.md (the decision lifetime is authorization's), so they are deleted. The Google directory, drive and spreadsheet adapters store a settings argument and never read it. No import-time reads.

Steps (tests first, red, then code):
1. infrastructure/directory/settings.py: DirectorySettings(ConfigurationSlice), toml_table_header ("directory",), env_prefix "DIRECTORY__", extra forbid; only require_startup_warmup: bool = False; provider and the three dead fields deleted; docstring lists the key.
2. infrastructure/directory/factory.py, google.py, __init__.py: build_google_directory_provider and GoogleDirectoryProvider lose the settings argument; get_directory_provider builds the Google provider directly (no provider branch, no entra_id ValueError).
3. infrastructure/drive/ and infrastructure/spreadsheets/: settings.py deleted; factory builds the Google adapter directly; google.py drops the settings argument; __init__.py exports drop the settings class and getter.
4. app/config/base.toml: [directory] require_startup_warmup = false, with a comment that the Google directory is the only implementation. No [drive] or [spreadsheets]. Environment files unchanged.
5. app/bin/audit_env_names.py HINTS: DIRECTORY_REQUIRE_STARTUP_WARMUP -> [directory] require_startup_warmup; DIRECTORY_PROVIDER, DIRECTORY_CACHE_TTL_SECONDS, DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS, DRIVE_PROVIDER, SPREADSHEET_PROVIDER -> deleted (follow the existing shape for a retired name).
6. app/.env.example: remove the commented DIRECTORY_* lines.
7. Docs: decisions/workplace-systems.md, authorization.md:17, lifecycle.md:16 current-state lines; configuration.md 2026-10-28 rules ride here; doc-14 facts line; TASK-128 AC #1 names DIRECTORY__REQUIRE_STARTUP_WARMUP.

Tests: tests/unit/infrastructure/directory/test_directory_settings_load.py (default from base.toml, file and DIRECTORY__ override, unknown and deleted keys fail naming them, old flat names unread); test_directory_factory_google.py, drive and spreadsheets factory tests (Google adapter built directly, no settings argument); drive and spreadsheet settings tests deleted, a test asserts their modules no longer import; tests/unit/infrastructure/configuration/test_configuration_files_hosting.py ([directory] has only require_startup_warmup, no [drive]/[spreadsheets]/provider key in any file); tests/integration/server/test_lifespan_hosting_slice_validation.py (unknown [directory] key stops startup naming it); production-names rows become retired-names-unread; HINTS cases.

Gates from app/: ruff, mypy (baseline 47), pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership.
Rollout: merge deploys; no terraform, SSM or task-definition change; values unchanged (require_startup_warmup default false, production does not set it). Circuit breaker rolls back a failed boot; one git revert undoes it. Generic deploy-checks pre/post only.
Human: make env-checks after merge lists any retired name left in Codespaces or app/.env.
~15 production files (2 deleted), ~250 LOC changed, net negative.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
DirectorySettings is now a ConfigurationSlice on [directory] (DIRECTORY__ prefix, extra=forbid) with require_startup_warmup as its only key, default false in base.toml. provider, cache_ttl_seconds, startup_warmup_timeout_seconds and startup_preload_groups are deleted as dead code; DriveSettings and SpreadsheetSettings and their settings.py files are deleted. The directory, drive and spreadsheet factories build the Google adapters directly (no entra_id branch), and the three Google adapters and the directory builder drop their unread settings argument. audit_env_names HINTS: DIRECTORY_REQUIRE_STARTUP_WARMUP maps to the new key; the five deleted names map to 'nothing (deleted: ...)', and the verdict text no longer reads 'set nothing instead'. Docs: workplace-systems, authorization:17, lifecycle:16, configuration (dated 2026-10-28 lines), doc-14 facts line. Tests: new directory settings load, hosting config files and lifespan hosting validation tests; factory, adapter and production-names tests updated; the three old settings tests deleted; 2 audit-name tests added. Not done: app/.env.example (read denied by permission settings) still needs the commented DIRECTORY_* lines near line 52 removed by the human, so AC 5 is left unchecked. Gates from app/: ruff clean; mypy 47 errors (baseline 47); pytest 6021 passed, 0 failed; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK.

Review (human): the DIRECTORY_PROVIDER deletion stands (a one-value switch cannot serve Google and Entra at once; DirectoryProvider is the extension point). Docstring, base.toml comment and the DIRECTORY_PROVIDER hint now say the directory follows the IdP in the data, Google the only adapter today; Entra adapter tracked as TASK-174 (unscheduled).
<!-- SECTION:NOTES:END -->
