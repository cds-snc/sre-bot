---
id: TASK-145
title: >-
  Incident feature by purpose: response, comms and postmortem subdomains over
  core; scribe dissolved; legacy incident rebuilt surface by surface
status: To Do
assignee: []
created_date: '2026-10-09 16:41'
updated_date: '2026-10-09 19:36'
labels:
  - incident
  - features
  - slack
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/oncall.md
  - decisions/product-scope.md
priority: high
type: feature
ordinal: 350000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: contains no implementation. Replaces TASK-38 and its slices TASK-38.1 to TASK-38.8, and TASK-124.5 (archived 2026-10-09; the move it planned is now the first slice here), which were written for lifecycle | retrospective | scribe subdomains and mixed the rebuild of legacy surfaces with a subdomain formed around the model rather than around a purpose. TASK-144 (human-first status updates) finishes first and is the starting point.

DIRECTION (human, 2026-10-09): incident subdomains are the phases and audiences of the incident process, named in the domain's words; capabilities are the mechanisms they use; a subdomain is never named for a mechanism. Three subdomains over core/ and common/: response (responders while the incident is open: declare, status, severity, roles, archive, timeline, nudge, alert buttons, summarize), comms (what is said to audiences outside the response: public status updates now; internal updates, senior-management briefs and a status page later, each an audience profile over the same form and approval), postmortem (learning: the report draft, the postmortem meeting, later action items and feedback). scribe/ dissolves: summarize goes to response, draft goes to postmortem, status updates go to comms. The record gains severity (a closed set in common/), the five roles (incident commander, operations lead, communications lead, policy lead, postmortem owner) and keeps declared, detection, impact-start and impact-end so time to detect and time to recover derive from it. Who is on call is a capability (TASK-146), consumed at declare. decisions/incident-management.md and decisions/feature-packages.md hold the decision; this task holds the breakdown.

STARTING POINT (2026-10-09): main is at f5aa2ca5 with TASK-144.1 to TASK-144.3 merged (#1568, #1569, #1571). TASK-144.4 and TASK-144.5 are open on the stack-i branches and merge before group A starts; the shape below describes the tree once they have. packages/incident/ holds core/ (incident lookup over the legacy table, security reader, transcript reader, StatusUpdate types and the interim DynamoDB StatusUpdateStore), scribe/ (draft, summarize and the status-update use case: status_update.py with start, save and generate, status_update_approval.py, status_update_history.py, status_update_prompt.py, comms_profile.py, publisher.py, ports.py with IncidentDocumentStore, IncidentReportLinkLookup, TextGenerator and StatusPagePublisher, adapters for Google Docs, Slack, text generation and copy-ready text, one Slack entry point of about 920 lines and one views module of about 840 lines, three catalogues) and the adapter-only siblings documents/, drive/, meet/, scheduling/. app/modules/incident/ (about 4,700 lines) is the live legacy surface with no pinning test yet (TASK-36.1, TASK-36.3). The text-generation capability does not exist yet (TASK-25.10, TASK-134): the status-update path binds a scribe-local TextGenerator to the OpenAI Summarizer; draft and summarize call the Summarizer directly.

ASSUMPTIONS IN FORCE (change them here before the slice that depends on them starts):
- the umbrella moves to app/features/incident/ in the first slice, as it stands and with no runtime change, so every later slice builds in its final home; the package-shape check, enablement and TOML settings arrive with TASK-114, TASK-112 and TASK-111 on their own;
- the incident record store is an interim adapter in core/adapters/ over the existing DynamoDB table, behind an IncidentStore interface and an in-memory fake, as the status-update store already is; TASK-108 and TASK-109 later swap its inside for the storage contract;
- the comms carve-out moves the scribe-local TextGenerator interface, its OpenAI binding and the availability predicate whole; draft and summarize keep calling the Summarizer directly until TASK-25.10 replaces both with the capability, so nothing is duplicated;
- each legacy surface is pinned (TASK-36.1 for commands and interactions, TASK-36.3 for jobs) before the slice that rebuilds it; command names, modal fields, replies and i18n keys do not change during the rebuild, apart from three added role pickers and the SEV0 option in the severity pickers;
- the alert buttons register into the webhooks capability's extension point when it exists, otherwise through the Slack registrar with a later move;
- severity is a closed set with levels 0 to 4 (0 for an event spanning several products) or unset; the set is wide because teams use different scales today, the legacy sev-1 to sev-4 values map one to one, and it narrows only if the organisation standardises;
- a subdomain's entry point stays two flat modules, entrypoints/slack.py and entrypoints/slack_views.py; a views split waits for TASK-118;
- renaming the plugin renames its action ids; modals open across that deploy are accepted as broken, as TASK-144.4 accepted.

LAYERS, each a single PR under the size gate, merged bottom-up (a gh stack is acceptable within a group):
A. In place, after TASK-144: TASK-145.1 (the umbrella moves to features/incident with the first-mover wiring) -> TASK-145.2 (status-update wording and prompt text out of the views module) -> TASK-145.3 (status-update handlers call one service method each) -> TASK-145.4 (comms carved out of scribe as plugin incident.comms).
B. Core, after TASK-145.1: TASK-145.5 (record, interim store, severity, five roles, two-part command check, common/) -> TASK-145.6 (resource interfaces: conversation, report absorbing documents/, drive/ and scribe's section writer, product catalog; transcript reader takes the reference).
C. Response, after pinning: TASK-145.7 (declare and the alert buttons; meet/ folds into core) -> TASK-145.8 (status, severity, show and update, roles, archive, recreate) -> TASK-145.9 (timeline capture, nudge job; summarize moves in; incident leaves aws_platform).
D. Postmortem, after TASK-138: TASK-145.10 (meeting scheduling over the calendar capability) -> TASK-145.11 (draft moves in; scribe deleted).
E. Cutover: TASK-145.12 (list sheet becomes a write-only projection; references backfilled) -> TASK-145.13 (delete app/modules/incident; layers contract response | comms | postmortem exhaustive).
TASK-146.3 (declare invites the on-call person through the on-call capability) joins group C once TASK-146.1 exists.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every subtask is done
<!-- AC:END -->
