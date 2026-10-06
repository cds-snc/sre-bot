---
id: TASK-140.1
title: >-
  Record the external status update design in the incident and interaction
  decision records
status: In Progress
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-06 19:07'
labels:
  - incident
dependencies:
  - TASK-110.2
references:
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
  - decisions/platform-transports.md
parent_task_id: TASK-140
priority: high
type: docs
ordinal: 320000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Architecture only, no code. Amend decisions/incident-management.md: external status updates are a scribe use case; update records live under the incident id in core (record type, store interface); a StatusPagePublisher interface with a copy-ready default; the channel-to-incident lookup is core's find_incident_for_conversation, served for now by an adapter over the legacy incidents table until TASK-38.1's store replaces it. Accept the minimal part of decisions/interaction-toolkits.md (Draft) that packages need: registering Slack block actions and view submissions through a host-owned registrar, never the Bolt app.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 decisions/incident-management.md places external status updates, their records, the publisher interface and the interim lookup adapter, with a dated change-log line
- [x] #2 decisions/platform-entrypoints.md and decisions/transport-slack.md accept a registration-only Slack action and view-submission registrar with native-SDK listeners in feature entry points, with its limits and tickets; decisions/interaction-toolkits.md (Draft) points to them
- [x] #3 decisions/incident-management.md and decisions/transport-slack.md cite the 2026-10-06 research sources on status-update conventions and AI drafting with human approval
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Docs only: no code, no tests. Decisions taken in the 2026-10-06 planning session (human):
- Principle: business code (services, core/) is platform-neutral; a feature's platform entry point (entrypoints/slack.py) handles platform concepts with the native SDK (Bolt listener arguments, slack_sdk models); the host owns registration only (startup, ids registered once, the Bolt App never handed out). Checked against current practice: hexagonal adapters speak the native technology (alistair.cockburn.us/hexagonal-architecture); Netflix Dispatch's Slack plugin uses Bolt ack/respond in @app.view handlers over a platform-free incident service; Chat SDK (chat-sdk.dev/docs/modals) normalizes modals for Slack and Teams only, with Slack-only components and a raw platform payload. A neutral port stays right for outbound notifications.
- The action and view-submission registrar is recorded in platform-entrypoints.md and transport-slack.md (Accepted); interaction-toolkits.md stays Draft and points to them. The command model (CommandPayload, parser, help) is unchanged now; a follow-up task reassesses it against the principle.
- StatusPagePublisher and its copy-ready adapter live in scribe/ (one consumer); StatusUpdate and StatusUpdateStore in core/.
- The model fills structured fields only; a per-product comms profile (keyed by the ProductCatalog product) renders the text. The first slice ships one default profile modelled on GC Notify's published incident history; per-product profiles and status-page adapters are an expansion ticket.
- incident-management.md cites four sources (one over the governance cap, accepted): Statuspage incident-communication tips, GC Notify incident history, GC Sign In service page, Rootly AI docs.

Steps
1. decisions/incident-management.md (stay <= ~150 lines):
   a. Context: replace "the stubbed updates command" with what main does (add via a modal, show; incident_updates rewritten by read-then-SET, modules/incident/incident_folder.py:540-585).
   b. The incident record: the legacy incidents-table UUID is the incident id, kept by the store, so records keyed by it now survive the store change.
   c. core/ owns: the StatusUpdate record and StatusUpdateStore (records under the incident id, conditional-put appends); find_incident_for_conversation returns the incident id.
   d. Subdomain table: scribe holds external status updates (draft, approve, publish); own adapters: the copy-ready publisher.
   e. New subsection "External status updates": public stage vocabulary (Investigating / Identified / Monitoring / Resolved; FR Enquête en cours / Problème identifié / Sous surveillance / Résolu) distinct from the internal status; fields; code decides "nothing new" and keeps stages forward-only; responder approves in a modal, security incidents need a second confirmation; StatusPagePublisher in scribe with a copy-ready default; comms profile renders text, default modelled on GC Notify; next update time in ET/HE, about every 30 minutes, never silent; sources.
   f. Checks: one line (no status update written to the incident item; no model call when nothing new).
   g. Migration: name TASK-140; tolerated: find_incident_for_conversation served by a paginated scan of the legacy incidents table until TASK-38's store; the legacy updates command and incident_updates until TASK-140 retires them. Expansion list: replace "the updates command" with per-product comms profiles and status-page adapters.
   h. Changes: dated line.
2. decisions/platform-entrypoints.md: rule 2 (registrar covers commands, block actions and view submissions; never the App); rule 3 (an entry point may use its platform SDK's listener arguments and models; nothing below it may); table row and Consequences adjusted; Checks: slack_bolt and slack_sdk imported only in entrypoints/slack.py and adapters/; Migration: TASK-140; Changes line.
3. decisions/transport-slack.md: Handlers and Rich interactions describe registration of actions and view submissions (exact string ids, each once, duplicate fails boot; listeners get Bolt's arguments; ack first, validation errors in the view-submission ack, work after); limits (no options, shortcuts, view_closed, regex ids, middleware until a consumer needs them); Check at line 56 changed; cite Slack's acknowledge and modals docs and Rootly's review-before-submit; Migration TASK-140; Changes line.
4. decisions/platform-transports.md rule 1 (line 30): features never touch connections or the SDK app; entry points receive listener arguments. Changes line.
5. decisions/interaction-toolkits.md (Draft): Context and Open section point to the registration decision; the toolkit-vs-conventions question noted as leaning to conventions plus lint; dated change line.
6. decisions/README.md index rows checked; cascade grep of decisions/ for every reference to the changed rules.
7. Backlog via CLI: reword AC #2 and #3; create the command-model reassessment task and the expansion draft (per-product comms profiles, status-page adapters) under TASK-97; sync TASK-140 (references), 140.2 (native Bolt listeners, no contract payload types), 140.5 and 140.6 (publisher in scribe, comms profile), TASK-139 (status updates in the where-new-work-goes table) as notes; check ACs one by one; leave In Progress.

AC traceability: #1 -> step 1; #2 -> steps 2-6; #3 -> steps 1e and 3.
Verification: wc -l per record (<= ~150), four frontmatter fields, every relative link resolves, URLs fetched this session listed in notes; no Python changed, so ruff/mypy/pytest are not run (stated in notes).
Blast radius: records only; one git revert restores. Sibling tasks 140.2-140.6 read these records, so they merge after this PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-06 implementation (docs only):
- Amended decisions/incident-management.md (External status updates subsection; StatusUpdate and StatusUpdateStore in core/; scribe row and StatusPagePublisher adapters; legacy UUID is the incident id; Context corrected: the legacy updates command is live, not stubbed; Checks, Migration tolerated items, expansion list, change line), platform-entrypoints.md (rules 1-3, table, Consequences, Checks, Migration, change line), transport-slack.md (Block actions and view submissions paragraph with limits, Rich interactions, Checks, Migration, change line), platform-transports.md (rule 1 wording, change line), interaction-toolkits.md (Draft; points to the accepted rules; change line). README index rows unchanged (still accurate). Cascade grep: feature-packages.md:88 already consistent; no import-linter contract forbids slack_bolt.
- Sources fetched this session: support.atlassian.com/statuspage/docs/incident-communication-tips, support.atlassian.com/statuspage/docs/create-an-incident, articles.alpha.canada.ca/notification-gc-notify/system-status/ (EN and FR JSON, modified 2026-09-24), connect.canada.ca/en/discover/service.html, docs.rootly.com/ai/ai-summaries, docs.rootly.com/configuration/publishing-incidents, docs.slack.dev/tools/bolt-python/concepts/acknowledge, docs.slack.dev/surfaces/modals, chat-sdk.dev/docs/modals, github.com/Netflix/dispatch (incident/interactive.py), alistair.cockburn.us/hexagonal-architecture. FireHydrant docs fetched but not cited: they do not state human approval. incident-management.md cites four sources, one over the governance cap (human-accepted).
- Verification: line counts 150/79/77/77/67 (cap ~150); four frontmatter fields each; every relative .md link resolves; cited URLs return 200. No Python changed, so ruff, mypy and pytest were not run.
- Backlog: AC #2 and #3 reworded (human-approved); created TASK-141 (command model vs rule 3) and DRAFT-10 (per-product profiles, status-page adapters); DRAFT-7 description corrected.
<!-- SECTION:NOTES:END -->
