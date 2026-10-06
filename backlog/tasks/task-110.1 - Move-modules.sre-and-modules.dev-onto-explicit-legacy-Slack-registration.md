---
id: TASK-110.1
title: Move modules.sre and modules.dev onto explicit legacy Slack registration
status: Done
assignee: []
created_date: '2026-10-06 14:15'
updated_date: '2026-10-06 17:09'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies: []
references:
  - decisions/plugins.md
  - decisions/migration.md
parent_task_id: TASK-110
priority: high
type: task
ordinal: 316000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Behaviour-preserving prerequisite of TASK-110. modules/sre and modules/dev are the only modules/ packages that ship pluggy hookimpls (register_slack_commands), reached only by the pkgutil walk that TASK-110.2 removes. Move them onto the hand-written legacy registration decisions/plugins.md and decisions/migration.md reserve for modules/: a plain register_commands(registrar) per package, called from an explicit step in server/lifespan.py before the Slack provider's initialize_app. The walk stays in place in this task. The legacy_surface suite pins the commands before and after.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 modules.sre and modules.dev define no pluggy hookimpls; their /sre subcommands are registered by an explicit legacy step in server/lifespan.py that runs before the Slack provider's initialize_app
- [x] #2 The registered command tree (every full_path and its is_auto_generated flag) is identical to the tree before the change
- [x] #3 /sre version, /sre webhooks, /sre incident (legacy mode), the /sre dev group and one dev leaf are proven by Bolt dispatch tests in the legacy_surface suite; the harness registers sre/dev through the production helper, not pluggy
- [x] #4 test_lifespan_sre_single_registration still proves /sre is wired to Bolt exactly once
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Behaviour-preserving. Walk (`auto_discover_plugins`) stays in place and keeps importing modules.sre/dev (now hookimpl-free, so it registers nothing from them).

## Findings
- modules/sre/__init__.py:8 and modules/dev/__init__.py:12 are the only hookimpls in modules/; each just calls `platforms.slack.register_commands(registrar)` (sre/platforms/slack.py:180, dev/platforms/slack.py:~291). Reached only via the walk's pm.register.
- Real legacy path: server/lifespan.py `_register_legacy_handlers(bot, logger)` (:96) registers Bolt handlers on the App AFTER `slack_provider.initialize_app()`. Provider commands are different: `SlackPlatformProvider.initialize_app` (integrations/slack/provider.py:221) calls `_auto_register_root_commands` (:268/:472), binding /sre from the provider's command registry, so sre/dev subcommands must be in the registry BEFORE `initialize_app()`. Today they are, via `register_feature_integrations` (lifespan.py:~262). So the new hand-written step goes right after `register_feature_integrations(...)` and before `app.state.slack_provider.initialize_app()`.
- Ordering delta: today modules.* are registered last by the walk and so called first (pluggy LIFO); the new call runs after all packages. The registry auto-creates parent nodes (provider.py:368) and no package registers under `sre.dev` or the `dev` node, so the final command tree is identical; pinned by a tree snapshot test.
- Existing pins: legacy_surface covers `/sre webhooks` and the `/sre dev` group ack/help only; nothing dispatches `/sre version` or a dev leaf. test_lifespan_sre_single_registration.py:11-12,40-41 imports the two hookimpls; legacy_surface/conftest.py:26-27,45-46,191-193 registers sre/dev through pluggy (would silently lose both commands once hookimpls go).

## Decisions
1. In modules/sre/__init__.py and modules/dev/__init__.py drop the `@hookimpl` decorator and the `contracts.plugins.namespace` import, and rename `register_slack_commands` to `register_commands(registrar: SlackCommandRegistrar) -> None` (a plain package entry function, like the `register(bot)` functions of the other legacy modules; the hookspec name is no longer reused).
2. server/lifespan.py: add `dev, sre` to the existing top-level `from modules import (...)` block (same pattern as `_register_legacy_handlers`; no lazy imports, decisions/migration.md "hard-coded legacy list") and add `_register_legacy_slack_commands(registrar: SlackCommandRegistrar, logger)` next to `_register_legacy_handlers`, calling `sre.register_commands(registrar)` then `dev.register_commands(registrar)` and logging `legacy_slack_commands_registered`. Called between `register_feature_integrations` and `initialize_app()`. Single helper is what tests exercise, so tests cannot drift from production.
3. Test harness (legacy_surface/conftest.py) drops sre/dev from `SLACK_COMMAND_HOOKIMPLS` and calls the lifespan helper after the hook call, before `_auto_register_root_commands`.
4. Update INVENTORY.md rows 110-111 (registration: "hard-coded legacy registration (`_register_legacy_slack_commands`)", defined-at paths), the heading/intro lines 5 and 102-104 and the surface test module docstring (line 1) so they no longer say sre/dev are hookimpls.
5. No decisions/*.md change needed (plugins.md already reserves hand-written registration for modules/); 110.2 edits the docs.

## Files (production) rough LOC
- modules/sre/__init__.py -8, modules/dev/__init__.py -8
- server/lifespan.py +25 (helper, 2 imports, one call site)
Total about 40 changed production LOC, 3 files, 1 subsystem. Tests/docs: conftest ~10, two new test files ~80, existing lifespan test ~15, INVENTORY ~6.

## TDD test matrix (write first, red)
| File | Cases |
|---|---|
| tests/integration/legacy_surface/test_slack_command_registration_surface.py (edit in place) | add `test_sre_version_replies_with_the_git_sha` (dispatch `/sre version`, assert ephemeral reply contains GIT_SHA); `test_sre_incident_forwards_to_incident_helper` (patch `modules.sre.platforms.slack.incident_helper.handle_incident_command`, assert called); `test_dev_leaf_outside_dev_environment_is_refused` (dispatch `/sre dev google` under non-dev env, assert the refusal text from `_require_dev_environment`); existing webhooks and dev-group tests stay. Red until conftest is switched is not possible, so these are written green against current code first to prove the pins, then conftest switch must keep them green |
| tests/integration/legacy_surface/conftest.py (edit) | sre/dev removed from SLACK_COMMAND_HOOKIMPLS; helper call added. Red step: with only the removal and no helper call, the pins above fail (proves the harness cannot silently lose commands) |
| tests/unit/modules/sre/test_sre_legacy_slack_registration.py (new) | modules.sre and modules.dev registered into a fresh pluggy PluginManager contribute zero `register_slack_commands` impls (red before change); `_register_legacy_slack_commands` against a recording registrar registers version/incident/webhooks (+groups) and dev + 6 leaves with the same (command, parent) pairs as a captured baseline literal |
| tests/integration/server/test_lifespan_legacy_slack_command_order.py (new) | drive the lifespan section with a recording provider double: `_register_legacy_slack_commands` is called after `register_feature_integrations` and before `initialize_app`; full command tree snapshot (full_path -> is_auto_generated) equals the baseline literal |
| tests/integration/server/test_lifespan_sre_single_registration.py (edit) | replace the two hookimpl imports with the lifespan helper `_register_legacy_slack_commands`; keep `/sre` count == 1 |

## Steps
1. Capture the baseline tree and write/extend the pins (green on current code); commit nothing, record baseline literal in the test.
2. Write the red tests (no-hookimpl test, order test).
3. Remove hookimpls; add helper and call site; switch conftest and the lifespan single-registration test.
4. INVENTORY/docstring updates.
5. Gates.

## Verification
cd app && uv run ruff check . && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' && uv run lint-imports && uv run pytest tests/integration/legacy_surface tests/integration/server tests/unit/modules/sre -q && uv run pytest tests --ignore=tests/smoke

## Risks and rollback
- Import-time: lifespan now imports modules.sre/modules.dev at module import (as it already does atip, aws, incident...). Their platforms/slack.py build `LegacySlackBootstrap().web` at import: settings read plus the get_slack_web_client() singleton, no network. Pre-existing legacy shortcut in files this task does not touch; removed when the surfaces are rebuilt (TASK-40). Verify `tests/unit/server` still imports lifespan cleanly.
- A missed call site silently drops /sre subcommands: covered by dispatch pins and the order test.
- Rollback: single revert; no config, deploy or ordering constraints.
- Assumption to verify: no other consumer imports `modules.sre.register_slack_commands` (grep found only the lifespan test and the legacy_surface conftest).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06 implementation:
- modules/sre/__init__.py and modules/dev/__init__.py: @hookimpl and the namespace import removed; register_slack_commands renamed to a plain register_commands(registrar). server/lifespan.py imports sre and dev in its existing top-level modules block (same pattern as the legacy Bolt list; no lazy import) and adds _register_legacy_slack_commands(registrar, logger), called after register_feature_integrations and before initialize_app.
- Command tree checked before the change under three orders (legacy_surface harness, modules-first, and the real pkgutil walk): all identical, 22 nodes; sre.incident stays the legacy handler (legacy_mode) because the provider stores by full_path, last write wins, and children are found by scanning. Pinned by test_registered_command_tree_is_unchanged.
- New pins: test_sre_incident_subcommand_forwards_to_incident_helper and test_dev_leaf_outside_the_development_environment_is_refused (legacy_surface); /sre version stays pinned by test_command_prefix_is_applied_to_root_slash_commands. The harness now registers sre/dev through the production helper.
- New tests: tests/unit/modules/sre/test_sre_slack_commands_registration.py (no hookimpls), tests/integration/server/test_lifespan_legacy_slack_commands_registration.py (helper order; lifespan order around initialize_app). test_lifespan_sre_single_registration uses the helper.
- Docs: legacy_surface/INVENTORY.md (intro, section heading, rows for /sre and /sre dev) and decisions/migration.md (current-state line plus change-log entry).
- Gates: ruff clean; ruff format clean on touched files; lint-imports 9 kept; mypy 57 errors repo-wide, 0 in touched files; pytest tests --ignore=tests/smoke 6 failed / 3698 passed, the 6 being the known TASK-90 order leaks (test_webhooks_aws_sns.py x3, directory/test_google.py x3), which pass in isolation (111 passed).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-06 14:15
---
Plan approved by the human on 2026-10-06 (TASK-110 planning session): the TASK-110.1 / TASK-110.2 split; sre/dev go to the end state (no hookimpls, explicit legacy registration, AC#2 of 110.2 kept literally); top-level imports in lifespan.py matching the existing legacy list, no lazy import; the start-log fix in 110.2; the zero-plugins check in load_plugins; a one-off image build check, no CI workflow change.
---
<!-- COMMENTS:END -->
