---
id: TASK-26.1.2
title: >-
  Move Slack lookups in rant, incident_draft and incident_summary behind package
  adapters
status: Done
assignee: []
created_date: '2026-09-29 20:19'
updated_date: '2026-10-02 14:58'
labels:
  - plugin-architecture
  - slack
milestone: m-7
dependencies:
  - TASK-26.1.1
references:
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
  - decisions/feature-packages.md
parent_task_id: TASK-26.1
priority: high
type: task
ordinal: 291000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack A layer 7b (slice 2 of TASK-26.1). Behaviour-neutral: every Slack Web API lookup the rant, incident_draft and incident_summary handlers make through provider.client (users_info, conversations_history, conversations_info, bookmarks_list, auth_test) moves behind a package-owned Protocol implemented in the package's adapters/slack.py on integrations.slack.client.get_slack_web_client(), wired through providers.py. Afterwards handlers use provider.client only for in-request replies, which slice 3 moves onto the reply Protocol.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 rant, incident_draft and incident_summary handlers make no Slack lookup through provider.client; each lookup goes through a Protocol defined in the package's service.py and implemented in its adapters/slack.py
- [x] #2 Only adapters/ modules import integrations; no contract (e) ignore entry is added and no ports.py or other name outside the decisions/feature-packages.md layout table is created
- [x] #3 Adapter tests cover each lookup method's call shape; existing handler tests keep their assertions and swap only their client stub for a fake of the new Protocol
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; the TASK-36 legacy_surface suite is green before and after
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack A layer 7b. Behaviour-neutral: same Slack calls with the same arguments, made through a package-owned Protocol instead of provider.client. Replies (rant chat_postMessage, incident_draft chat_postEphemeral, user_rotations views_open) are untouched here; TASK-26.1.3 moves them.

Pattern (precedent: incident_draft's IncidentDocumentPort in service.py, GoogleDocsIncidentDocument in adapters/, wired by providers.py): the lookup Protocol is defined in the package's service.py, implemented in adapters/slack.py on integrations.slack.client.get_slack_web_client() (bot), and exposed by an lru_cached function in providers.py. No ports.py or other name outside the decisions/feature-packages.md layout table. Handler closures in platforms/slack.py obtain the port from providers.py at dispatch time.

Per package:
- rant: Protocol with lookup_user_identity(user_id) covering users_info. New providers.py and adapters/slack.py (+ adapters/__init__.py). _resolve_user_identity keeps its current failure handling (a failed lookup falls back to posting as the bot).
- incident_draft: Protocol covering bookmarks_list, conversations_history, conversations_info, users_info and auth_test as the handler uses them today (find incident document id, channel start, transcript page, display name, self identity). Adapter in adapters/slack.py beside google_docs.py; providers.py gains its provider function.
- incident_summary: Protocol covering conversations_history, conversations_info and users_info. New providers.py and adapters/slack.py.
Each adapter keeps today's error behaviour exactly: where the handler catches SlackApiError today, the adapter or handler still does; where the adapter classifies, it uses classify_slack_error. No new user-visible messages.

Tests first:
- app/tests/unit/packages/rant/test_rant_slack_adapter_lookup.py, app/tests/unit/packages/incident_draft/test_incident_draft_slack_adapter_lookup.py, app/tests/unit/packages/incident_summary/test_incident_summary_slack_adapter_lookup.py: each adapter method issues the expected Web API call on a stub WebClient and returns the shape the handler consumes; SlackApiError behaviour matches today's.
- Existing handler tests (test_rant_slack.py, test_incident_draft_slack.py, test_incident_summary_slack.py) keep their assertions and swap only their client stub for a fake of the Protocol.
- legacy_surface suite: the harness's FakeSlackClient now needs to back the package adapters too; patch each package's providers function to an adapter over the harness client (fixture change only, no assertion change).

Also: remove `from __future__ import annotations` from touched files.
Verify: rg finds no provider.client lookup calls in the three packages; lint-imports with no new entry; gates.

AC map: #1 per-package steps; #2 pattern + lint-imports; #3 tests; #4 gates.
Size: about 12 production files, about 140 LOC.
Rollback: git revert; same Slack calls either way.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-01 on stack-a/task-26.1.2-slack-lookup-adapters (Stack A layer 7b). Left In Progress for human review.

What changed
- rant: service.py gains UserIdentity (frozen dataclass) and the UserIdentityLookup Protocol (lookup_user_identity). New adapters/slack.py (SlackUserIdentityLookup, build_user_identity_lookup) and providers.py (get_user_identity_lookup, lru_cached). The users_info call and profile parsing moved into the adapter; the handler keeps the try/except that falls back to posting as the bot.
- incident_draft: service.py gains IncidentChannelPort (list_bookmarks, fetch_history, get_channel, get_user, get_self_identity). New adapters/slack.py (SlackIncidentChannel) beside google_docs.py; providers.py gains get_incident_channel_port.
- incident_summary: service.py gains IncidentChannelPort (fetch_history, get_channel, get_user). New adapters/slack.py and providers.py.
- The draft and summary adapters are thin: one Web API call per method with the same arguments as before, returning the part of the payload the handler reads. They let Web API errors propagate, so every existing `except Exception` degradation and log event stays in the handler. Nothing classifies, so classify_slack_error is not used.
- Handlers get the port from providers.py inside the dispatch closure. provider.client is now used only for replies: rant chat_postMessage and incident_draft chat_postEphemeral. incident_summary no longer reads provider.client at all.
- Removed `from __future__ import annotations` from every touched file that had it.

Things a reviewer should know
- Lookups now run on integrations.slack.client.get_slack_web_client() (same SLACK_BOT_TOKEN) instead of the Bolt app's client, so they pick up that factory's timeout and rate-limit/server-error retry handlers. This follows from the approved plan; the calls and arguments are unchanged.
- handle_summarize_command keeps an optional third parameter (now `IncidentChannelPort | None`) so the existing missing-client test keeps its assertion. Production never passes None. TASK-26.1.3 re-signs the handlers and can drop it.
- platforms/slack.py in incident_draft now imports providers at module level, so the Google Docs adapter is imported when the package loads rather than on first draft. Import only; no side effects.
- Size: 7 modified and 7 new production files, about 320 added lines (the plan estimated 12 files and 140 LOC; docstrings and Protocol bodies account for the difference).

Tests
- New: test_rant_slack_adapter_lookup.py, test_incident_draft_slack_adapter_lookup.py, test_incident_summary_slack_adapter_lookup.py (call shape per method, returned shape, SlackApiError propagates, builder uses the client factory).
- Existing handler tests keep their assertions; the client stub became a MagicMock(spec=<Protocol>), and assertions that named a Web API method now name the Protocol method (for example conversations_history -> fetch_history). One test was renamed (test_handler_dispatches_with_channel_port_and_parsed_args) and one rant handler test was added for a lookup that raises.
- legacy_surface conftest: build_harness patches each package's provider function to the real adapter over the harness FakeSlackClient. No assertion changed.

Gates (run from app/)
- uv run ruff check . -> All checks passed
- uv run lint-imports -> 8 kept, 0 broken; app/pyproject.toml untouched, no ignore entry added
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> 67 errors in 24 files repo-wide, 0 in files touched by this task
- uv run pytest tests/integration/legacy_surface -> 17 passed before and after
- uv run pytest tests --ignore=tests/smoke -> 3563 passed, 6 failed. The 6 are the known order-dependent failures in tests/modules/webhooks/test_webhooks_aws_sns.py (3) and tests/unit/infrastructure/directory/test_google.py (3); both files pass when run on their own (111 passed).
<!-- SECTION:NOTES:END -->
