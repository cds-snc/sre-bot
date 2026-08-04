---
id: TASK-45.3
title: Cut over /secret and /talent-role command namespacing to COMMAND_PREFIX
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
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1317'
parent_task_id: TASK-45
priority: high
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out). Swap the command-namespace source in app/modules/secret/secret.py and app/modules/role/role.py from AppSettings.PREFIX to COMMAND_PREFIX; keep existing registration and all other behavior identical. Delete the secret and role entries from app/bin/baselines/prefix_readers.txt in the same PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/modules/secret/secret.py and app/modules/role/role.py build their slash-command name from COMMAND_PREFIX, not AppSettings.PREFIX; no other behavior changes
- [x] #2 Pre/post command-name regression tests assert /secret and /talent-role register with the identical command string for COMMAND_PREFIX='' and 'dev-'
- [x] #3 secret and role baseline entries are removed from prefix_readers.txt and the TASK-1.3 guardrail still passes
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR references decisions/transport-slack.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Verified anchors (2026-07-22, code read directly; pattern replicated from TASK-45.2's completed sre/aws cutover, commit 52942363 / PR #1315, same shape for this pair):

- app/modules/secret/secret.py:12 imports `from infrastructure.configuration.app import get_app_settings`; line 15 `PREFIX = get_app_settings().PREFIX` is computed at MODULE IMPORT time (module-level global, not inside register()); line 25 `bot.command(f"/{PREFIX}secret")(secret_command)` is the only PREFIX use in the file (grep confirmed no other PREFIX/app_settings reference in secret.py).
- app/modules/role/role.py:6 imports get_app_settings; line 15 `app_settings = get_app_settings()`; line 19 `PREFIX = app_settings.PREFIX` (also module-level); line 46 `bot.command(f"/{PREFIX}talent-role")(role_command)` is the only PREFIX use (grep confirmed `app_settings` is used ONLY for PREFIX in role.py — google_settings/google_resources are separate get_google_workspace_settings()/get_google_resources_config() calls, untouched).
- TASK-45.1 (Done) already stood up `get_slack_transport_settings()` in app/infrastructure/slack/settings.py returning a cached SlackTransportSettings with `.COMMAND_PREFIX: str` (default "", env SLACK__COMMAND_PREFIX). This is the exact import TASK-45.2 used for sre.py/aws.py and is the only settings source this task needs.
- Established cutover pattern (git show 52942363 -- app/modules/sre/sre.py app/modules/aws/aws.py): replace the `from infrastructure.configuration.app import get_app_settings` import with `from infrastructure.slack.settings import get_slack_transport_settings`; inside register(), replace `app_settings = get_app_settings(); bot.command(f"/{app_settings.PREFIX}sre")(...)` with `transport_settings = get_slack_transport_settings(); bot.command(f"/{transport_settings.COMMAND_PREFIX}sre")(...)`. secret.py/role.py currently read PREFIX at MODULE level (not inside register()) — this task moves the read INSIDE register(), matching the sre/aws shape exactly, which is what makes the module monkeypatch-testable per-call (test sets `monkeypatch.setattr(secret, "get_slack_transport_settings", lambda: SimpleNamespace(COMMAND_PREFIX=...))` then calls `secret.register(bot)`). This is a mechanical relocation, not a behavior change: PREFIX was already fixed at process-start-import time and used only once, at registration; COMMAND_PREFIX is read once at registration time too — the resulting bot.command() string is identical for a given env value.
- app/bin/baselines/prefix_readers.txt currently lists (in order): infrastructure/configuration/app.py, server/lifespan.py, modules/atip/atip.py, modules/incident/incident.py, modules/role/role.py, modules/secret/secret.py. This task removes the `modules/role/role.py` and `modules/secret/secret.py` lines only (mirrors the 52942363 diff that removed `modules/aws/aws.py` and `modules/sre/sre.py`). The guardrail script app/bin/check_prefix_command_namespace.py loads this baseline dynamically at runtime (main(), line ~272) and (a) fails if a baseline entry no longer reads PREFIX ("stale baseline entry") and (b) fails on any net-new PREFIX reader not in baseline — so after the code edit, secret.py/role.py MUST be removed from baseline in the same PR or the guardrail fails on rule (b)... actually the opposite: once PREFIX is no longer read in those files, leaving their baseline entries in place trips the "stale baseline entry: file no longer reads PREFIX" rule. Both edits (code + baseline) are required together. Guardrail is invoked via `make check-prefix-guardrail` (app/Makefile:85-86) — run `cd app && python bin/check_prefix_command_namespace.py` after the edits to verify exit 0.
- No other file reads `modules.secret.secret.PREFIX` / `modules.role.role.PREFIX` as an external attribute (grep across app/ confirmed only stale .mypy_cache entries, no live code or tests). app/tests/integration/server/test_lifespan.py patches the whole `secret`/`role` module objects (`patch("server.lifespan.secret")`, `patch("server.lifespan.role")`) so register() internals are irrelevant there — unaffected by this change.
- No existing test exercises secret.register()/role.register() today (app/tests/modules/secret/test_secret.py and app/tests/modules/role/test_role.py cover only command/view handlers, never register()). New regression tests are net-new files, following the TASK-45.2 precedent exactly: app/tests/unit/modules/aws/test_aws_command_registration.py and app/tests/unit/modules/sre/test_sre_command_registration.py (parametrized "" / "dev-" cases, monkeypatch.setattr on the module's get_slack_transport_settings name, MagicMock bot, assert bot.command.assert_called_once_with(expected)). app/tests/unit/modules/secret/ and app/tests/unit/modules/role/ do not yet exist (only atip/, aws/, sre/ exist under app/tests/unit/modules/) — both need a new __init__.py (empty, matching aws/sre) alongside the new test file.
- .github/instructions/tests-python.instructions.md already carries (from 52942363) the rule: test docstrings must describe only observable behavior/stub strategy/assertion rationale and must NOT reference task/ticket IDs, plan steps, or transitory phases — new test docstrings here must follow the same style as the existing aws/sre docstrings (no "TASK-45.3" mentions).

Step 1 — secret.py cutover (AC #1). Edit app/modules/secret/secret.py:
  (a) line 12: replace `from infrastructure.configuration.app import get_app_settings` with `from infrastructure.slack.settings import get_slack_transport_settings`.
  (b) delete line 15 (`PREFIX = get_app_settings().PREFIX`) — no module-level PREFIX constant remains.
  (c) in register() (currently line ~24-27), replace `bot.command(f"/{PREFIX}secret")(secret_command)` with:
      `transport_settings = get_slack_transport_settings()`
      `bot.command(f"/{transport_settings.COMMAND_PREFIX}secret")(secret_command)`
  No other line in secret.py changes (action/view registrations, handlers, i18n setup untouched).

Step 2 — role.py cutover (AC #1). Edit app/modules/role/role.py:
  (a) line 6: replace `from infrastructure.configuration.app import get_app_settings` with `from infrastructure.slack.settings import get_slack_transport_settings`.
  (b) delete line 15 (`app_settings = get_app_settings()`) and line 19 (`PREFIX = app_settings.PREFIX`). Leave `google_settings = get_google_workspace_settings()` and `google_resources = get_google_resources_config()` (lines 16-17) and their downstream constants (BOT_EMAIL, template ids, ROLE_SCOPES) untouched — they do not depend on app_settings.
  (c) in register() (currently line ~45-48), replace `bot.command(f"/{PREFIX}talent-role")(role_command)` with:
      `transport_settings = get_slack_transport_settings()`
      `bot.command(f"/{transport_settings.COMMAND_PREFIX}talent-role")(role_command)`
  No other line in role.py changes (modal view, locale handling, drive integration untouched).

Step 3 — Regression tests (AC #2). Create, mirroring app/tests/unit/modules/aws/test_aws_command_registration.py and app/tests/unit/modules/sre/test_sre_command_registration.py exactly (same fixture-less style, same parametrize shape, no task-ID references in docstrings per tests-python.instructions.md):
  - app/tests/unit/modules/secret/__init__.py (new, empty).
  - app/tests/unit/modules/secret/test_secret_command_registration.py (new): parametrize [("", "/secret"), ("dev-", "/dev-secret")]; `monkeypatch.setattr(secret, "get_slack_transport_settings", lambda: SimpleNamespace(COMMAND_PREFIX=command_prefix))`; `bot = MagicMock(); secret.register(bot); bot.command.assert_called_once_with(expected_command)`. Note secret.register() also calls bot.action("secret_change_locale") and bot.view("secret_view") — inert on a MagicMock, does not interfere with the bot.command assertion (same caveat documented in the aws test's docstring for its two bot.view() calls).
  - app/tests/unit/modules/role/__init__.py (new, empty).
  - app/tests/unit/modules/role/test_role_command_registration.py (new): parametrize [("", "/talent-role"), ("dev-", "/dev-talent-role")]; same monkeypatch/MagicMock/assert shape against `role.register(bot)`. Note role.register() also calls bot.view("role_view") and bot.action("role_change_locale") — inert, same caveat.

Step 4 — Baseline shrink + guardrail (AC #3). Edit app/bin/baselines/prefix_readers.txt: delete the `modules/role/role.py` and `modules/secret/secret.py` lines (keep the header comments, `infrastructure/configuration/app.py`, `server/lifespan.py`, `modules/atip/atip.py`, `modules/incident/incident.py` untouched). Verify with `cd app && python bin/check_prefix_command_namespace.py` — expect exit 0 / "✓ PREFIX guardrail: clean tree" (confirms no stale baseline entries and no net-new readers introduced).

Test matrix:
  AC#1 -> Steps 1-2: covered indirectly by Step 3's registration tests (they assert the command string is built from COMMAND_PREFIX, not PREFIX) plus existing app/tests/modules/secret/test_secret.py and app/tests/modules/role/test_role.py (untouched handler/view tests) staying green — proves "no other behavior changes".
  AC#2 -> Step 3: app/tests/unit/modules/secret/test_secret_command_registration.py and app/tests/unit/modules/role/test_role_command_registration.py, each parametrized over COMMAND_PREFIX="" and "dev-".
  AC#3 -> Step 4: `python bin/check_prefix_command_namespace.py` exit 0, plus a manual grep confirming `modules/role/role.py` and `modules/secret/secret.py` are absent from prefix_readers.txt.

Assumptions / doubts (verification already done, recorded for reviewer):
  - Moving PREFIX/COMMAND_PREFIX from a module-level read to a register()-local read is treated as within "no other behavior changes" (AC #1) because the value was already frozen at process-import time and used exactly once, at registration — confirmed by re-reading TASK-45.2's completed diff, which made the identical relocation for sre.py/aws.py without objection at review.
  - No caller reads `secret.PREFIX`/`role.PREFIX` as a module attribute from outside these two files — confirmed via workspace-wide grep (only stale .mypy_cache artifacts, not live code/tests).
  - test_lifespan.py's whole-module patching of secret/role is unaffected — confirmed by reading app/tests/integration/server/test_lifespan.py:110-130.

Blast radius: app/modules/secret/secret.py, app/modules/role/role.py, app/bin/baselines/prefix_readers.txt, plus two new test files/packages. No import-linter/baseline files beyond prefix_readers.txt are touched; no terraform/CI/Makefile changes needed (COMMAND_PREFIX env plumbing already landed in TASK-45.1). External contract (the /secret and /talent-role slash commands themselves, and all their handler/view/action behavior) is unchanged for a fixed COMMAND_PREFIX value — verified by the parametrized "" case matching current production behavior exactly.

Rollback: revert the single PR (2 module edits + 1 baseline edit + 2 new test files/dirs) — no migrations, no data, no other subsystem touched; AppSettings.PREFIX itself is untouched (still exists, still read by the remaining baseline files) so no cross-module coupling to unwind.

Size verdict: fits one PR. 3 production files touched (~10-12 LOC changed total), 2 new small test files (~35-40 LOC each) + 2 empty __init__.py — well under the ~400 LOC / ~10 files / single-subsystem gate; directly mirrors TASK-45.2's already-merged PR of the same shape (2 modules + baseline + 2 tests). No decomposition needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented: replaced get_app_settings().PREFIX with get_slack_transport_settings().COMMAND_PREFIX in both modules. Relocated PREFIX read from module-level to inside register() in both files (same mechanical relocation as the sre/aws cutover in PR #1315). Removed modules/role/role.py and modules/secret/secret.py from prefix_readers.txt. All 4 new registration tests pass; 26 existing role/secret handler tests stay green; PREFIX guardrail exits 0. Pre-existing mypy error at role.py:351 (Value of type 'Any | None' is not indexable) confirmed unchanged — present in original file before this PR. DoD item #1 (PR references decisions/transport-slack.md) left for human verification at PR creation.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @copilot
created: 2026-07-22 14:58
---
Alignment (2026-07-22): read prefix from infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home), replacing get_app_settings().PREFIX for /secret + /talent-role. Smoke/new tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Transport move stays with TASK-26.
---
<!-- COMMENTS:END -->
