---
id: TASK-45.2
title: >-
  Cut over /sre and /aws command namespacing from AppSettings.PREFIX to
  COMMAND_PREFIX
status: To Do
assignee: []
created_date: '2026-07-21 19:13'
updated_date: '2026-07-22 16:50'
labels:
  - phase-0
  - slack
milestone: m-0
dependencies:
  - TASK-45.1
references:
  - decisions/transport-slack.md
  - decisions/migration.md
parent_task_id: TASK-45
priority: high
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-module cutover (freeze carve-out). Swap the command-namespace source in app/modules/sre/sre.py and app/modules/aws/aws.py from get_app_settings().PREFIX to the transport COMMAND_PREFIX; keep each module's existing bot.command() registration and all other behavior identical. Delete the sre and aws entries from TASK-1.3's app/bin/baselines/prefix_readers.txt in this same PR. Single, small, reviewable PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/modules/sre/sre.py and app/modules/aws/aws.py build their slash-command name from COMMAND_PREFIX, not AppSettings.PREFIX; no other behavior changes
- [ ] #2 Pre/post command-name regression tests (mocked Bolt app) assert /sre and /aws register with the identical command string for both COMMAND_PREFIX='' and COMMAND_PREFIX='dev-'
- [ ] #3 sre and aws baseline entries are removed from app/bin/baselines/prefix_readers.txt and the TASK-1.3 guardrail still passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Verified anchors (2026-07-22):

- TASK-45.1 (dependency) is Done: app/infrastructure/slack/settings.py defines
  SlackTransportSettings(COMMAND_PREFIX: str = Field(default="", alias="SLACK__COMMAND_PREFIX"))
  and get_slack_transport_settings() (lru_cache singleton). This is the read
  target for this slice.
- app/modules/sre/sre.py:13 imports get_app_settings from
  infrastructure.configuration.app; sre.py:20-23 register(bot) does
  `app_settings = get_app_settings(); bot.command(f"/{app_settings.PREFIX}sre")(sre_command)`.
  get_app_settings is used nowhere else in this file (grep-confirmed).
- app/modules/aws/aws.py:26 imports get_app_settings the same way; aws.py:55-65
  register(bot) does `app_settings = get_app_settings(); bot.command(f"/{app_settings.PREFIX}aws")(aws_command)`
  followed by two unrelated `bot.view(...)` registrations (aws_access_view,
  aws_health_view) that must be left untouched. get_app_settings is used
  nowhere else in this file.
- Both register() functions are called directly and only from
  app/server/lifespan.py:92 (`aws.register(bot)`) and :94 (`sre.register(bot)`)
  — the frozen hard-coded legacy registration list. No other call site touches
  either register() function; no lifespan change is needed.
- app/bin/baselines/prefix_readers.txt currently lists (among others)
  `modules/aws/aws.py` and `modules/sre/sre.py`. app/bin/check_prefix_command_namespace.py
  enforces two relevant rules: (b) any file reading `PREFIX` that is NOT in the
  baseline is a net-new violation; (d) any baseline entry whose file no longer
  reads `PREFIX` is a stale-baseline violation. So removing the PREFIX read AND
  removing the baseline entry must happen together in the same PR, or the
  guardrail fails either way (net-new if entry removed first, stale if code
  changed first) — confirms AC#1 and AC#3 are one atomic change, not two.
  `make check-prefix-guardrail` (app/Makefile:85) runs this script.
- No existing test covers either module's register()/PREFIX behavior: grep of
  app/tests for `def register(bot`, `bot.command`, `from modules.sre.sre`,
  `from modules.aws.aws` found no hits. app/tests/unit/modules/sre/ has only
  conftest.py + test_webhook_helper.py; app/tests/unit/modules/aws/ has handler
  tests (test_aws_command_handler.py etc.) but none for aws.register(). Both
  new test files are net-new, not extensions.
- Pattern precedent for the assertion style: app/tests/unit/integrations/slack/test_slack_auto_registration.py
  ("test_should_apply_command_prefix_to_auto_registered_root_commands") asserts
  the composed slash-command string via a captured/mocked `.command(name)` call
  — same shape this task's tests use, but scoped to each legacy module's own
  register(), not the platform provider.
- Test-hygiene constraint (task comment #1, 2026-07-22): new tests must NOT
  import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings
  (dead duplicate, TASK-24). Use a SimpleNamespace(COMMAND_PREFIX=...) stub via
  monkeypatch instead — no real settings class needed since only one attribute
  is read.

Step 1 (AC#1) — app/modules/sre/sre.py:
  - Replace line 13 `from infrastructure.configuration.app import get_app_settings`
    with `from infrastructure.slack.settings import get_slack_transport_settings`.
  - Replace lines 22-23:
      `app_settings = get_app_settings()`
      `bot.command(f"/{app_settings.PREFIX}sre")(sre_command)`
    with:
      `transport_settings = get_slack_transport_settings()`
      `bot.command(f"/{transport_settings.COMMAND_PREFIX}sre")(sre_command)`
  - No other line in this file changes.

Step 2 (AC#1) — app/modules/aws/aws.py:
  - Replace line 26 `from infrastructure.configuration.app import get_app_settings`
    with `from infrastructure.slack.settings import get_slack_transport_settings`.
  - Replace lines 62-63:
      `app_settings = get_app_settings()`
      `bot.command(f"/{app_settings.PREFIX}aws")(aws_command)`
    with:
      `transport_settings = get_slack_transport_settings()`
      `bot.command(f"/{transport_settings.COMMAND_PREFIX}aws")(aws_command)`
  - Lines 64-65 (`bot.view(...)` registrations) are untouched.

Step 3 (AC#3) — app/bin/baselines/prefix_readers.txt:
  - Remove the `modules/aws/aws.py` and `modules/sre/sre.py` lines (done in the
    same commit as Steps 1-2, per the atomic-change note above).
  - Verify: `cd app && make check-prefix-guardrail` exits 0 (no net-new reader,
    no stale entry).

Step 4 (AC#2) — new regression tests:
  - New file app/tests/unit/modules/sre/test_sre_command_registration.py:
    parametrized test over COMMAND_PREFIX in {"", "dev-"}; monkeypatch
    `modules.sre.sre.get_slack_transport_settings` to return
    `SimpleNamespace(COMMAND_PREFIX=<value>)`; call `sre.register(MagicMock())`;
    assert `bot.command.assert_called_once_with("/sre")` (prefix="") and
    `"/dev-sre"` (prefix="dev-").
  - New file app/tests/unit/modules/aws/test_aws_command_registration.py: same
    shape against `modules.aws.aws`, asserting `/aws` and `/dev-aws`; bot is a
    MagicMock so the two subsequent `bot.view(...)` calls in aws.register are
    inert and don't interfere with the `bot.command` assertion.
  - Both tests import only `modules.sre.sre` / `modules.aws.aws` and
    `types.SimpleNamespace` — no import of the dead
    infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings.

Test matrix:
  AC#1 -> Steps 1-2: covered indirectly by Step 4's tests (they only pass if
    the source is COMMAND_PREFIX, not AppSettings.PREFIX).
  AC#2 -> Step 4: test_sre_command_registration.py and
    test_aws_command_registration.py, each parametrized COMMAND_PREFIX="" / "dev-".
  AC#3 -> Step 3: `cd app && make check-prefix-guardrail` (wraps
    bin/check_prefix_command_namespace.py) must exit 0 post-edit.
  Full-suite regression: `cd app && uv run pytest tests/unit/modules/sre
    tests/unit/modules/aws -q` plus the existing
    tests/unit/modules/aws/test_aws_command_handler.py suite to confirm no
    behavior change in aws_command/sre_command bodies (untouched).

Assumptions/doubts:
  (a) Assumes get_app_settings()/AppSettings.PREFIX is not read anywhere else
      in sre.py/aws.py beyond the register() line — verified by grep (2 hits
      per file: the import and the one usage). If wrong, the file would keep
      importing get_app_settings unnecessarily; re-grep after editing to
      confirm no leftover unused import (ruff F401 would also catch this).
  (b) Assumes app/server/lifespan.py's two call sites (`aws.register(bot)`,
      `sre.register(bot)`) are the only callers — verified above; no lifespan
      edit is in scope.
  (c) Assumes the guardrail script's stale-baseline rule (rule d) means Step 3
      must land in the same PR as Steps 1-2, not before or after — verified by
      reading check_prefix_command_namespace.py's find_violations() directly.

Blast radius: two production files edited (~4 line-swap each), one baseline
config file edited (2 lines removed), two new unit test files. No frozen-module
behavior change beyond the prefix source (bot.command() call, decorator target,
all other logic byte-identical). No lifespan.py, provider.py, or settings edits
in this slice (those landed in TASK-45.1). Single subsystem (legacy Slack
command-namespace source), no mixed refactor, well under the ~400 LOC/~10 file
gate. Rollback: revert the PR; behavior reverts to reading AppSettings.PREFIX
(both PREFIX and SLACK__COMMAND_PREFIX are kept at the same value per
environment during coexistence per decisions/transport-slack.md, so a revert
produces byte-identical command names).
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR references decisions/transport-slack.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @copilot
created: 2026-07-22 14:58
---
Alignment (2026-07-22): read prefix from infrastructure.slack.settings.get_slack_transport_settings().COMMAND_PREFIX (TASK-45.1 home), replacing get_app_settings().PREFIX in app/modules/sre/sre.py + app/modules/aws/aws.py. Pre/post command-name smoke tests must NOT import infrastructure.configuration.infrastructure.platforms.SlackPlatformSettings (dead duplicate, deletion tracked by TASK-24); use integrations.slack.settings.SlackSettings or a lightweight attribute stub (SimpleNamespace / MockSlackSettings pattern). Do not move the transport provider here — that's TASK-26.
---
<!-- COMMENTS:END -->
