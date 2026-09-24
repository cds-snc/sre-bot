---
id: TASK-26
title: >-
  Split the Slack platform by direction: runtime to app/server/slack/, handler
  contract to app/contracts/, integrations/slack/ shrinks to client factory,
  classifier and settings
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 19:58'
labels:
  - slack
  - phase-3
  - architecture
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-25.4
references:
  - decisions/transport-slack.md
  - decisions/platform-transports.md
  - 'https://github.com/cds-snc/sre-bot/issues/1280'
  - decisions/platform-entrypoints.md
  - decisions/plugin-architecture.md
priority: high
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR (rescoped 2026-09-24). Implemented by its subtasks; closes when they are Done and the acceptance criteria below hold.

Target homes (decisions/platform-entrypoints.md, platform-transports.md, transport-slack.md, plugin-architecture.md):
- app/server/slack/: the Bolt runtime and Socket Mode lifecycle, verification, dispatch, parser, formatter, help, and the transport settings (COMMAND_PREFIX).
- app/contracts/ (the Slack part under app/contracts/slack/): registration hookspecs, typed request and reply models, the registrar Protocol features register through, and the outbound messaging Protocol. It imports no SDK runtime; pure-data slack_sdk model types are allowed.
- app/integrations/slack/: the authenticated AsyncWebClient factory, classify_slack_error (TASK-25.4) and credentials only.

The earlier scope moved the transport to app/infrastructure/slack/ and left re-export shims at the old paths. Both are dropped. infrastructure/ is hosting-only, so no inbound runtime belongs there. Shims are the lingering migration state this backlog avoids: every importer is rewritten in the subtask that moves its target.

Constraint for planning: legacy modules/ import integrations.slack (models, parser, provider, bootstrap, channels, users, blocks) in about 25 places. A legacy module importing app/server/ adds an import-linter ignore entry, which migration.md rule 3 forbids. The subtasks must therefore choose, for each helper:
- pure-data models go to app/contracts/slack/;
- anything a handler reaches at runtime (parser, renderer, reply) is exposed through the handler contract;
- vendor-calling helpers (channels.py, users.py) move to the adapters of their consumers, or stay in their legacy consumer until that surface is rebuilt.
Record that disposition in the plan.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Slack runtime, verification, dispatch, parser, formatter, help and COMMAND_PREFIX live only under app/server/slack/; app/infrastructure/slack/ no longer exists
- [ ] #2 app/integrations/slack/ exports only the client factory, classify_slack_error and settings; the vendor_package_contract baseline has no Slack entry left
- [ ] #3 No shim or re-export remains at any old integrations.slack or infrastructure.slack path, and no import-linter ignore entry was added
- [ ] #4 Existing Slack commands behave identically: the TASK-36 smoke suite is green before and after
- [ ] #5 Parser uses shlex.split; parser test suite still green
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 modules/ untouched and still functional
- [ ] #2 PR references decisions/transport-slack.md and decisions/platform-transports.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @copilot
created: 2026-07-22 14:56
---
Cross-ref TASK-45.1 (Slack transport settings home / COMMAND_PREFIX): that slice, executed before this move, adds NEW transport logic into the still-mislocated app/integrations/slack/provider.py — (1) a command_prefix param on SlackPlatformProvider.__init__, (2) central prefix application in _auto_register_root_commands (slash_command = f'/{self._command_prefix}{root_command}'), and (3) get_slack_provider() reading get_slack_transport_settings() from infrastructure.slack.settings (a deliberate, tolerated upward import until this consolidation lands). When moving the transport runtime to app/infrastructure/slack/ per decisions/transport-slack.md + platform-transports.md, this move MUST carry all three, and relocate their tests (app/tests/unit/integrations/slack/test_slack_provider.py::TestSlackProviderFactory and test_slack_auto_registration.py prefix cases) to app/tests/unit/infrastructure/slack/. The upward integrations->infrastructure.slack import is resolved by that relocation.
---

created: 2026-07-27 14:01
---
Carry-forward from TASK-5.2 (2026-07-27): TASK-5.2 was re-scoped to DELETE the dead app/integrations/slack/utils.py (legacy_slack_listener + generate_slack_idempotency_key) rather than migrate it, because Slack redelivery dedup does not belong in the vendor-client layer. When this task builds the transport dispatch in app/infrastructure/slack/, that dispatch is where per-handler idempotency must live: every mutating Slack handler idempotent via the TASK-5.1 claim/complete/release primitive, key feature:intent:idempotency_id, with idempotency_id being the sender-assigned Slack event_id (decisions/reliability.md - never request_id, never a payload hash). OPEN PRODUCT QUESTION inherited from TASK-5.2, unresolved: how to handle Slack events that carry no trigger_id/action/view and thus no obvious sender-assigned stable id (reject vs defer vs adopt another Slack-provided id). Flag for human/product decision when implementing dispatch dedup; do not silently pick a payload-hash fallback (prohibited). If dedup grows beyond a code-move, split it into its own task rather than overloading this consolidation task's no-behavior-change scope.
---

created: 2026-07-27 14:07
---
Bootstrap relocation sequence (added 2026-07-27): the Slack Bolt bootstrap in app/integrations/slack/bootstrap.py moves to app/infrastructure/slack/ as part of this transport-home consolidation. At the time this task runs (phase-3), BOTH SlackBootstrap (AsyncApp) and the still-live LegacySlackBootstrap (sync App, used by provider.py:180 runtime + ops/dev/sre module callers) exist; per step 3 of this task, leave an import shim at the old integrations/slack path so app/modules/ callers keep working until the strangler (TASK-37..41). TASK-33 (phase-4, depends on this task) then collapses the sync/async duplication down to AsyncApp only and deletes LegacySlackBootstrap once its provider.py runtime and module callers are cut over - see the LegacySlackBootstrap call-site inventory recorded on TASK-33.
---

created: 2026-09-10 16:18
---
ARCHITECTURE CONSTRAINT ADDED 2026-09-10 (human-directed). Chat platforms are split by direction (decisions/platform-entrypoints.md, Draft):
- Entry point: SDK runtime and connection lifecycle, verification, dispatch and in-request replies. Goes to app/server/<platform>/, beside HTTP.
- Handler contract: typed request/response models, argument parser, OperationResult renderer, in-request reply Protocol and registrar Protocol. Goes to app/infrastructure/<platform>/, with no runtime and no I/O.
- Messaging people or channels outside a request: goes to a capability package (decisions/capability-packages.md, Draft) or a Path B adapter.
- Web API client and classify_<platform>_error: app/integrations/<platform>/ (unchanged).

Features never receive SDK runtime objects such as the Bolt App. Do not move a runtime into app/infrastructure/<platform>/ in the meantime, so it moves only once.

This task's AC#1 conflicts with the split. The runtime, verification and dispatch go to app/server/slack/; infrastructure/slack/ keeps only the handler contract. The acceptance criteria are left unchanged; re-scope when the Draft records are accepted (TASK-83.1).
---

created: 2026-09-18 16:51
---
2026-09-18: dependency narrowed from the TASK-25 umbrella to TASK-25.4. This task needs only the Slack Web-client factory and classify_slack_error that 25.4 now owns. TASK-25 grew five unrelated vendor subtasks (25.6-25.10, Opsgenie/Sentinel/Notify/Trello/OpenAI) plus MaxMind (25.5), none of which this move needs.
---

created: 2026-09-24 19:58
---
2026-09-24 rescope: target homes follow decisions/platform-entrypoints.md and plugin-architecture.md (server/slack, contracts), not infrastructure/slack; shims dropped. Decomposed into ordered subtasks; the existing plan predates the split and must be re-planned per subtask.
---
<!-- COMMENTS:END -->
