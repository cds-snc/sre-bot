---
id: TASK-145.6.3
title: >-
  IncidentConversation with writability; the transcript reader takes a
  ConversationReference; IncidentReportLinkLookup deleted
status: To Do
assignee: []
created_date: '2026-11-05T00:44:00Z'
updated_date: '2026-11-05T00:44:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.6.2
parent_task_id: TASK-145.6
priority: medium
ordinal: 483000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 12c of Stack K (TASK-145.6 plan, approved 2026-11-05). IncidentConversation Protocol on ConversationReference (post, set purpose, add bookmark, invite, archive, is_writable) with SlackIncidentConversation beside the transcript reader over the Slack client factory and classify_slack_error, an in-memory fake, and conversation_is_writable next to find_incident_for_conversation (decisions/incident-management.md: called only before a write to the conversation). No legacy caller is repointed; its consumers are TASK-145.7, 145.8 and 145.10. IncidentTranscriptReader.read_transcript and conversation_started_at take a ConversationReference; scribe and comms resolve the record and pass incident.conversation, and scribe takes the report from incident.report. scribe/adapters/slack.py, IncidentReportLinkLookup and its provider are deleted; the legacy_surface conftest and the core api-surface test follow.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 IncidentConversation is a Protocol in core/api.py; SlackIncidentConversation implements it in core/adapters/slack.py and InMemoryIncidentConversation is its fake, with a parity test
- [ ] #2 is_writable is false for an archived channel and for not_in_channel, true for an open one; conversation_is_writable is exported beside find_incident_for_conversation
- [ ] #3 read_transcript and conversation_started_at take a ConversationReference; a reference of another system returns an unsupported result
- [ ] #4 rg finds no IncidentReportLinkLookup or scribe/adapters/slack.py in app/; scribe's report link comes from the record
- [ ] #5 No user-visible command, reply or log event changes; the legacy_surface, scribe and comms suites pass
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline from the TASK-145.6 plan approved 2026-11-05 (steps 11-13); full plan at pickup against 12b. Tests: test_incident_core_conversation_{operations,writable,errors,fake_parity}.py; transcript reader tests take references; scribe and comms service tests pass a reference.
<!-- SECTION:PLAN:END -->
