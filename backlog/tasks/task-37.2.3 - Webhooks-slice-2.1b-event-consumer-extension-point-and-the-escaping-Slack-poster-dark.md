---
id: TASK-37.2.3
title: >-
  Webhooks slice 2.1b: event-consumer extension point and the escaping Slack
  poster (dark)
status: To Do
assignee: []
created_date: '2026-11-26T13:18:00Z'
updated_date: '2026-11-26T13:23:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.2.1
  - TASK-195
references:
  - decisions/webhooks.md
  - decisions/languages.md
  - decisions/security.md
  - decisions/plugins.md
parent_task_id: TASK-37.2
priority: high
ordinal: 554000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack W layer W2b, split out of TASK-37.2.1 at its planning (P1, human-approved 2026-11-26). Stacked above W2; waits on TASK-195 (host extension-point phase) merged. decisions/webhooks.md 5a Extension point and 9 Output encoding; languages.md.

Scope:
- capabilities/webhooks/hookspecs.py: the webhooks extension point (event consumers by event type, handlers by id), declared through TASK-195's register_extension_points and collected once at startup into a frozen WebhookExtensions value in the service registry; a duplicate handler id or a consumer for an unregistered event type fails boot naming the plugin.
- api.py: the EventConsumer, EventHandler and registrar Protocols, and EventAction (a consumer's contributed action: a MultilingualText label, an action id, a value), so the incident alert consumer (TASK-37.3) contributes triage actions without Slack types.
- adapters/slack.py: the channel poster on AsyncWebClient, the default consumer for alert and notification. It escapes every content-derived value (&, <, >) before inserting trusted tokens (resolved mentions, adapter-built https links), and lays out MultilingualText (title, summary, link and action labels) in the destination's shared languages (LanguagePolicy). Sender details are posted once, and Slack's 3,000-character section and 50-block limits are adapter constants (Slack API facts).
- The fallback rendering for an unmatched delivery or a render failure: escaped, truncated text of the decoded message under a bot-worded header from catalogue keys in capabilities/webhooks/locales/ (en-US and fr-FR parity).
- The mention resolver: TASK-37.2.1's find_email_addresses, then at most [webhooks] email_lookups_per_message users_lookupByEmail calls per message, cached per delivery (TASK-190 hand-off F-I).

Out of scope: protocols, the inbox, ingest and the route (TASK-37.2.2); sender-kind files, the Notify handler and the incident alert consumer (TASK-37.3).
Size: ~330 production LOC, ~7 files.
Production: dark. No route, no instance, no traffic; the extension point collects no implementation outside the capability.
Revert / blast radius: one git revert.
Change notice: none (dark slice, packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The webhooks extension point (consumers by event type, handlers by id) is declared through register_extension_points and its implementations are collected once at startup; a duplicate handler id or an unknown event type fails boot naming the plugin; no pluggy hook is called per request (test)
- [ ] #2 The Slack poster escapes every content-derived value: <!channel>, <@U123> and <https://x|y> in a payload field render inert, and links come only from validated https fields (test)
- [ ] #3 Bot wording (title, summary, link and action labels, the fallback header) is laid out as MultilingualText in the destination's shared languages, and sender details appear once (test)
- [ ] #4 The mention resolver makes at most the configured number of Slack lookups per message, cached per delivery (TASK-190 hand-off F-I) (test)
- [ ] #5 The fallback rendering posts escaped, truncated text of the decoded message under a catalogue-keyed header with en-US and fr-FR parity (test)
- [ ] #6 The capability core imports no slack_sdk; Slack shapes exist only in adapters/slack.py; make check-import-contracts, check-package-shape and check-fake-coverage are green (check)
- [ ] #7 The slice is dark: no route is mounted, no instance is read and production behaviour is unchanged (review)
- [ ] #8 mrkdwn objects carrying payload text set verbatim: true, plain_text is used where no trusted token is needed, truncation happens after escaping, and every Slack call has a timeout and a bounded retry (test)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-26T13:23:00Z

---

2026-11-26 OWASP review (TASK-37.2.1 planning): mrkdwn objects carrying payload text set verbatim: true; plain_text wherever no trusted token is needed; truncate after escaping; every Slack call (post, users_lookupByEmail) has a timeout and a bounded retry (OWASP API10:2023).

---
<!-- COMMENTS:END -->
