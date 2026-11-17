---
id: TASK-145.8.5.2
title: 'Slack transport: legacy attachment aliases scoped to button values'
status: Done
assignee: []
created_date: '2026-11-16T19:34:00Z'
updated_date: '2026-11-17T19:05:00Z'
labels:
  - slack
  - transport
dependencies: []
references:
  - decisions/transport-slack.md
parent_task_id: TASK-145.8.5
priority: medium
type: feature
ordinal: 524000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L side PR from main (doc-11 row 18.L7a.2), no consumer (dark). Created 2026-11-16 (human, TASK-145.8.5 OQ3). One posted legacy attachment callback can carry buttons owned by different listeners (archive_channel: archive by incident.response, ignore by TASK-145.9.2, schedule_retro by incident.postmortem, TASK-36.1.2 ruling), and rebuilt listeners attach before the legacy ones, so a plain alias would take every button. register_attachment_action takes aliases scoped to action values; the provider attaches each with a value matcher (Bolt runs the first listener whose matchers pass), so an unclaimed value falls through to a later legacy listener. New messages carry one Block Kit action id per button. TASK-145.13 removes the aliases.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 register_attachment_action accepts legacy callback aliases scoped to action values; the provider attaches each scoped alias with a value matcher so an unclaimed value reaches a listener registered later; a value claimed twice for one callback aborts boot; the provider's alias listing names the values
- [x] #2 decisions/transport-slack.md amended (value-scoped aliases; new messages carry one Block Kit action id per owning listener; TASK-145.13 removes them) with sources and a dated Changes line
- [x] #3 Tests: a claimed value reaches the rebuilt listener, an unclaimed value reaches a legacy listener registered after it, a duplicate claim aborts boot, unscoped aliases behave as before
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-16 against main ac3b8f8d (side PR, branch task-145.8.5.2-value-scoped-aliases). Dark: no registration uses it until TASK-145.8.5.3 (archive), TASK-145.9.2 (ignore) and TASK-145.10 (schedule_retro); merging changes no runtime behaviour.

Evidence. The legacy stale-channel nudge posts one attachment, callback_id archive_channel, with three buttons (values archive, schedule_retro, ignore; modules/incident/notify_stale_incident_channels.py:21-45); the legacy listener is app.action("archive_channel") (incident_helper.py:150), whose str matcher also matches interactive_message (slack_bolt listener_matcher/builtins.py:274-285) and reads body["actions"][0]["value"] (incident_conversation.py:433). The provider attaches rebuilt listeners in initialize_app (server/lifespan.py:274) before _register_legacy_handlers (:280), and Bolt runs the first listener whose matchers all pass and skips the rest (slack_bolt app/app.py:585-606; attachment_action(callback_id, matchers) :1137-1149, slack-bolt 1.30.0). So a plain alias would take every button; a value matcher lets an unclaimed value reach the legacy listener.

Steps (TDD: failing tests first).
1. Contract (app/contracts/slack/registrar.py): register_attachment_action gains keyword legacy_callback_values: Mapping[str, Collection[str]] = {} (legacy callback id -> the button values this listener answers). Docstring states fall-through, exemption from the prefix and the boot errors. legacy_callback_ids unchanged.
2. Server registrar (app/server/plugins/slack_registrar.py): validates within the registration (callback id and every value non-blank, value set non-empty, no value repeated, a callback id not in both legacy_callback_ids and legacy_callback_values), forwards, and logs each (callback id, value) once (slack_legacy_id_registered with value=).
3. Provider (app/integrations/slack/provider.py): scoped aliases kept apart from the exact-id dict: _scoped_attachment_actions: dict[str, dict[str, Callable]] (callback id -> value -> listener). Registration is all-or-nothing: a scoped callback id must not be any exact id (new id, plain alias, block action); a value already claimed for that callback id raises ValueError (boot aborts); several listeners, from any plugin, may share a callback id with disjoint values. _attach_interaction_listeners attaches, per (callback id, listener), app.attachment_action(callback_id, matchers=[_value_in(values)])(listener) after the exact ids; the matcher reads body["actions"][0]["value"] and is False when either is missing. legacy_callback_values() lists (callback id, value) -> new id for TASK-145.13; legacy_ids() unchanged. The attach log names the scoped entries.
4. Fake (tests/factories/slack.py): RecordingSlackRegistrar takes and records legacy_callback_values (fake coverage check).
5. ADR decisions/transport-slack.md "Legacy ids at rebuild": one posted attachment callback can carry buttons owned by different listeners; an alias may be scoped to button values, attached with a value matcher so an unclaimed value reaches a listener attached later (the legacy one); each value claimed once; new messages carry one Block Kit action id per button, owned by its listener; TASK-145.13 removes them. Sources: Slack migrating outmoded compositions to blocks, Bolt listener matchers reference, Fowler strangler fig (transitional architecture). Changes line dated 2026-11-16 (TASK-145.8.5.2, TASK-145.8.5 OQ3). Migration: TASK-33 note (AsyncApp needs an async matcher; the provider owns it).

Tests.
- tests/unit/integrations/slack/test_slack_provider_scoped_alias_dispatch.py (real Bolt App, the existing dispatch harness): a claimed value reaches the rebuilt listener and not the legacy one; an unclaimed value reaches a legacy app.action listener registered after initialize_app; two listeners with disjoint values on one callback each get their own; a payload without a value reaches the legacy listener.
- tests/unit/integrations/slack/test_slack_provider_listener_registration.py (extend): a value claimed twice raises; a scoped callback id that is an exact id (and the reverse) raises; a refused registration stores nothing; the listing names the values; unscoped aliases behave as before (existing tests stay).
- tests/unit/server/plugins/test_server_slack_registrar_legacy_ids.py (extend): scoped ids exempt from the prefix; blank callback id or value, empty value set, a repeated value and a callback id in both kwargs refused; each (callback id, value) logged once.

Size: ~90 production LOC in 3 files, ADR ~6 lines, fake ~4, tests ~170 in 3 files. Under the gate; one subsystem (Slack transport). Blast radius on merge: none (no caller); revert is one commit.

Gates: ruff and the three test files during TDD; then make check-import-contracts, check-package-shape, check-test-seams, check-settings-key-ownership; mypy once, then pytest tests --ignore=tests/smoke once.

Open questions, assessed at program scope 2026-11-16 (ADRs, doc-11, doc-15, prior and upcoming tasks); recommendation each:
OQ1 API shape. ADR: transport-slack.md:39 takes aliases with the listener as keywords (legacy_action_ids, legacy_callback_ids); platform-entrypoints.md:52 keeps the registrar narrow (matcher options arrive only when a feature needs them); type-model-boundaries: no entity, a plain Mapping suffices. Prior: TASK-145.7.2 added both keywords the same way. Upcoming: 145.8.5.3, 145.9.2, 145.10 are the only callers. No gap. Recommendation: new keyword legacy_callback_values: Mapping[str, Collection[str]]; no generic matcher is exposed on the Protocol. Scope key confirmed as the button value, not the name: Slack's legacy button example gives three buttons one name and tells them apart by value (https://docs.slack.dev/legacy/legacy-messaging/legacy-message-buttons/), Block Kit keeps value per element (https://docs.slack.dev/messaging/migrating-outmoded-message-compositions-to-blocks/), and the legacy listener branches on value (incident_conversation.py:433). The legacy alert buttons (handle_incident_action_buttons) branch on name and carry data in value, but one listener owns both (TASK-145.7.10), so they keep a plain alias.
OQ2 Sharing one callback across listeners and plugins. CONFLICT: transport-slack.md:39 says each id is registered once. Prior: TASK-36.1.2 ruling (2026-11-06) split archive_channel across owners; TASK-145.8.5 OQ3 (approved 2026-11-16) chose value-scoped aliases. Upcoming: 145.8.5.3 AC #2 (archive, incident.response), 145.9.2 AC #3 (ignore, incident.response), 145.10 note 2026-11-16 (schedule_retro, incident.postmortem), so sharing across plugins is required. Research: Bolt runs the first listener whose matchers all pass and skips the rest (slack_bolt app.py:585-606; https://docs.slack.dev/tools/bolt-python/reference/listener_matcher/index.html); strangler-fig routing by request attribute (https://martinfowler.com/bliki/StranglerFigApplication.html). Fix (this task's ADR amendment): the registered unit for a scoped alias is (callback id, value); each pair is registered once and a duplicate aborts boot; a scoped callback id is never also an exact id.
OQ3 Listing. ADR: transport-slack.md:39 (the provider lists every alias with its new id for the contract task). Upcoming: TASK-145.13 AC #10 removes the three scoped aliases. No gap. Recommendation: a separate legacy_callback_values() keyed (callback id, value) -> new id; legacy_ids() unchanged.
OQ4 Task file. Memory/feedback: plans and task edits ride with the implementing code PR or the next code PR in the same area. Prior: doc-16 L0, L2a, L4b, L4c task files rode in another layer's commit. The file exists only on the stack (0ef9d413), so adding it to the side PR conflicts (add/add) at the stack's next sync. No gap. Recommendation: the side PR carries code, tests, fake and ADR; this task file's plan, AC and notes edits ride with the L7a.3 commit (same area: L7a.3 is the first consumer).
OQ5 Unclaimed values after the legacy listener is deleted. Upcoming: TASK-145.13 depends on 145.8 (145.8.5.3), 145.9 (145.9.2) and 145.10, so all three values are claimed before the legacy listener goes; the nudge only ever posted these three values. No gap. Recommendation: no catch-all; TASK-145.13 checks legacy_callback_values() is empty after the removal.
OQ6 (new) Async Bolt. GAP: TASK-33 converts listeners to async but does not name matchers; AsyncApp runs AsyncCustomListenerMatcher, which awaits its function (slack_bolt listener_matcher/async_listener_matcher.py:30-43), so the provider's sync value matcher must become async there. Recommendation: one line in transport-slack.md Migration and a TASK-33 description note (the provider owns the matcher, so no feature changes).
OQ7 (new) Legacy branches left unreachable. ADR: migration.md step 4 and "never both" per interaction; feedback: delete dead code in the task that touches it. Once a value is claimed, the matching branch of archive_channel_action is never reached. 145.8.5.3 already deletes close_incident, which the archive branch calls. Recommendation: name it in the consumers' scopes: 145.8.5.3 AC #2 also deletes the archive branch, 145.9.2 the ignore branch, 145.10 the schedule_retro branch, 145.13 the listener. Not this task's scope.
doc-15: no row touches posted Slack buttons or the transport; no conflict.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-16: implemented TDD in the working tree of stack-l/task-145.8.5.1-roles; every touched file is identical on main ac3b8f8d (git diff origin/main HEAD empty for them), so the change carries to the side branch task-145.8.5.2-value-scoped-aliases. 22 new tests failed first, then passed.
- AC #1: register_attachment_action(legacy_callback_values: Mapping[str, Collection[str]] | None) on the contract, PluginSlackRegistrar (validates blank, empty, bare-string and repeated values and a callback id both unscoped and scoped; logs each (callback id, value) once) and SlackPlatformProvider (all-or-nothing; (callback id, value) claimed once across plugins; a scoped callback id is never an exact id, either order; attached after the exact ids with app.attachment_action(callback_id, matchers=[_value_in(values)]); listing legacy_callback_values()). Test fake records the pairs.
- AC #2: decisions/transport-slack.md: Value-scoped aliases paragraph with sources (Slack legacy buttons, migrating to blocks, Bolt listener matchers, Fowler), Migration tolerance for the sync matcher (TASK-33), Changes line 2026-11-16.
- AC #3: test_slack_provider_scoped_alias_dispatch.py (real Bolt: claimed value reaches the rebuilt listener only; unclaimed value reaches the legacy app.action listener attached after initialize_app; disjoint values on one callback; a click without a value falls through); test_slack_provider_listener_registration.py (attach order and matcher; a value claimed twice raises; disjoint claims listed; scoped vs exact conflicts both ways; refused registration stores nothing; blank, empty, string scopes raise; existing unscoped alias tests unchanged and passing); test_server_slack_registrar_legacy_ids.py (prefix exemption and listing, malformed scopes, both-kinds refusal, logging).
- AC #4: ruff check . (All checks passed), ruff format --check (1219 formatted); make check-import-contracts (13 kept, 0 broken), check-settings-key-ownership OK, check-package-shape OK (3 baselined), check-test-seams OK (12 baselined); mypy 40 errors in 13 files (unchanged baseline, none in touched files); pytest tests --ignore=tests/smoke: 7480 passed (run on the stack tree, which includes L6b and L7a.1).
Size: ~110 production LOC added in 3 files (contract docstring included), fake +10, tests ~300 in 3 files, ADR one paragraph + 2 lines. Dark: no caller until TASK-145.8.5.3; revert is one commit. This task file rides with the L7a.3 commit (OQ4).

2026-11-16: side PR #1863 opened; rebased onto main d2f5b2f0 (head 6036ce51): transport-slack.md conflict with TASK-145.8.8's tolerance removal resolved (matcher line kept, both Changes lines); Slack and server tests 641 passed after the rebase.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T20:19:00Z

---

APPROVED 2026-11-16 (human): OQ1-OQ7 as recommended in the plan's program-scope assessment. TASK-176 unchanged. Scope notes applied: TASK-33 (async value matcher), TASK-145.8.5.3, TASK-145.9.2 and TASK-145.10 (each deletes the archive_channel_action branch its claimed value leaves unreachable; TASK-145.13 deletes the listener).

---
<!-- COMMENTS:END -->
