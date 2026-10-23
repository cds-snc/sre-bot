---
id: TASK-26.1.3
title: >-
  Define the Slack registrar and reply Protocols and move every hookimpl onto
  them
status: Done
assignee: []
created_date: '2026-09-29 20:19'
updated_date: '2026-10-02 14:59'
labels:
  - plugin-architecture
  - slack
milestone: m-7
dependencies:
  - TASK-26.1.2
references:
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
  - decisions/feature-packages.md
parent_task_id: TASK-26.1
priority: high
type: task
ordinal: 292000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack A layer 7c (slice 3 of TASK-26.1). Adds SlackCommandRegistrar (mirroring register_command, exposing a reply property) and SlackReplyPort (post_message, post_ephemeral, open_view, returning OperationResult) in app/contracts/slack/. register_slack_commands is re-signed to take the registrar, the unused register_slack_listeners(app: AsyncApp) hookspec is deleted, and all 8 hookimpls migrate in the same change. SlackPlatformProvider implements both Protocols where it lives today; it moves in TASK-26.2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/contracts/slack/registrar.py and reply.py define SlackCommandRegistrar and SlackReplyPort and import no SDK runtime (slack_bolt, SocketModeHandler)
- [x] #2 register_slack_commands takes registrar: SlackCommandRegistrar; register_slack_listeners is deleted; no hookspec signature names AsyncApp, App or SlackPlatformProvider
- [x] #3 All 8 hookimpls take the registrar; rant, incident_draft and user_rotations reply through registrar.reply; grep finds no hookimpl receiving SlackPlatformProvider or the Bolt app
- [x] #4 The 4 '-> integrations.slack.provider' contract (e) ignore entries are deleted and no ignore entry is added
- [x] #5 The TASK-36 legacy_surface suite changes only its registration fixture call; no assertion changes
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; the TASK-36 legacy_surface suite is green before and after
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack A layer 7c. Applies decisions/platform-entrypoints.md rule 2 (features never receive SDK runtime objects) and transport-slack.md (registrar Protocol; outbound messaging Protocol for replies).

Contracts (new, no SDK runtime import):
- app/contracts/slack/registrar.py: SlackCommandRegistrar(Protocol) with register_command(...) mirroring SlackPlatformProvider.register_command's current signature exactly (command, handler, description, description_key, usage_hint, examples, example_keys, parent, legacy_mode, arguments, schema, argument_mapper, fallback_handler), typed on contracts.slack.models, and a read-only `reply: SlackReplyPort` property.
- app/contracts/slack/reply.py: SlackReplyPort(Protocol): post_message(*, channel_id, text, username=None, icon_url=None), post_ephemeral(*, channel_id, user_id, text), open_view(*, trigger_id, view: dict). Each returns OperationResult (contracts.operations); failures are classified, not raised (transport-slack.md Errors).

Runtime (where it lives today; TASK-26.2 moves it):
- integrations/slack/provider.py: SlackPlatformProvider satisfies SlackCommandRegistrar structurally; its `reply` returns a SlackWebReply built on the provider's own client (self._client, already from the TASK-25.4 factory) that maps SlackApiError through classify_slack_error into OperationResult.error.

Hookspecs and call sites:
- infrastructure/plugins/specs.py: register_slack_commands(self, registrar: SlackCommandRegistrar); delete register_slack_listeners (zero implementers; AC#2 forbids a hookspec naming AsyncApp). Update any hookspec inventory test.
- infrastructure/plugins/manager.py: pm.hook.register_slack_commands(registrar=slack_provider).
- Tests calling the hook or hookimpls: tests/integration/legacy_surface/conftest.py (the single registration line), tests/integration/packages/access/test_access_plugin_discovery_registration.py, tests/integration/server/test_lifespan_sre_single_registration.py.

Hookimpls (all 8 in this change; a hookspec has one signature):
- modules/sre, modules/dev, packages/geolocate, packages/access/sync, packages/incident_summary: parameter renamed to registrar: SlackCommandRegistrar; register_command calls unchanged. geolocate and access/sync drop their TYPE_CHECKING import of the nonexistent infrastructure.platforms.providers.slack.
- packages/rant: chat_postMessage -> registrar.reply.post_message; the fallback-to-bot path triggers on a failed OperationResult instead of an exception.
- packages/incident_draft: chat_postEphemeral progress note -> registrar.reply.post_ephemeral; a failure is still logged and never fails the command.
- packages/user_rotations: views_open -> registrar.reply.open_view.
- Remove `from __future__ import annotations` from touched files.

import-linter: delete the 4 "-> integrations.slack.provider" contract (e) entries (incident_draft, incident_summary, rant, user_rotations platforms); add none.

Tests first:
- app/tests/unit/contracts/slack/test_slack_contracts_registrar_protocol.py: a fake registrar satisfies the Protocol and a hookimpl registers through it; AST scan: no SDK runtime import in contracts/slack.
- app/tests/unit/integrations/slack/test_slack_provider_reply_classifies_errors.py: each reply method issues the expected Web API call; success -> OperationResult success; SlackApiError ratelimited with Retry-After -> TRANSIENT_ERROR with retry_after; unmapped code -> error result without raising.
- Handler tests for rant, incident_draft and user_rotations assert through a fake SlackReplyPort.
- legacy_surface suite: only the registration call changes (provider= -> registrar=); its FakeSlackClient still backs the reply calls through the provider's client; all 17 assertions unchanged.

Verify: rg finds no hookimpl or hookspec naming SlackPlatformProvider, AsyncApp or App; lint-imports 8 kept; gates.

AC map: #1 contracts; #2 specs/manager; #3 hookimpls; #4 import-linter; #5 legacy_surface; #6 gates.
Size: 13 production files, about 200 LOC. Cannot split further: every implementer of the hookspec changes with it.
Rollback: git revert; same Slack calls, different indirection.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From 7a (TASK-26.1.1): packages/access/sync/interactions/slack.py:32 and packages/geolocate/platforms/slack.py:14 still import SlackPlatformProvider under TYPE_CHECKING from the deleted infrastructure.platforms.providers.slack (mypy import-untyped). Re-signing their register_commands onto SlackCommandRegistrar must remove these imports; do not repoint them at integrations.slack.provider (that would need new contract (e) entries).

From TASK-26.1.2 (2026-10-01): rant, incident_draft and incident_summary now take their Slack lookups from providers.py (get_user_identity_lookup, get_incident_channel_port). The only provider.client uses left in those three packages are replies: rant chat_postMessage and incident_draft chat_postEphemeral. handle_summarize_command still carries an optional port parameter (`IncidentChannelPort | None`) kept for its missing-client test; drop it when re-signing the handlers. The legacy_surface harness patches those provider functions at the handler modules (tests/integration/legacy_surface/conftest.py build_harness).

Implemented 2026-10-01 (Stack A layer 7c), left In Progress for human review.

What changed:
- contracts/slack/registrar.py (SlackCommandRegistrar: register_command mirroring the provider's signature, read-only reply property) and contracts/slack/reply.py (SlackReplyPort: post_message, post_ephemeral, open_view, keyword-only, returning OperationResult[None]). No SDK import.
- integrations/slack/reply.py: SlackWebReply, built by SlackPlatformProvider on its own client (read lazily; the client exists only after initialize_app) and exposed as provider.reply. SlackApiError goes through classify_slack_error; a Slack code the catalogues do not name becomes PERMANENT_ERROR carrying the Slack code; any other exception becomes PERMANENT_ERROR/UNEXPECTED_ERROR with the exception in cause; a call before startup returns PERMANENT_ERROR/INITIALIZATION_ERROR. Nothing is raised.
- infrastructure/plugins/specs.py: register_slack_commands(self, registrar: SlackCommandRegistrar); register_slack_listeners deleted; slack_bolt and integrations.slack.provider imports removed. manager.py calls the hook with registrar= and types slack_provider as SlackCommandRegistrar.
- All 8 hookimpls (modules sre, dev; packages geolocate, access/sync, incident_summary, rant, incident_draft, user_rotations) take registrar: SlackCommandRegistrar in both __init__.py and their register_commands. rant posts through reply.post_message and falls back to the bot mention on a failed result; incident_draft posts its progress notice through reply.post_ephemeral and only logs a failure; user_rotations opens its modal through reply.open_view.
- geolocate and access/sync no longer import the nonexistent infrastructure.platforms.providers.slack. handle_summarize_command's port is no longer optional.
- pyproject.toml: the 4 '-> integrations.slack.provider' contract (e) entries deleted, none added (38 -> 34 ignored imports).

Behaviour differences to review:
- user_rotations: a failed views.open used to raise and surface as 'Error executing sre.rotations.view: ...'; it now logs user_rotations_view_open_failed and answers 'Unable to open the user rotation view.'
- rant, incident_draft, incident_summary: the 'client is None' guards are gone (the handlers no longer hold a client). A reply before startup comes back as an error result, so rant still falls back to the mention. Log events renamed incident_draft_no_channel and incident_summary_no_channel.

Tests: new tests/unit/contracts/slack/test_slack_contracts_registrar_protocol.py, tests/unit/integrations/slack/test_slack_provider_reply_classifies_errors.py and Protocol fakes in tests/factories/slack.py; rant, incident_draft and user_rotations handler tests assert through FakeSlackReply. legacy_surface: only the registration call in conftest.py changed (provider= -> registrar=).

Gates (from app/): ruff check: All checks passed. lint-imports: 8 kept, 0 broken. mypy: 65 errors in 22 files repo-wide, 0 in touched files (the two import-untyped errors in geolocate and access/sync are gone). pytest tests --ignore=tests/smoke: 3582 passed, 6 failed; the 6 are the known single-process order failures (3 in test_webhooks_aws_sns.py, 3 in infrastructure/directory/test_google.py, TASK-90) and pass when run on their own (111 passed). legacy_surface: 17 passed before and after.

Size: 22 production files against the plan's 13, because each hookimpl is an __init__.py plus a platforms module; 20 modified files net -8 lines, plus 3 new files (192 lines). One subsystem, not split because every implementer changes with the hookspec.

Follow-ups, not done here: decisions/plugins.md:18, platform-entrypoints.md, platform-transports.md, transport-slack.md and hookspec-deprecation.md still describe register_slack_listeners and the provider-typed hookspec as current; packages/access/request/__init__.py docstring still says register_slack_commands(provider).

CI fix 2026-10-01 (PR #1519): the tests job failed at make check-vendor-package-contract with two net-new violations, module:integrations/slack/reply.py and operation-result:integrations/slack/reply.py (a vendor package holds only __init__.py, client.py and settings.py, and the baseline only ratchets down). Fix: SlackWebReply and its classifier helper moved into integrations/slack/provider.py, which is already baselined under both rules and moves to server/slack/ as a whole in TASK-26.2; integrations/slack/reply.py deleted. No baseline entry and no import-linter entry added; no behaviour or test change (the tests reach the class through provider.reply). This local gate list missed the guardrail scripts; the full CI sequence was run this time, from app/: make fmt-ci (764 files already formatted), check-sdk-typing OK, check-vendor-package-contract OK (16 baselined entries remain), check-aws-platform-seam OK, check-runtime-imports OK, check-import-contracts 8 kept 0 broken, ruff check clean, mypy 65 errors in 22 files repo-wide and 0 in integrations/slack/provider.py, make test 2828 passed and 760 passed.
<!-- SECTION:NOTES:END -->
