---
id: TASK-140.2
title: >-
  Add a Slack action and view-submission registrar so packages can handle
  buttons and modals without the Bolt app
status: In Progress
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-06 20:07'
labels:
  - incident
dependencies:
  - TASK-140.1
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 321000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per decisions/transport-slack.md (Block actions and view submissions) and platform-entrypoints.md rules 2-3: extend the registrar Protocol in contracts/slack and SlackPlatformProvider so a package's entrypoints/slack.py registers native Bolt listeners for block actions and view submissions by exact action_id or callback_id, at startup like commands. Listeners receive Bolt's own arguments (ack, body, client, respond) and open modals with Bolt's client; the host never normalizes the payload and never hands out the App. Ids carry the plugin's entry-point name. Options, shortcuts, view_closed, regex ids and middleware are out of scope until a feature needs them. Needed by the status-update approval modal and later by the rebuilt declare modal (TASK-38.3).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A package registers a block-action handler and a view-submission handler through a registrar Protocol in contracts/slack; no package imports slack_bolt App
- [x] #2 Handlers are registered at startup through the plugin hooks, never at import time, and each id is registered once (duplicate ids fail boot)
- [x] #3 Integration tests dispatch a block action and a view submission through a real Bolt app and assert ack, handler call and validation-error response
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [x] #5 import-linter allows slack_bolt in packages only from entrypoints/slack.py modules (transport-slack.md Checks)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Decisions (approved in session 2026-10-06)
- Ids carry the entry-point name by **validation**, not auto-prefixing: the host calls `register_slack_commands` once per plugin (`pm.subset_hook_caller`) with a registrar scoped to `pm.get_name(plugin)`. An action/callback id not starting with `<name>.` aborts boot. Commands pass through unchanged.
- Protocol gains `register_block_action(action_id, listener)` and `register_view_submission(callback_id, listener)` (Bolt's names). `SlackCommandRegistrar` / `register_slack_commands` names kept; the rename is a separate follow-up task.
- Superseded during implementation: the agreed `warn` for an unmatched ignore rule breaks the enforced repo rule that every contract with `ignore_imports` alerts `error` (`tests/unit/tooling/test_tooling_import_contracts_config.py`). Contract (j) is instead a `protected` contract on `slack_bolt` with `allowed_importers` (no ignore list, no warning), which also enforces platform-entrypoints.md's check that `contracts` imports no SDK runtime. TASK-140.6 needs no follow-up switch.
- `decisions/plugins.md` line 51 ("the Bolt app for listeners") is corrected in this PR to match platform-entrypoints.md rule 2 (governance cascade rule).
- Registering a listener after listeners are attached to the Bolt app raises `RuntimeError` (startup-only).

## Verified current state (main @ ce5bb3aa)
- `server/plugins/manager.py:87` calls `pm.hook.register_slack_commands(registrar=slack_provider)` in a single sweep; `server/lifespan.py:273` → `:281` legacy commands → `:283` `initialize_app()` (creates the Bolt App, `_auto_register_root_commands`; catches every exception) → `:287` legacy `bot.action/view` handlers.
- `pm.get_name(plugin)` returns the entry-point name (`incident.scribe`, `access.sync`, …; `app/pyproject.toml [project.entry-points.sre_bot]`).
- No `packages/**/entrypoints/slack.py` exists; no package imports `slack_bolt`. slack_bolt 1.27.0 has `App.block_action` / `App.view_submission`, and a str constraint is an exact match. pluggy 1.6.0, import-linter 2.15 (9 contracts kept).
- Only production implementer of `SlackCommandRegistrar`: `integrations/slack/provider.py::SlackPlatformProvider`. Test fake: `tests/factories/slack.py::FakeSlackRegistrar`.
- `tests/integration/legacy_surface/conftest.py` builds a real Bolt App (pristine `App.__init__`, static authorize, `InlineExecutor`) and sets `provider._app` before calling the hook directly.

## Steps
1. `contracts/slack/registrar.py`: add `register_block_action(self, action_id: str, listener: Callable[..., object]) -> None` and `register_view_submission(self, callback_id: str, listener: Callable[..., object]) -> None`. The docstrings say the listener is a native Bolt listener (Bolt injects `ack`, `body`, `client`, `respond`, … by parameter name), acks first, and returns field errors via `ack(response_action="errors", errors=...)`; the id is exact and starts with the plugin's entry-point name. No Bolt import (contract c). Module docstring updated.
2. `contracts/plugins/hookspecs.py`: `register_slack_commands` docstring now says it registers commands, block actions and view submissions, once per plugin.
3. `integrations/slack/provider.py`: `_block_actions` / `_view_submissions` dicts; `register_block_action` / `register_view_submission` reject an empty id or an id already registered (`ValueError`, raised during the hook call so boot aborts) and raise `RuntimeError` once listeners are attached; `_attach_interaction_listeners()` wires `app.block_action(id)` / `app.view_submission(id)` and sets the attached flag; called from `initialize_app` after `_auto_register_root_commands`. Listeners are passed to Bolt unwrapped.
4. `server/plugins/slack_registrar.py` (new): `PluginSlackRegistrar(registrar, plugin_name)` implements `SlackCommandRegistrar`, delegating `reply` and `register_command` unchanged and rejecting (`ValueError`) action/callback ids without the `<plugin_name>.` prefix before delegating.
5. `server/plugins/manager.py`: replace the single sweep with a loop over `pm.list_name_plugin()`, skipping blocked entries (pluggy lists a `set_blocked` name with plugin `None`; plugins.md enablement), calling `pm.subset_hook_caller("register_slack_commands", remove_plugins=<others>)(registrar=PluginSlackRegistrar(slack_provider, name))`.
6. `app/pyproject.toml`: root `include_external_packages = true` (needed to name an external module; the other 9 contracts stay kept). New contract (j), type `protected`: `protected_modules = ["slack_bolt"]`, `allowed_importers = ["server", "integrations", "modules", "packages.**.entrypoints.slack"]` (today's importers are exactly server, integrations and modules). Direct imports only; chains through integrations stay covered by (e).
7. Tests (written first, failing): see matrix. Move `InlineExecutor`, `FakeSlackClient`, `_unpatched_app_init` and `_authorize_single_workspace` from `tests/integration/legacy_surface/conftest.py` into a new `tests/factories/slack_bolt.py` (conftest imports them; `tests/factories/slack.py` stays SDK-free) so the new integration test reuses them; `FakeSlackRegistrar` records block actions and view submissions.
8. Gates: ruff, mypy (0 new in touched files), lint-imports, pytest tests --ignore=tests/smoke. One-off checks of contract (j) with temporary modules, removed afterwards: a plain package module importing slack_bolt breaks it, `packages/<x>/entrypoints/slack.py` is allowed, and a `contracts/` module importing slack_bolt breaks it.

## Test matrix
- `tests/unit/integrations/slack/test_slack_provider_listener_registration.py` (AC1, AC2): stored listeners are wired into Bolt on initialization; duplicate action id raises; duplicate callback id raises; the same id as an action and as a view is allowed (separate namespaces); empty id raises; registering after listeners are attached raises RuntimeError.
- `tests/unit/server/plugins/test_server_plugins_slack_listener_scoping.py` (AC1, AC2): each plugin's hookimpl receives a registrar scoped to its own entry-point name; a prefixed id reaches the provider; an unprefixed id, or one carrying another plugin's name, raises; commands and `reply` pass through unchanged; two plugins registering the same id through `register_feature_integrations` raise (boot abort); a hookimpl that raises propagates.
- `tests/integration/integrations/slack/test_slack_provider_listener_dispatch.py` (AC3): a plugin registered on a real pluggy manager registers a block action and a view submission; real Bolt App + `InlineExecutor`; dispatching a `block_actions` payload → HTTP 200 ack, listener called with Bolt's `body` and `client` and opens a view through `client.views_open` (FakeSlackClient records it); a `view_submission` with valid input → 200 empty ack and listener called; a `view_submission` with invalid input → 200 body `{"response_action":"errors","errors":{...}}`; an unregistered action id is not routed to the listener.
- `tests/unit/contracts/slack/test_slack_contracts_registrar_protocol.py`: `FakeSlackRegistrar` and `PluginSlackRegistrar` satisfy the Protocol (mypy-checked assignment).
- AC5: `lint-imports` output showing contract (j) kept, plus the checks in step 8.

## AC traceability
AC1 → steps 1,3,4 → provider + scoping tests · AC2 → steps 3,5 → duplicate/late/boot-abort tests · AC3 → step 3 → integration test · AC4 → step 8 · AC5 → step 6 → lint-imports evidence.

## Size gate
Production: 6 files (registrar.py, hookspecs.py, provider.py, manager.py, new slack_registrar.py, pyproject.toml), ~180 LOC, one subsystem (app code) plus import-linter config. No mechanical refactor mixed in (the names are kept). Single PR. Verdict: pass.

## Assumptions and doubts
- `include_external_packages = true` does not break contracts (a)-(i): verify with lint-imports right after step 6.
- `pm.subset_hook_caller` passes kwargs like `pm.hook`: covered by the scoping tests.
- The legacy `bot.action/view` ids in `app/modules` cannot collide with prefixed package ids (they don't start with entry-point names) and are out of the duplicate check: accepted, and they go away as legacy modules retire.
- The legacy harness calls the hook unscoped with the provider: still valid (the provider satisfies the Protocol); it only checks duplicates.

## Blast radius and rollback
No current plugin registers actions/views, so runtime behavior is unchanged except the per-plugin hook loop (same hookimpls, same args). Wrong ship → command registration could fail at boot (loud, caught by the legacy-surface tests). One `git revert` restores the previous behavior; no config, env or terraform ordering. TASK-140.6 depends on this.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per the plan. Deviations: contract (j) is a protected contract on slack_bolt (allowed_importers server, integrations, modules, packages.**.entrypoints.slack) instead of forbidden + ignore_imports with warn, because tests/unit/tooling/test_tooling_import_contracts_config.py requires every contract with ignore_imports to alert error; it also blocks slack_bolt in contracts. decisions/plugins.md line 51 corrected (the Bolt app for listeners) to match platform-entrypoints.md rule 2. Bolt test helpers moved from tests/integration/legacy_surface/conftest.py to tests/factories/slack_bolt.py.
Evidence: ruff check and format clean; lint-imports 10 kept 0 broken, (j) breaks for a temporary slack_bolt import in a package module and in contracts and stays kept for packages/<x>/entrypoints/slack.py; mypy 57 errors in 20 files repo-wide, 0 in touched files; pytest tests --ignore=tests/smoke 3742 passed, 6 failed (known TASK-90 order leaks in test_webhooks_aws_sns.py and directory/test_google.py; 111 passed when those files run alone).
<!-- SECTION:NOTES:END -->
