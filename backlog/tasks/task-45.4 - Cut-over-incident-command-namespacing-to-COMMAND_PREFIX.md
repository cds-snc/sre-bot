---
id: TASK-45.4
title: Cut over /incident command namespacing to COMMAND_PREFIX
status: Done
assignee:
  - '@me'
created_date: '2026-07-21 19:13'
updated_date: '2026-07-22 18:44'
labels:
  - phase-0
  - slack
milestone: m-0
dependencies:
  - TASK-45.1
references:
  - decisions/transport-slack.md
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1318'
parent_task_id: TASK-45
priority: high
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out) — largest user surface, isolated in its own PR. Swap the module-level PREFIX in app/modules/incident/incident.py (PREFIX = app_settings.PREFIX at line 25, used at line 39 for bot.command(f'/{PREFIX}incident')) to read COMMAND_PREFIX; keep registration and all other incident behavior identical. Verify no OTHER incident file derives a command name from AppSettings.PREFIX. Delete the incident baseline entry from app/bin/baselines/prefix_readers.txt in the same PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/modules/incident/incident.py builds /incident from COMMAND_PREFIX, not AppSettings.PREFIX; no other incident behavior changes
- [x] #2 Pre/post command-name regression tests assert /incident registers with the identical command string for COMMAND_PREFIX='' and 'dev-'
- [x] #3 incident baseline entry is removed from prefix_readers.txt and the TASK-1.3 guardrail still passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Precedent: TASK-45.2 (sre/aws cutover, commit 52942363, already merged to main) established the exact per-module pattern this task replicates for /incident. TASK-45.1 (Done) provides the settings home consumed here: infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX.

Step 1 (AC#1) - app/modules/incident/incident.py:
- Replace the import at line 10 `from infrastructure.configuration.app import get_app_settings` with `from infrastructure.slack.settings import get_slack_transport_settings`.
- Remove the two module-level lines `app_settings = get_app_settings()` (line 22) and `PREFIX = app_settings.PREFIX` (line 25). Keep `incident_settings = get_incident_settings()`, `google_resource = get_google_resources_config()`, and `INCIDENT_CHANNEL = incident_settings.INCIDENT_CHANNEL` unchanged, same relative order.
- In register() (currently `bot.command(f"/{PREFIX}incident")(open_create_incident_modal)`), add `transport_settings = get_slack_transport_settings()` as the function's first line, then change the bot.command call to `bot.command(f"/{transport_settings.COMMAND_PREFIX}incident")(open_create_incident_modal)`. The next two lines (`bot.view("incident_view")(submit)`, `bot.action("incident_change_locale")(handle_change_locale_button)`) stay untouched.

Step 2 (AC#1, verification only, no code change) - confirmed no OTHER incident file derives a command name from AppSettings.PREFIX:
- app/modules/incident/core.py imports get_app_settings but only reads `.ENVIRONMENT` (lines ~300, ~430, ~573) - unrelated to PREFIX, no edit.
- app/modules/incident/incident_conversation.py imports get_app_settings and reads only `.ENVIRONMENT` for its `channel_name_prefix` branch (line ~40: `"incident-dev-" if settings.ENVIRONMENT != "production" else "incident-"`) - this is the ENVIRONMENT-derived channel-naming concern (parallel to atip's out-of-scope "second use" called out in decisions/migration.md), already on ENVIRONMENT today, not PREFIX - no edit needed.
- app/modules/incident/incident_folder.py's "incident-"/"incident-dev-" strings are literals unrelated to any settings read - no edit.

Step 3 (AC#3) - app/bin/baselines/prefix_readers.txt: remove the `modules/incident/incident.py` line, in the same commit as Step 1 (the guardrail's stale-entry rule flags a baseline entry whose file no longer reads PREFIX). Verify: `cd app && make check-prefix-guardrail` exits 0.

Step 4 (AC#2) - new regression tests, mirroring TASK-45.2's test_sre_command_registration.py / test_aws_command_registration.py exactly:
- New file app/tests/unit/modules/incident/__init__.py (empty package marker, matching sibling aws/sre/role/secret/atip test dirs).
- New file app/tests/unit/modules/incident/test_incident_command_registration.py: parametrized over COMMAND_PREFIX in {"", "dev-"}; monkeypatch `modules.incident.incident.get_slack_transport_settings` to return `SimpleNamespace(COMMAND_PREFIX=<value>)`; call `incident.register(MagicMock())`; assert `bot.command.assert_called_once_with("/incident")` (prefix="") and `"/dev-incident"` (prefix="dev-"). bot.view()/bot.action() calls in register() are inert on the MagicMock (same shape as aws's bot.view() calls in TASK-45.2's test).

Test matrix:
- AC#1 -> Step 1 + Step 2: Step 1 covered indirectly by Step 4's tests (they only pass if the source is COMMAND_PREFIX, not AppSettings.PREFIX); Step 2 is a grep-verified research note, no new test artifact (matches TASK-45.2's precedent for its own "no other reader" assumption).
- AC#2 -> Step 4: test_incident_command_registration.py, 2 parametrized cases (empty-prefix, dev-prefix).
- AC#3 -> Step 3: `cd app && make check-prefix-guardrail` exits 0 post-edit.
- Full-suite regression: `cd app && uv run pytest tests/unit/modules/incident tests/modules/incident -q` - the legacy suite (tests/modules/incident/test_incident.py et al.) continues to cover open_create_incident_modal/submit/core behavior untouched by this change.

Assumptions/doubts:
(a) Assumes get_app_settings()/AppSettings.PREFIX is read in incident.py only at the import line + the two module-level assignments removed in Step 1 - verified by grep (3 hits total: import, `app_settings = get_app_settings()`, `PREFIX = app_settings.PREFIX`; no other reference in the file). Ruff F401 will also catch a leftover unused import if missed.
(b) Assumes app/server/lifespan.py:96 (`incident.register(bot)`) is the only caller of register() - verified by grep; no lifespan.py edit in scope.
(c) Assumes the new test directory app/tests/unit/modules/incident/ (parallel to legacy app/tests/modules/incident/) is the correct home for the new registration test, matching the TASK-45.2 precedent for sre/aws rather than extending the legacy test_incident.py file, for consistency across the 45.2/45.3/45.4 per-module cutover PR series. If reviewers prefer extending test_incident.py instead, this is a one-file relocation, not a scope change.

Blast radius: one production file edited (app/modules/incident/incident.py: 1 import swap, 2 line removals, register() gains 1 line and 1 changed line - about 5 line-level changes total), one baseline config file edited (1 line removed from prefix_readers.txt), two new test files (__init__.py + test file, ~35 LOC). No lifespan.py, provider.py, or settings-home edits (those landed in TASK-45.1/45.2). No edit to incident_conversation.py, core.py, or incident_folder.py. Single subsystem (legacy /incident command-namespace source), no mixed refactor, well under the ~400 LOC/~10 file single-PR gate - same size class as the already-merged TASK-45.2 (sre+aws, two modules) but for one module, so smaller.
Rollback: revert the PR; behavior reverts to reading AppSettings.PREFIX. Safe because PREFIX and SLACK__COMMAND_PREFIX are kept at the same value per environment during coexistence (decisions/transport-slack.md), so a revert produces a byte-identical /incident command name.

Size gate verdict: fits comfortably in a single PR, no decomposition needed - smaller in scope than the already-merged TASK-45.2 (one module vs two).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented TASK-45.4 incident command-prefix cutover.

What changed:
- app/modules/incident/incident.py now imports get_slack_transport_settings from infrastructure.slack.settings and builds /incident from transport_settings.COMMAND_PREFIX inside register().
- Removed legacy AppSettings.PREFIX read in incident.py (deleted get_app_settings import, app_settings assignment, and PREFIX constant).
- Removed modules/incident/incident.py from app/bin/baselines/prefix_readers.txt.
- Added behavior regression tests in app/tests/unit/modules/incident/test_incident_command_registration.py (COMMAND_PREFIX='' -> /incident, COMMAND_PREFIX='dev-' -> /dev-incident).

Verification evidence:
- cd app && uv run pytest tests/unit/modules/incident tests/modules/incident -q -> 288 passed.
- cd app && make check-prefix-guardrail -> clean tree.
- cd app && uv run ruff check . -> pass.
- cd app && uv run black --check . -> pass.
- cd app && uv run pytest tests --ignore=tests/smoke -> 2857 passed, 37 skipped.
- cd app && uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)' -> fails on pre-existing repository-wide typing issues outside this task's change scope.

DoD left for human verification:
- PR description references decisions/transport-slack.md.
<!-- SECTION:NOTES:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR references decisions/transport-slack.md
<!-- DOD:END -->



## Comments

<!-- COMMENTS:BEGIN -->
author: @copilot
created: 2026-07-22 14:58
---
Alignment (2026-07-22): read prefix from infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home), replacing get_app_settings().PREFIX for /incident. Smoke/new tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Transport move stays with TASK-26.
---
<!-- COMMENTS:END -->
