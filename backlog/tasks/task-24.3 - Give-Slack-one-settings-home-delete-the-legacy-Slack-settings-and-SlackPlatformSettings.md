---
id: TASK-24.3
title: >-
  Give Slack one settings home: delete the legacy Slack settings and
  SlackPlatformSettings
status: In Progress
assignee: []
created_date: '2026-10-19 17:18'
updated_date: '2026-10-20 13:44'
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
ordinal: 401000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-24. Slack has three settings homes: app/integrations/slack/settings.py (kept), app/infrastructure/configuration/integrations/slack.py (bare names ENABLED, SOCKET_MODE, APP_TOKEN, SLACK_TOKEN; no production consumer) and SlackPlatformSettings in app/infrastructure/configuration/infrastructure/platforms.py (env_prefix SLACK_, reads the same names as the kept slice; no production consumer). Deleting the two dead homes leaves SLACK_ENABLED defined once (the interim transport switch until TASK-112, SLACK_TEAM_ID required when on).

INCIDENT_CHANNEL and SLACK_SECURITY_USER_GROUP_ID stay owned by the incident feature slice (infrastructure/configuration/features/incident.py), which moves with its rebuild.

Independent of Stack K: app/server/configured_systems.py (#1728) reads the kept slice. The Slack tenant entry is TASK-24.5.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/infrastructure/configuration/integrations/slack.py, SlackPlatformSettings and its empty PlatformsSettings container (the whole infrastructure/configuration/infrastructure/platforms.py) are deleted with their barrel exports, tests of them and the pytest env entries only they read; app/integrations/slack/settings.py is the only Slack vendor slice and no importer of the deleted names remains
- [x] #2 SLACK_ENABLED, SLACK_SOCKET_MODE, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET, INCIDENT_CHANNEL and SLACK_SECURITY_USER_GROUP_ID are each read by exactly one settings class (the first five by integrations/slack/settings.py, the last two by the incident feature slice), shown by an rg sweep of every settings class recorded in the notes; the kept slice's names, defaults and validation are unchanged
- [x] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [x] #4 decisions/configuration.md (current-state, SLACK_ENABLED and tolerated-dual-homes lines) and decisions/transport-slack.md (platforms.py duplicate) record Slack's single settings home, each with a dated Changes line
- [x] #5 Dead and deprecated Slack settings leftovers found on the way are gone: the unused mock_settings fixture in tests/unit/server/conftest.py, the stale slack.SLACK_TOKEN docstring example in tests/conftest.py and comment in tests/integration/test_app_state_initialization.py, and the from __future__ import in app/infrastructure/slack/settings.py
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Slice 3 of TASK-24. Remove the two dead Slack settings homes and leave app/integrations/slack/settings.py as the only Slack vendor slice, plus the dead and deprecated Slack settings leftovers found on the way (clean up as we go). No env name, default or validation of the kept slice changes (renames ride with TASK-111; the tenant entry is TASK-24.5; the transport key is TASK-112). Same shape as TASK-24.1 and 24.2. Independent of Stack K: server/configured_systems.py:20 and server/lifespan.py:40 already read the kept slice.

Branch from an up-to-date main (24.2 merged). Commit 1: the TASK-24.3 planning edits. Commit 2: the deletion.

Design decisions
- The whole file app/infrastructure/configuration/infrastructure/platforms.py is deleted, not only SlackPlatformSettings. PlatformsSettings has one field (slack) and get_platforms_settings has no production caller, so keeping the container would leave an empty aggregator that decisions/configuration.md (no aggregator of all settings) and decisions/transport-slack.md (the duplicate is "deleted rather than extended") end-state removes anyway. Nothing is left for TASK-24.5, 24.6, 111, 112 or 156 to delete or move.
- app/infrastructure/configuration/integrations/slack.py is deleted and its two barrel exports go. The integrations/ package keeps Google until TASK-24.4 moves it and TASK-24.5 deletes the empty package; this slice does not touch google.py or the barrel's Google lines.
- INCIDENT_CHANNEL, SLACK_SECURITY_USER_GROUP_ID and SLACK_NOTIFY_MGMT_USER_GROUP_ID stay on IncidentFeatureSettings (features/incident.py:29-31) untouched: it moves with the incident rebuild. Deleting the legacy slice is what makes it their only reader (today both classes read the first two).
- SLACK_ENABLED stays defined once, on integrations/slack/settings.py:43, as the interim transport switch with SLACK_TEAM_ID required when on (until TASK-112); nothing is added or changed in that file. No SlackSettings field, alias or validator changes, so TASK-24.5 adds the tenant entry to an unmodified slice.
- Tests of deleted classes are deleted, not ported: the kept slice already has tests/unit/integrations/slack/test_slack_settings.py and tests/integration/server/test_lifespan_vendor_slice_validation.py. Tests that only used SlackPlatformSettings as a provider settings fixture use a SimpleNamespace stub (the pattern in tests/unit/integrations/slack/conftest.py and tests/unit/server/plugins/test_server_plugins_slack_listener_scoping.py:74), because the kept SlackSettings is alias-only and requires SLACK_TEAM_ID when enabled.
- Stale pytest env entries that only the deleted classes read are removed from app/pyproject.toml (a bug in a touched area, not left behind).
- No new test for AC2: deleting the second reader is the change, and an rg sweep of every settings class (aliases, env_prefix plus field names) recorded in the implementation notes is the evidence. TASK-24.6's single-owner check is the automated proof; nothing is written here that 24.6 would delete.
- Dead and deprecated leftovers go in this PR: the unused mock_settings fixture in tests/unit/server/conftest.py (no user; attributes of a removed aggregator), the stale 'slack.SLACK_TOKEN' example in the make_mock_settings docstring (tests/conftest.py:408-411,430; the factory itself is used by tests/integration/conftest.py:120), the stale SLACK_TOKEN comment at tests/integration/test_app_state_initialization.py:107, and the deprecated `from __future__ import annotations` in app/infrastructure/slack/settings.py:7 (PEP 649/749 baseline).

Call sites found (path:line)
- Definitions: infrastructure/configuration/integrations/slack.py:8-41 (SlackSettings, get_slack_settings; bare names ENABLED, SOCKET_MODE, APP_TOKEN, SLACK_TOKEN plus INCIDENT_CHANNEL and SLACK_SECURITY_USER_GROUP_ID); infrastructure/configuration/infrastructure/platforms.py:14-103 (SlackPlatformSettings, env_prefix SLACK_), :106-139 (PlatformsSettings, get_platforms_settings).
- Barrels: infrastructure/configuration/integrations/__init__.py:9-12,15,18; infrastructure/configuration/infrastructure/__init__.py:3-7,26-28.
- Production consumers: none. Aggregators that compose the classes: PlatformsSettings.slack only (platforms.py:130); no root Settings, no providers.py entry, no lifespan or server reference (rg over app/ excluding tests). The kept slice is read at server/configured_systems.py:20,57; server/lifespan.py:40,251; packages/oncall_sync/adapters/slack.py (USER_TOKEN) and integrations/slack/provider.py.
- Tests that import the deleted names: tests/unit/infrastructure/configuration/test_platforms.py:5-8,12-93 (whole file); tests/unit/infrastructure/platforms/test_configuration_validation.py:5-7,10-80 (whole file, only file in the dir); tests/unit/infrastructure/configuration/test_infra_settings_singletons.py:3-6,67-79; tests/unit/infrastructure/configuration/test_integration_settings_singletons.py:9-12,15-28; tests/unit/infrastructure/configuration/test_settings_structure.py:33-37,105,128; tests/unit/integrations/slack/test_slack_auto_registration.py:14-17,26-33 (fixture make_slack_settings).
- Tests with stale mock names only (no import; cleaned up in step 4): tests/unit/server/conftest.py:19-31 (unused mock_settings fixture); tests/conftest.py:411,430 (docstring example); tests/integration/test_app_state_initialization.py:107 (comment).
- Deprecated construct: app/infrastructure/slack/settings.py:7 `from __future__ import annotations` (no other __future__ import in infrastructure/configuration or the touched tests).
- Config: app/pyproject.toml:134 (SLACK_TOKEN), :138 (APP_TOKEN), :163-164 (SLACK__SLACK_TOKEN, SLACK__APP_TOKEN), :169 (SLACK__SLACK_SECURITY_USER_GROUP_ID): read only by the deleted legacy slice (the SLACK__ names were already dead). Kept: :133 SLACK_ENABLED, :135-137 SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET, :151-152 SLACK_SECURITY_USER_GROUP_ID, SLACK_NOTIFY_MGMT_USER_GROUP_ID. No import-linter entry names the deleted modules.
- Not affected (verified): terraform/ (only SLACK__COMMAND_PREFIX at templates/sre-bot.json.tpl:70); .github/workflows (SLACK__COMMAND_PREFIX at ci_code.yml:75, webhook secrets only); app/bin (no Slack settings reference); app/Makefile:4,12 (SLACK__COMMAND_PREFIX); app/.env.example as it stands on the 24.2 branch (lines 23-27, 57 name SLACK_ENABLED, SLACK_APP_TOKEN, SLACK_BOT_TOKEN, SLACK_TEAM_ID, SLACK_DEV_MSG_CHANNEL, INCIDENT_CHANNEL, SLACK_SECURITY_USER_GROUP_ID, SLACK_NOTIFY_MGMT_USER_GROUP_ID; none is a deleted-only name). The file is outside the planner's read permission, so this was checked through the committed copy; the implementer re-checks it.
- Env-name ownership today (case-sensitive): SLACK_ENABLED, SLACK_SOCKET_MODE, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET are each read by integrations/slack/settings.py and by SlackPlatformSettings; INCIDENT_CHANNEL and SLACK_SECURITY_USER_GROUP_ID by the legacy SlackSettings and IncidentFeatureSettings. The legacy class never read SLACK_ENABLED (it read bare ENABLED), so decisions/configuration.md's "defined in three slices" counts fields, not variables. Other SLACK* names are single-owner and outside the AC: SLACK_TEAM_ID, SLACK_USER_TOKEN, SLACK_REQUEST_TIMEOUT_SECONDS, SLACK_RETRY_MAX_ATTEMPTS, SLACK_TRANSIENT_RETRY_AFTER_SECONDS and the three SLACK_*_ERRORS (kept slice); SLACK_NOTIFY_MGMT_USER_GROUP_ID (incident); SLACK_DEV_MSG_CHANNEL (infrastructure/configuration/infrastructure/server.py:60); SLACK__COMMAND_PREFIX (infrastructure/slack/settings.py:25). No env_prefix or validation_alias elsewhere reads a SLACK name (only ACCESS_ at packages/access/common/settings.py:133).
- Docs: decisions/configuration.md:15 (two-homes line), :16 (SLACK_ENABLED "defined in three slices"), :80 (dual-vendor-homes tolerance); decisions/transport-slack.md:14 (platforms.py "still duplicates"), :72 (tolerated duplicate bullet).

Steps (red to green through existing tests: no new behaviour, so the edited tests and the full suite are the safety net)
1. Delete app/infrastructure/configuration/integrations/slack.py and app/infrastructure/configuration/infrastructure/platforms.py. Remove the Slack imports and __all__ entries from integrations/__init__.py and the platforms imports and __all__ entries from infrastructure/__init__.py (Google, retry and server lines stay).
2. Delete tests/unit/infrastructure/configuration/test_platforms.py and tests/unit/infrastructure/platforms/test_configuration_validation.py (and the emptied directory). Edit in place: test_infra_settings_singletons.py (drop the platforms import and TestPlatformsSettingsSingleton); test_integration_settings_singletons.py (drop the Slack import and TestSlackSettingsSingleton; Google classes stay); test_settings_structure.py (drop SlackSettings from the barrel import, the instances list, and replace the issubclass check with GoogleWorkspaceSettings); test_slack_auto_registration.py (make_slack_settings returns SimpleNamespace(ENABLED, SOCKET_MODE, APP_TOKEN, BOT_TOKEN)). Imports stay at module top level.
3. app/pyproject.toml: remove the five dead env entries listed above.
4. Cleanup: delete the unused mock_settings fixture in tests/unit/server/conftest.py (and any import it alone used); change the make_mock_settings docstring example to a live key ('idempotency.IDEMPOTENCY_TTL_SECONDS', as tests/integration/conftest.py uses) at tests/conftest.py:411 and :430; reword the comment at tests/integration/test_app_state_initialization.py:107 to name SLACK_ENABLED; remove `from __future__ import annotations` from app/infrastructure/slack/settings.py.
5. Docs: decisions/configuration.md:15 (Slack now lives only in integrations/slack/settings.py; Google is the one vendor still in infrastructure/configuration/integrations/), :16 (SLACK_ENABLED is defined once, interim transport switch, still mixing the two meanings), :80 (dual homes now Google only) and a dated Changes line (2026-10-20, TASK-24.3); decisions/transport-slack.md:14 (drop the platforms.py clause), :72 (remove the closed tolerance bullet) and a dated Changes line.
6. Gates from app/: ruff check ., ruff format --check ., lint-imports, mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 new errors in touched files), pytest tests --ignore=tests/smoke. Then the AC evidence sweeps, recorded in the notes: rg -n "SlackPlatformSettings|get_platforms_settings|PlatformsSettings|configuration\.integrations\.slack|configuration/integrations/slack|get_slack_settings" app shows only integrations.slack.settings users; for each of the seven names, rg over app/ (excluding tests) for the alias and for env_prefix="SLACK_" shows one settings class.

AC traceability
- AC1 (deleted; one Slack vendor slice) <- steps 1, 2, 3; evidence: step 6 rg sweep; test_slack_auto_registration.py and test_settings_structure.py still import and pass.
- AC2 (each of the seven names read once) <- steps 1, 3; evidence: step 6 per-name rg sweep in the notes; the kept slice's tests (tests/unit/integrations/slack/test_slack_settings.py) pass unchanged.
- AC3 (gates) <- step 6.
- AC4 (docs) <- step 5.
- AC5 (dead and deprecated leftovers) <- step 4; evidence: rg for mock_settings in tests/unit/server, slack.SLACK_TOKEN in tests and __future__ in infrastructure/slack returns nothing; the full suite passes.
Every step maps to an AC.

Test matrix: happy (kept-slice tests and legacy_surface/ provider tests pass unchanged; the provider auto-registration tests pass with the stub; SlackTransportSettings tests pass without the __future__ import); boundary and failure are covered by the existing kept-slice validation tests (SLACK_TEAM_ID required when enabled); no new test file; no authorization or idempotency surface.

Size gate: production files 4 edited or deleted (slack.py -41, platforms.py -139, two barrels about -12) plus pyproject.toml (-5) and 2 ADR files (about 8 lines changed); about 200 LOC, almost all deletions; one subsystem (app configuration); no mechanical-plus-behaviour mix; revertible by one git revert. Tests: 2 deleted, 7 edited; 1 production file gains a one-line deletion. Passes the gate.

Assumptions and doubts
- No runtime reader of the deleted classes: assumed from rg over app/, terraform/, .github/, app/bin (done 2026-10-20). Verify: step 6 rg plus the full pytest run.
- Removing SLACK_TOKEN and APP_TOKEN from the pytest env breaks no test: they were read only by the deleted legacy slice. Verify: run pytest after step 4 (single-process run shows the known TASK-90 order failures; use make test for the green baseline).
- Production sets none of the deleted-only names (bare ENABLED, SOCKET_MODE, APP_TOKEN, SLACK_TOKEN) in a way that matters: nothing reads them after the deletion, so a leftover value is ignored (extra="ignore"). The SSM sre-bot-config values are not visible to the planner; TASK-111's SSM inventory (AC6) covers them.
- Merge order with 24.2: the plan touches test_infra_settings_singletons.py and decisions/configuration.md, both edited by 24.2 (adjacent hunks, Changes line appended at the end). Cut the PR from main after 24.2 merges, or rebase onto it. 24.2's other files (app.py, server.py, security/*, lifespan.py) do not overlap.

Blast radius and rollback: an import error would stop the app at import; covered by the full pytest run. The kept slice is untouched, so Slack behaviour cannot change. One git revert restores everything; no env, terraform or deploy change; no ordering constraint with 24.4 (disjoint Google lines, but both edit test_integration_settings_singletons.py and the integrations barrel: merge one then rebase the other) or 24.5.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Deleted app/infrastructure/configuration/integrations/slack.py and the whole infrastructure/configuration/infrastructure/platforms.py (SlackPlatformSettings plus the empty PlatformsSettings container), their barrel exports, test_platforms.py and tests/unit/infrastructure/platforms/ (whole directory). Edited in place: test_infra_settings_singletons.py, test_integration_settings_singletons.py, test_settings_structure.py (Google class now carries the base-class check), test_slack_auto_registration.py (SimpleNamespace stub). Removed five pytest env entries only the legacy slice read: SLACK_TOKEN, APP_TOKEN, SLACK__SLACK_TOKEN, SLACK__APP_TOKEN, SLACK__SLACK_SECURITY_USER_GROUP_ID.

Clean-up (AC5 and beyond the plan): deleted the unused mock_settings fixture in tests/unit/server/conftest.py; the make_mock_settings docstring in tests/conftest.py now shows live keys; the comment in tests/integration/test_app_state_initialization.py names SLACK_ENABLED; removed the deprecated from __future__ import in infrastructure/slack/settings.py. Not in the plan: integrations/slack/provider.py still described its settings as SlackPlatformSettings (an untyped constructor parameter, the settings property, and a docstring example importing a name the configuration barrel never exported). Both are now typed as the kept SlackSettings and the example calls get_slack_settings(); no behaviour change.

AC2 evidence (rg over app/ excluding tests and .venv): each name has one owner. SLACK_ENABLED integrations/slack/settings.py:43, SLACK_SOCKET_MODE :44, SLACK_BOT_TOKEN :51, SLACK_APP_TOKEN :53, SLACK_SIGNING_SECRET :54; INCIDENT_CHANNEL and SLACK_SECURITY_USER_GROUP_ID infrastructure/configuration/features/incident.py:29-30. No settings class uses env_prefix SLACK_. No match left for SlackPlatformSettings, PlatformsSettings, get_platforms_settings, configuration.integrations.slack or configuration.infrastructure.platforms. The bare legacy names ENABLED, SOCKET_MODE, APP_TOKEN and SLACK_TOKEN have no reader now.

ADRs: configuration.md (current state, SLACK_ENABLED read by one slice, tolerance narrowed to Google) and transport-slack.md (platforms.py clause and tolerance bullet removed), each with a 2026-10-20 Changes line.

Gates (from app/, 2026-10-20): ruff check . All checks passed; ruff format --check . 976 files already formatted; lint-imports 12 kept, 0 broken; mypy . Found 48 errors in 19 files, 0 in touched files; pytest tests --ignore=tests/smoke 5354 passed.

Merge order: TASK-24.2 (in review) also edits test_infra_settings_singletons.py and decisions/configuration.md. Whichever merges second rebases; the expected conflict is the two Changes lines at the end of configuration.md (keep both, in date order).
<!-- SECTION:NOTES:END -->
