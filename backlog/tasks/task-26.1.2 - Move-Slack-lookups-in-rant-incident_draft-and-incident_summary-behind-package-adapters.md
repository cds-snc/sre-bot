---
id: TASK-26.1.2
title: >-
  Move Slack lookups in rant, incident_draft and incident_summary behind package
  adapters
status: To Do
assignee: []
created_date: '2026-09-29 20:19'
updated_date: '2026-09-29 20:20'
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
- [ ] #1 rant, incident_draft and incident_summary handlers make no Slack lookup through provider.client; each lookup goes through a Protocol defined in the package's service.py and implemented in its adapters/slack.py
- [ ] #2 Only adapters/ modules import integrations; no contract (e) ignore entry is added and no ports.py or other name outside the decisions/feature-packages.md layout table is created
- [ ] #3 Adapter tests cover each lookup method's call shape; existing handler tests keep their assertions and swap only their client stub for a fake of the new Protocol
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; the TASK-36 legacy_surface suite is green before and after
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
