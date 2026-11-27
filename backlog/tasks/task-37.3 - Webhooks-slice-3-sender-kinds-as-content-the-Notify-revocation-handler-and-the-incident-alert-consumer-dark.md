---
id: TASK-37.3
title: >-
  Webhooks slice 3: sender kinds as content, the Notify revocation handler and
  the incident alert consumer (dark)
status: To Do
assignee: []
created_date: 2026-07-28 18:40
updated_date: '2026-11-27T17:31:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.2.2
  - TASK-25.8
references:
  - decisions/webhooks.md
  - decisions/platform-transports.md
  - decisions/transport-slack.md
  - https://github.com/cds-snc/sre-bot/issues/1378
  - decisions/plugin-architecture.md
parent_task_id: TASK-37
priority: high
ordinal: 98000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack W layer W4, the top of the dark chain (decisions/webhooks.md as rewritten in TASK-37.1; TASK-168 research packet section 5, row 37.3, Q3, Q7 and OQ8). Ports today's per-sender Python into provisioned content and code handlers.

Scope:
- The 11 legacy sender kinds as YAML under app/content/webhooks/sender-kinds/, each with an example under app/content/examples/webhooks/sender-kinds/ (example.com, no organisation data); the webhooks/sender-kinds content kind becomes required.
- Parity tests from the TASK-36.2 fixtures, plus an injection case per kind (Slack control sequences render inert).
- Findings F-E and F-F (TASK-37.2 comment #3) become tests: matching order is declared per instance, so the os.listdir tie-break is gone; a suppress: true kind acknowledges with no post, so budget_auto_adjustment no longer answers 400.
- The Notify key-revocation handler (api_key_detected) as a registered handler in its own small owning package (candidate app/features/notify_key_leak/, OQ8), not in webhooks core and not in content: a linear regex, async httpx through the TASK-25.8 Notify contract client, run from the inbox item and keyed on the delivery id.
- The incident feature registers its alert consumer through the webhooks hookspec, contributing the triage actions (call incident, ignore) to the poster's render; the button contract is unchanged here (its value changes in TASK-37.4.3).
- CODEOWNERS: an entry per app/content/<owner>/ folder when its first content lands, with a check (TASK-37.1 plan correction C10).
- Whether the AccessRequest kind is ported or deleted follows the human evidence (packet section 6, item 3).

Out of scope: instances, routes and the cutover (TASK-37.4.x).

Size: ~200 production LOC plus 22 YAML files: a size exception on file count is requested (content files are reviewed as data).
Production: dark. No instance uses the kinds and no route is mounted.
Revert / blast radius: one revert.
Change notice: none (dark slice, packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each legacy sender kind is a YAML file under app/content/webhooks/sender-kinds/ with an example under app/content/examples/webhooks/sender-kinds/; the kind is required and make check-content-schemas is green (check)
- [ ] #2 For every TASK-36.2 fixture the content renders the same message as the legacy handler (parity test per kind)
- [ ] #3 An injection case per kind: <!channel>, <@U123> and <https://x|y> in payload fields render inert (test)
- [ ] #4 Matching order is declared, so the F-E tie no longer depends on os.listdir order; a suppress: true kind acknowledges with no post, replacing the F-F 400 (test)
- [ ] #5 The Notify key-revocation handler lives in its own package, is registered by id through the webhooks hookspec, uses a linear regex and async httpx through the TASK-25.8 Notify client, runs from the inbox item and acts once per delivery id (test)
- [ ] #6 The incident feature registers an alert consumer that contributes the triage actions; webhooks core imports no feature and the button contract is unchanged (test)
- [ ] #7 A CODEOWNERS entry exists for each app/content/<owner>/ folder when its first content lands, and a check fails when a folder under app/content/ has no CODEOWNERS entry (check)
- [ ] #8 The slice is dark: no instance uses the kinds and no route is mounted (review)
- [ ] #9 Each kind's bot-worded templates hold en-US and fr-FR wording, the French reviewed by a human before merge; parity tests compare the en-US part (test + review)
- [ ] #10 A kind whose handler: id no plugin registered fails boot naming the file (test)
- [ ] #11 The Notify package's product area is named; the webhooks enablement key sits in that area's table, or in [plugins.shared] when its consumers span areas (check)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27 (TASK-37.2.2 implementation, hand-offs): (a) SNS kinds match the decoded document: the signed fields (Type, MessageId, TopicArn, Subject, Timestamp) with Message parsed when it is a strict JSON object, so paths read $.Message.<field>; a text Message stays a string (decisions/webhooks.md 2). (b) A kind with suppress: true yields no event, so neither consumers nor its handler run (interpret returns Suppressed with no event): decide at planning how the Notify revocation kind runs its handler without posting (for example no destinations on its instance, or a suppress that still hands the event to the handler). (c) Consumers and handlers receive the event rendered in the instance languages (LanguagePolicy.reply_languages(None)); each destination's post is rendered in that destination's shared languages. (d) Each consume and handler call is recorded on the inbox item, so a retry never repeats a finished one; an exception is retried by the inbox.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-10 16:18

---

ARCHITECTURE CONSTRAINT ADDED 2026-09-10 (human-directed). Chat platforms are split by direction (decisions/platform-entrypoints.md, Draft):
- Entry point: SDK runtime and connection lifecycle, verification, dispatch and in-request replies. Goes to app/server/<platform>/, beside HTTP.
- Handler contract: typed request/response models, argument parser, OperationResult renderer, in-request reply Protocol and registrar Protocol. Goes to app/infrastructure/<platform>/, with no runtime and no I/O.
- Messaging people or channels outside a request: goes to a capability package (decisions/capability-packages.md, Draft) or a Path B adapter.
- Web API client and classify_<platform>_error: app/integrations/<platform>/ (unchanged).

Features never receive SDK runtime objects such as the Bolt App. Do not move a runtime into app/infrastructure/<platform>/ in the meantime, so it moves only once.

The OperationResult renderer is part of the Slack handler contract and stays importable from app/infrastructure/slack/. Posting outside a request belongs to a capability package or a Path B adapter, not to a SlackService in the contract.

---

created: 2026-11-25T20:50:00Z

---

2026-11-25 re-cut (TASK-168, human-approved; TASK-37.1 plan corrections C6-C10). Old title "Webhooks slice 3: transport-neutral intent + Slack renderer". Old ACs, verbatim (short), and where each intent now lives:
- #1 "The webhooks capability core imports no slack_sdk/WebClient and constructs no Block Kit; Slack shapes exist only behind the transport renderer" -> TASK-37.2.1 AC #1 (no slack_sdk in the core) and AC #6 (the Slack poster adapter).
- #2 "The interpret stage emits transport-neutral intents; the Slack renderer is the only place intents become Slack messages" -> TASK-37.2.1 AC #2 (InboundEvent) and AC #9 (consumers by event type).
- #3 "The os.listdir/importlib pattern-handler registries are deleted" -> the walk is replaced by content in this task and deleted in TASK-37.5 AC #1.
- #4 "Incident-button behaviour is expressed as an intent/target attribute, not a hook_type magic-string branch in the route" -> this task's new AC #6 (the incident alert consumer) and TASK-37.4.3 AC #6 (the button value).
- #5 "Message output for existing SNS notification types is unchanged: TASK-36 smoke tests pass before and after" -> this task's new AC #2 (parity per kind) and TASK-37.4.3 AC #8.
Old dependencies: TASK-37.2 (now the coordinator; this task waits on its last child TASK-37.2.2) and TASK-26.1 (Done) dropped; TASK-25.8 added (Notify: the revocation handler calls the contract client). Comment #1 (the platform-entrypoints split) still applies: posting outside a request lives in the capability's adapter. Nothing is archived.

---

created: 2026-11-25T20:54:00Z

---

Carried from TASK-168 comment #4 (2026-11-25, human, TASK-193 approved): bot-authored wording (headers, buttons, titles the bot writes) is MultilingualText from LanguagePolicy; sender-supplied alert content (AWS, other senders) keeps its source language, placed once (decisions/languages.md). Applies to the incident alert consumer's triage actions and any bot-authored wording in the sender-kind templates.

---

created: 2026-11-26T13:19:00Z

---

2026-11-26 (TASK-37.2.1 planning, human-approved P2 and P5).
- P2: each kind's bot wording (title, summary, link labels) is one Liquid template per supported language (en-US and fr-FR), required by the kind's model; the French wording of the 11 kinds needs a human review before merge; parity tests compare the en-US part with the legacy English output; sender text goes in details, once.
- P5: OQ8 names the Notify key-revocation package's product area; if it is not incident response, the webhooks enablement key moves from [plugins.incident_response] to [plugins.shared] in this task (plugins.md 2026-11-06).
- The boot check that a kind's handler: id was registered by a plugin lands here, with the first handler (TASK-37.2.3 collects handlers).

---
<!-- COMMENTS:END -->
