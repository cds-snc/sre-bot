---
id: TASK-45.5
title: >-
  Cut over atip: command namespace to COMMAND_PREFIX and channel-name prefix to
  ENVIRONMENT
status: Done
assignee:
  - '@me'
created_date: '2026-07-21 19:13'
updated_date: '2026-07-24 12:51'
labels:
  - phase-0
  - slack
milestone: m-0
dependencies:
  - TASK-45.1
references:
  - decisions/transport-slack.md
  - decisions/configuration.md
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1319'
parent_task_id: TASK-45
priority: high
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out) — atip has TWO PREFIX uses that split to different homes. (1) Command namespace at app/modules/atip/atip.py:37 (bot.command(f'/{prefix}atip'), f'/{prefix}aiprp')) -> read COMMAND_PREFIX. (2) SECOND use at atip.py:428 prefixes created CHANNEL names (dev-tmp-atip-...) -> this is NOT a command-namespace concern and must NOT read COMMAND_PREFIX; derive it from ENVIRONMENT (dev/local/ci get the 'dev-' style prefix, prod none) or an atip feature setting, per decisions/configuration.md (environment identity is orthogonal to platform-presentation config). Keep both resulting strings identical to today. Delete the atip baseline entry from prefix_readers.txt in the same PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 atip slash commands (/atip, /aiprp) build from COMMAND_PREFIX, not AppSettings.PREFIX
- [x] #2 atip channel-name prefixing (atip.py:428) derives from ENVIRONMENT or an atip feature setting, not AppSettings.PREFIX; a test proves the created channel name is unchanged for dev vs prod
- [x] #3 Pre/post command-name regression tests assert /atip and /aiprp register with the identical command string for COMMAND_PREFIX='' and 'dev-'
- [x] #4 atip baseline entry is removed from prefix_readers.txt and the TASK-1.3 guardrail still passes
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR references decisions/transport-slack.md and decisions/configuration.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Precedent: TASK-45.2 (sre/aws), TASK-45.3 (secret/talent-role), TASK-45.4 (incident) established the exact per-module command-namespace cutover pattern this task replicates for atip's FIRST prefix use; TASK-45.1 (Done) provides the settings home consumed here: infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX. atip's SECOND prefix use (channel-name prefixing) has its own precedent already in the codebase: app/modules/incident/incident_conversation.py:40-41 derives `channel_name_prefix = "incident-dev-" if settings.ENVIRONMENT != "production" else "incident-"` reading AppSettings.ENVIRONMENT directly (no new feature-settings class) — this task mirrors that exact condition/shape for atip instead of introducing a new atip feature setting, keeping the change minimal and consistent with an existing sibling pattern plus decisions/configuration.md's explicit allowance for features to read ENVIRONMENT for legitimate environment-conditional behavior.

Verified anchors:
- app/modules/atip/atip.py is the ONLY atip file reading PREFIX (grep confirms 9 hits, all in this one file: import at line 11, register() at lines 36-39, atip_view_handler() at lines 383/428-430). No other atip module file (__init__.py) touches PREFIX or get_app_settings.
- register() (lines 24-44): `app_settings = get_app_settings()` (36) then `prefix = app_settings.PREFIX if app_settings.PREFIX else ""` (37), used to build `f"/{prefix}atip"` (38) and `f"/{prefix}aiprp"` (39). No other line in register() depends on app_settings.
- atip_view_handler() (lines 381+): `app_settings = get_app_settings()` (383) used ONLY at line 428 for the channel-name prefix: `prefix = app_settings.PREFIX if app_settings.PREFIX else ""`; `if prefix: slug = f"{prefix}-{slug}"` (429-430); slug then passed to `client.conversations_create(name=f"{slug}")`. Today's real values: PREFIX="dev-" is set ONLY by app/Makefile's `dev`/`debug` targets (which run inside the devcontainer where docker-compose sets ENVIRONMENT=dev), so PREFIX="dev-" occurs exactly when ENVIRONMENT="dev" in current practice; PREFIX defaults to "" (unset) in CI (ENVIRONMENT=ci, confirmed .github/workflows/ci_code.yml:50-51) and in prod (ENVIRONMENT=production, no PREFIX set in terraform/templates/sre-bot.json.tpl). Using `ENVIRONMENT != "production"` (matching incident_conversation.py's precedent, not a dev/local/ci allowlist) reproduces byte-identical output for the two states the AC requires tested (dev vs prod) and is consistent with how the sibling incident module already treats every non-production environment identically for channel naming.
- app/server/lifespan.py:42,91 is the only caller of atip.register(bot) — no other registration path to update.
- app/bin/baselines/prefix_readers.txt lists `modules/atip/atip.py` (along with `infrastructure/configuration/app.py`, `server/lifespan.py`, `modules/incident/incident.py` — incident's entry was already removed by TASK-45.4 per its implementation notes, so post-45.4 the file should currently list only 3 entries; confirm at implementation time and remove the atip line only).
- app/bin/check_prefix_command_namespace.py's stale-entry rule requires atip's baseline line to be removed in the same change, or the guardrail fails (file no longer reads PREFIX -> 'Stale baseline entry' violation).
- Existing test home: app/tests/unit/modules/atip/test_atip.py (no current register()/channel-name-prefix assertions); app/tests/unit/modules/incident/test_incident_command_registration.py is the exact test-shape precedent to replicate (SimpleNamespace stub for get_slack_transport_settings, parametrized '' / 'dev-' cases, bot.command assertions).

Step 1 (AC#1) - app/modules/atip/atip.py register():
- Add import `from infrastructure.slack.settings import get_slack_transport_settings` alongside the existing `from infrastructure.configuration.app import get_app_settings` (keep get_app_settings import — still needed by atip_view_handler in Step 2).
- In register(), replace `app_settings = get_app_settings()` / `prefix = app_settings.PREFIX if app_settings.PREFIX else ""` with `transport_settings = get_slack_transport_settings()` and `prefix = transport_settings.COMMAND_PREFIX`. Keep `bot.command(f"/{prefix}atip")(atip_command)` and `bot.command(f"/{prefix}aiprp")(atip_command)` unchanged, and keep the following `bot.action(...)`/`bot.view(...)`/`bot.action(...)` lines untouched.

Step 2 (AC#2) - app/modules/atip/atip.py atip_view_handler():
- Keep `app_settings = get_app_settings()` (line 383, unchanged — still needed for ENVIRONMENT).
- Replace `prefix = app_settings.PREFIX if app_settings.PREFIX else ""` (line 428) with `prefix = "dev-" if app_settings.ENVIRONMENT != "production" else ""`, keeping the following `if prefix: slug = f"{prefix}-{slug}"` (429-430) and everything after (client.conversations_create, etc.) unchanged.

Step 3 (AC#4) - app/bin/baselines/prefix_readers.txt: remove the `modules/atip/atip.py` line (verify current file contents first — TASK-45.4 already removed incident's entry). Verify with `cd app && make check-prefix-guardrail` exits 0.

Step 4 (AC#3) - new regression tests, mirroring TASK-45.4's test_incident_command_registration.py:
- New file app/tests/unit/modules/atip/test_atip_command_registration.py: parametrized over COMMAND_PREFIX in {"", "dev-"}; monkeypatch `modules.atip.atip.get_slack_transport_settings` to return `SimpleNamespace(COMMAND_PREFIX=<value>)`; call `atip.register(MagicMock())`; assert `bot.command.assert_any_call("/atip")` and `bot.command.assert_any_call("/aiprp")` for prefix="" , and `.../dev-atip"` / `"/dev-aiprp"` for prefix="dev-" (use assert_any_call + call_count==2 since register() calls bot.command twice, unlike incident/sre's single call).

Step 5 (AC#2 test) - channel-name prefix regression test, added to app/tests/unit/modules/atip/test_atip.py (extending the existing `test_should_successfully_create_atip_channel` test area, matching its fixtures) or a new adjacent test function: parametrize over ENVIRONMENT in {"production", "dev"}; monkeypatch `modules.atip.atip.get_app_settings` to return a stub/SimpleNamespace exposing `.ENVIRONMENT` (and any other attributes atip_view_handler reads from app_settings — confirm via re-read of the function body that ENVIRONMENT is the only field used); call `atip.atip_view_handler(ack, body, say, client)` using the existing `make_view_submission_payload` fixture; assert `client.conversations_create.call_args.kwargs['name']` (or positional, matching existing call style `client.conversations_create(name=f"{slug}")`) equals the expected slug for each case: prod -> unprefixed slug (e.g. 'tmp-atip-<id>'), dev -> 'dev--tmp-atip-<id>' (double-dash preserved, matching current f"{prefix}-{slug}" join behavior) — this directly satisfies AC#2's 'test proves the created channel name is unchanged for dev vs prod' by pinning both literal values.

Test matrix:
- AC#1 -> Step 1 + Step 4: test_atip_command_registration.py (2 parametrized cases forcing both /atip and /aiprp).
- AC#2 -> Step 2 + Step 5: new channel-name-prefix test in test_atip.py (2 parametrized cases: production, dev).
- AC#3 -> Step 4 (command-string regression, '' and 'dev-').
- AC#4 -> Step 3: `cd app && make check-prefix-guardrail` exits 0 after baseline edit.
- Full-suite regression: `cd app && uv run pytest tests/unit/modules/atip tests/modules/atip -q` (legacy suite, if any, continues to cover unrelated atip behavior).

Assumptions/doubts:
(a) OPEN - confirm at implementation time whether prefix_readers.txt currently has 3 or 4 lines (incident's removal in TASK-45.4 may or may not have landed on this branch yet); remove only the atip line regardless.
(b) RESOLVED (design choice) - channel-name prefix derives directly from AppSettings.ENVIRONMENT (already-imported get_app_settings()), not a new atip feature settings field, mirroring incident_conversation.py's existing `ENVIRONMENT != \"production\"` pattern exactly; the pre-existing app/infrastructure/configuration/features/atip.py::AtipSettings (ATIP_ANNOUNCE_CHANNEL only) is left untouched — adding a field there for this single boolean-ish concern would be a wider, unnecessary change for a one-line derivation.
(c) OPEN - verify no other test in the suite (e.g. app/tests/unit/infrastructure/configuration/test_settings_delegation.py, test_feature_settings_singletons.py, which reference AtipSettings) breaks from this change; expected: no, since AtipSettings is untouched.
(d) RESOLVED - the pre-existing double-dash artifact in `f\"{prefix}-{slug}\"` when prefix already ends in '-' is preserved as-is (out of scope to fix per 'keep both resulting strings identical to today').

Blast radius: one production file edited (app/modules/atip/atip.py: 1 import added, register() 2 lines changed, atip_view_handler() 1 line changed - about 4-5 line-level changes), one baseline config file edited (1 line removed from prefix_readers.txt), one new test file (test_atip_command_registration.py, ~35-40 LOC) plus a small addition to the existing test_atip.py (~20-30 LOC for the channel-name-prefix cases). No lifespan.py, provider.py, or settings-home edits (already landed in TASK-45.1). No edit to infrastructure/configuration/features/atip.py. Single subsystem (legacy atip command-namespace + channel-naming source), no mixed refactor, well under the ~400 LOC/~10 file single-PR gate - same size class as the already-merged TASK-45.2/45.4.
Rollback: revert the PR; behavior reverts to reading AppSettings.PREFIX for both uses. Safe because PREFIX and SLACK__COMMAND_PREFIX are kept at the same value per environment during coexistence, and ENVIRONMENT already correlates 1:1 with today's real PREFIX values for the channel-name use, so a revert produces byte-identical /atip, /aiprp command names and channel-name slugs.

Size gate verdict: fits comfortably in a single PR, no decomposition needed - same scope class as the already-merged sibling per-module cutovers (TASK-45.2, TASK-45.4).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented TASK-45.5 cutover.\n\nCode changes:\n- app/modules/atip/atip.py: register() now reads command namespace from infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX for both /atip and /aiprp.\n- app/modules/atip/atip.py: channel-name prefixing in atip_view_handler now derives from ENVIRONMENT ("dev-" when ENVIRONMENT != "production", else "") instead of AppSettings.PREFIX; preserved existing join behavior, including the pre-existing double-dash artifact for dev (dev--tmp-atip-...).\n- app/bin/baselines/prefix_readers.txt: removed modules/atip/atip.py reader entry; additionally removed stale modules/incident/incident.py entry that was already migrated and was causing guardrail failure.\n\nTest changes:\n- Added app/tests/unit/modules/atip/test_atip_command_registration.py with COMMAND_PREFIX regression coverage for /atip and /aiprp ("" and "dev-").\n- Extended app/tests/unit/modules/atip/test_atip.py with ENVIRONMENT-based channel-name prefix regression coverage for production vs dev.\n\nValidation evidence:\n- Targeted regression tests: cd /workspace/app && uv run pytest tests/unit/modules/atip/test_atip_command_registration.py tests/unit/modules/atip/test_atip.py -q -> 22 passed.\n- Guardrail: cd /workspace/app && make check-prefix-guardrail -> clean tree.\n- Ruff: cd /workspace/app && uv run ruff check . -> pass.\n- Black check: cd /workspace/app && uv run black --check . -> pass.\n- Full pytest (excluding smoke): cd /workspace/app && uv run pytest tests --ignore=tests/smoke -> 2865 passed, 37 skipped.\n- Mypy: cd /workspace/app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> fails with pre-existing repository-wide errors outside this task scope (google_workspace/aws/incident/security modules), no new atip-specific typing regression observed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @copilot
created: 2026-07-22 14:58
---
Alignment (2026-07-22): command-namespace read moves to infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home); atip's SECOND PREFIX use (channel-name prefixing) moves to ENVIRONMENT/atip feature setting, NOT COMMAND_PREFIX. Smoke/new tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Transport move stays with TASK-26.
---
<!-- COMMENTS:END -->
