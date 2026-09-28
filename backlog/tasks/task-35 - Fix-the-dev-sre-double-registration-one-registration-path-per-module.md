---
id: TASK-35
title: Fix the dev/sre double registration (one registration path per module)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-28 14:55'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies: []
references:
  - decisions/migration.md
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1289'
priority: high
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/migration.md coexistence rule 4: modules register via the legacy hard-coded list OR hookimpls, never both - and it says this is fixed FIRST (live bug risk). The hard-coded _register_legacy_handlers() at app/server/lifespan.py:96-104 lists role, atip, aws, secret, sre, webhook_helper, incident, incident_helper, while the plugin discovery walk also covers modules/ (app/infrastructure/plugins/manager.py:57 and, redundantly, app/server/lifespan.py:188, both base_paths=["packages", "modules"]) - so any module exposing hookimpls AND sitting in the list (sre confirmed; dev checked and confirmed clean, see below) registers twice.

Confirmed during planning (2026-09-28):
- Only `sre` overlaps. `dev` (app/modules/dev/__init__.py) has a register_slack_commands hookimpl and is never referenced from app/server/lifespan.py or anywhere outside app/modules/dev/ - it already has exactly one registration path.
- `sre` overlaps because app/modules/sre/sre.py:register(bot) (called from the hard-coded list as `sre.register(bot)`, re-exported via `from .sre import (sre, webhook_helper)` in app/modules/__init__.py) calls `bot.command(f"/{COMMAND_PREFIX}sre")(sre_command)` directly on the Bolt App - the exact same slash command the hookimpl path also wires up, via app/modules/sre/__init__.py's register_slack_commands hookimpl -> app/modules/sre/platforms/slack.py:register_commands(provider) -> SlackPlatformProvider._auto_register_root_commands() (integrations/slack/provider.py) calling `self._app.command("/sre")(...)`.
- Production effect today: both `bot.command("/sre")` calls append a Listener to slack_bolt's App._listeners (slack_bolt/app/app.py). App.dispatch() iterates listeners in registration order and returns on the first one whose handler produces a response (app.py ~L585-616), i.e. first-match-wins, not duplicate execution. Registration order is: register_feature_integrations() populates provider commands (server/lifespan.py:265) -> slack_provider.initialize_app() calls _auto_register_root_commands(), registering the provider's "/sre" listener first (server/lifespan.py:272) -> _register_legacy_handlers() then registers the legacy "/sre" listener second (server/lifespan.py:276). So the hookimpl/provider path always wins today and app/modules/sre/sre.py's register()/sre_command() are unreachable dead code, not a source of duplicate user-visible replies - but they are a live bug risk per rule 4 (e.g. any reordering of lifespan phases would start double-firing/dead-code-swap silently).
- webhook_helper (app/modules/sre/webhook_helper.py, re-exported as top-level `webhook_helper`) is a distinct module from sre.py: it registers Bolt `view`/`action` interactions (create_webhooks_view, toggle_webhook, etc.), which the hookimpl path does not cover (no register_slack_listeners hookimpl exists yet - decisions/plugins.md lists it as a hookspec with zero implementations). webhook_helper.register(bot) stays on the hard-coded list; it is not part of this bug.
- Resolution: keep the hookimpl path for `sre` (the target mechanism) and delete the dead-code legacy path (app/modules/sre/sre.py) rather than merely unwiring it, since nothing else references it.

Open cross-task note (not resolved by this task): a 2026-09-24 comment on this task proposed the opposite direction (keep sre on the hard-coded list, drop the hookimpl) because TASK-110 will replace the pkgutil-based auto_discover_plugins walk with pyproject entry points, and modules/dev and modules/sre have no entry points today. decisions/plugins.md's Migration section states modules/ keeps its hand-written (pkgutil) registration until each surface is rebuilt, which reads as scoping TASK-110's entry-point cutover to packages/->features/ and capabilities/, not to modules/ - but this is TASK-110's design question, not this task's, and is flagged there rather than resolved here.

Steps:
1. Enumerate which modules under app/modules/ expose hookimpls (grep for hookimpl decorators) and intersect with the _register_legacy_handlers() list. Done: only sre; dev has no overlap.
2. Remove app/modules/sre/sre.py's register(bot)/sre_command() (dead, duplicate registration) and its dedicated test; stop calling `sre.register(bot)` from _register_legacy_handlers() and drop `sre` from the app/modules/__init__.py re-export and from server/lifespan.py's import list. Keep webhook_helper.register(bot) unchanged.
3. Add a regression test proving app/server/lifespan.py never registers "/sre" via both the hookimpl/provider path and the legacy path (asserts the Bolt bot's `.command("/sre")` is invoked exactly once across both registration phases).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No module appears in both _register_legacy_handlers() and the hookimpl discovery (startup assertion or test proves it)
- [ ] #2 A startup assertion or test proves no handler registers twice
- [ ] #3 All dev/sre commands still respond (smoke check recorded in PR)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests green
- [ ] #2 PR references decisions/migration.md rule 4
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decision: keep the hookimpl/provider registration path for `sre` (matches `dev`'s existing single-path shape) and delete the now-fully-dead legacy path, rather than keeping both alive behind one call site. Rationale and the counter-proposal from the 2026-09-24 task comment are recorded in the task description; the TASK-110 entry-point interaction is flagged there for TASK-110's own planning, not solved here.

Files and exact changes:

1. app/modules/sre/sre.py - DELETE the file. It contains only `register(bot)` (calls `bot.command(f"/{COMMAND_PREFIX}sre")(sre_command)`) and `sre_command()`/`_send_response()`, all unreachable today (see description) and fully superseded by app/modules/sre/platforms/slack.py's provider-based routing. No other production code imports it (verified: only app/modules/__init__.py and its own test).

2. app/modules/__init__.py - change `from .sre import (sre, webhook_helper)` to `from .sre import webhook_helper` (drop the `sre` re-export; `webhook_helper` re-export is untouched).

3. app/server/lifespan.py:
   - Remove `sre` from the `from modules import (...)` tuple (keep atip, aws, incident, incident_helper, role, secret, webhook_helper).
   - In `_register_legacy_handlers()` (currently lines 96-105), delete the `sre.register(bot)` line. Resulting call order: role, atip, aws, secret, webhook_helper, incident, incident_helper.

4. app/tests/unit/modules/sre/test_sre_command_registration.py - DELETE. It exists solely to test the deleted `modules/sre/sre.py:register()`.

5. app/tests/integration/server/test_lifespan.py - edit `test_lifespan_register_legacy_handlers_calls_register` (existing test, edited in place, not moved): remove the `patch("server.lifespan.sre")` context manager and the `mock_sre.register.assert_called_once_with(mock_bot)` assertion; keep the other seven module patches/assertions unchanged.

6. New test file app/tests/integration/server/test_lifespan_sre_single_registration.py - one regression test:
   - `test_register_legacy_handlers_and_hookimpl_path_register_sre_command_once`: builds a real `SlackPlatformProvider` (command_prefix=""), sets `provider._app` to the existing `mock_bot` fixture (a MagicMock recording `.command()` calls), calls the real `sre.register_slack_commands(provider=provider)` and `dev.register_slack_commands(provider=provider)` hookimpls directly (no pluggy indirection needed - the goal is to exercise the exact functions the plugin manager calls), then `provider._auto_register_root_commands()`, then the current (fixed) `_register_legacy_handlers(mock_bot, mock_logger)`. Asserts `mock_bot.command.call_args_list` contains a call with `"/sre"` exactly once (`Counter` or list-comprehension count). This test fails against the pre-fix code (would show 2) and documents in its docstring which two registration phases it is asserting don't double-fire, satisfying AC #1/#2 as a concrete regression guard rather than a structural/AST check.
   - Note in the test docstring, per testing-standards, only observable behavior/assertion rationale - no task id.

AC traceability:
- AC #1 (no module in both paths) -> steps 1-3 (sre.py deleted, sre dropped from the hard-coded list and its import) + the new test's assertion.
- AC #2 (test proves no double registration) -> new test in file 6.
- AC #3 (dev/sre commands still respond) -> manual smoke check to record in the PR description: run the app locally (or the existing dev-environment gate) and exercise `/sre version`, `/sre incident`, `/sre webhooks`, and `/sre dev ...` once each; this task predates TASK-36's automated smoke harness so it stays a manual, PR-recorded check as the task's own Steps specify.

Test matrix:
- Happy path: new test proves exactly one `/sre` Bolt registration after the fix.
- Regression/failure: same test would fail (count=2) against the pre-fix code - confirmed by walking the current call order in lifespan.py before editing (documented in the task description).
- No boundary/auth/idempotency cases apply; this is a startup-wiring fix, not a request-path change.

Assumptions and doubts:
- Assumes `webhook_helper.register(bot)` (view/action interactions) is unrelated to the hookimpl path and must stay on the hard-coded list, since no `register_slack_listeners` hookimpl exists yet (verified zero implementers of that hookspec via repo-wide grep). Re-verify with `grep -rn "def register_slack_listeners" app --include=*.py` if this PR's diff grows to touch webhook_helper.
- Assumes deleting app/modules/sre/sre.py is in-scope "fix bugs in touched files" cleanup (dead code) rather than scope creep, since removing only the call site would leave an orphaned, untested, unreachable module. Flagged in the plan for human confirmation at review; revert to "leave sre.py in place, just unwire the call" if the reviewer prefers the smaller diff.
- Assumes `command_prefix` passed to `SlackPlatformProvider` (`transport_settings.COMMAND_PREFIX`, integrations/slack/provider.py:946) and the one `modules/sre/sre.py` reads independently (`get_slack_transport_settings().COMMAND_PREFIX`) are the same settings singleton and therefore always produce an identical slash-command string - confirmed by reading both call sites; both call `infrastructure.slack.settings.get_slack_transport_settings()`.
- Does not touch the duplicate `auto_discover_plugins(...)` call present in both infrastructure/plugins/manager.py:57 (`collect_feature_i18n_resources`, apparently unused by the real startup path) and server/lifespan.py:188 (`_initialize_translation_service`, the one actually called from `lifespan()`) - flagged as a separate, unrelated cleanup candidate, out of this task's scope.

Blast radius and rollback:
- Single subsystem (Slack command registration at startup), 6 files, well under the size gate (no production LOC estimate exceeds ~40 changed/deleted lines plus one file deletion of ~93 lines and one test file deletion).
- A single `git revert` fully restores prior behavior (the dead legacy listener returns, the redundant import/call line comes back) with no data/schema/ordering dependencies - safe to revert at any time.
- Runtime risk: none expected, since the removed registration was unreachable dead code under current listener ordering; the only externally observable surface (the "/sre" Slack command and its subcommands) continues to be served by the hookimpl/provider path exactly as it is today. The PR must still record the manual smoke check (AC #3) because this reasoning rests on today's registration order, which is worth confirming empirically once more before merge.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:10
---
2026-09-24 interaction with TASK-110 (entry-point plugin loading): TASK-110 removes the pkgutil walk over packages/ and modules/ entirely, and legacy modules/ keep hand-written registration until each surface is rebuilt (decisions/migration.md, plugins.md). Choosing the legacy _register_legacy_handlers() list as dev/sre's single path, rather than their hookimpls, keeps them registered after the walk is gone without adding modules.* entry points. Confirm the choice during planning; TASK-110 depends on this task.
---

created: 2026-09-28 14:43
---
2026-09-28 planning: confirmed the direction for the 2026-09-24 comment's open question - this task keeps sre on the hookimpl/provider path (matching dev's existing single-path shape) and deletes the dead-code legacy modules/sre/sre.py rather than moving sre onto the hard-coded list. Rationale is in the task description. The TASK-110 interaction (entry-point loading needs to keep discovering modules/dev and modules/sre once the pkgutil walk is removed, since decisions/plugins.md's Migration section scopes the entry-point cutover to packages/->features/+capabilities/ and says modules/ keeps hand-written registration until each surface is rebuilt) is unresolved and belongs to TASK-110's own planning, not this task.
---

created: 2026-09-28 14:55
---
2026-09-28: implementation plan approved by human (Guillaume Charest) for the doc-2 Stack A / Wave 0 realignment.
---
<!-- COMMENTS:END -->
