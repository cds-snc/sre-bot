---
id: TASK-33
title: Migrate the Slack transport to async Bolt (AsyncApp + AsyncSocketModeHandler)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-27 14:07'
labels:
  - slack
  - phase-4
milestone: m-4
dependencies:
  - TASK-26
references:
  - decisions/transport-slack.md
  - 'https://github.com/cds-snc/sre-bot/issues/1287'
priority: medium
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/transport-slack.md (Concurrency). Today the runtime is sync Bolt (App + SocketModeHandler + threads) while an AsyncApp already exists in bootstrap.py - two concurrency models at once; sync handlers cannot rely on loop-local contextvars for correlation/locale.

Steps:
1. In app/infrastructure/slack/ (post task-26): construct AsyncApp + AsyncSocketModeHandler on the app event loop; start in lifespan phase 5, close at shutdown; delete the thread-based runner and the duplicate sync/async bootstrap.
2. Convert registered listeners to async def; handlers ack() within the deadline then continue in the same listener (Bolt runs each listener on its own task - no ad-hoc create_task, no lazy listeners in this long-running process).
3. Bind request_id and locale contextvars at the inbound boundary so they flow into handlers (aligns with task-28 correlation).
4. Any remaining blocking SDK call inside handlers gets asyncio.to_thread.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Exactly one Bolt runtime exists (AsyncApp); grep shows no SocketModeHandler (sync) or threading-based Slack runner
- [ ] #2 A log line emitted inside a Slack handler carries request_id (contextvar inheritance test)
- [ ] #3 Slack smoke tests: commands ack within deadline and respond correctly
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No behavior change on the command surface; modules/ handlers still work
- [ ] #2 PR references decisions/transport-slack.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-27 14:07
---
Explicit target for the 'duplicate sync/async bootstrap' this task deletes (added 2026-07-27): app/integrations/slack/bootstrap.py::LegacySlackBootstrap (sync Bolt App + sync WebClient) vs SlackBootstrap (AsyncApp + AsyncWebClient). LegacySlackBootstrap is the sync survivor that must disappear once AsyncApp is the sole runtime. Live production call sites: (1) app/integrations/slack/provider.py:180 - self._app = LegacySlackBootstrap().create_app(), the sync SocketModeHandler runtime and the core of this task; (2) app/modules/ops/notifications.py:20 - LegacySlackBootstrap().create_app(); (3) app/modules/dev/platforms/slack.py:31 - LegacySlackBootstrap().web; (4) app/modules/sre/platforms/slack.py:22 - LegacySlackBootstrap().web. Also the export in app/integrations/slack/__init__.py and tests (test_slack_bootstrap.py, test_ops_notifications.py, integration/modules/sre/conftest.py). Sequence: the provider.py runtime is retired HERE (TASK-33). The three app/modules/ callers build a sync web client for OUTBOUND calls; they are owned by the strangler cutovers (ops/dev/sre -> TASK-39/40) and must move to the bot-scoped AsyncWebClient (build_slack_web_client per decisions/transport-slack.md) or the surviving async bootstrap. LegacySlackBootstrap cannot be fully deleted until BOTH the runtime (here) AND all three module callers (strangler) are cut over. Distinct from the identically-prefixed dead legacy_slack_listener decorator deleted by TASK-5.2 - shared 'legacy' name only, unrelated concern.
---
<!-- COMMENTS:END -->
