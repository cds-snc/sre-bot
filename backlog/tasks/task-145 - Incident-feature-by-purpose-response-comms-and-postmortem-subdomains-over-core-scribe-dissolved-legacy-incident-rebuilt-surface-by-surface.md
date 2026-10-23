---
id: TASK-145
title: >-
  Incident feature by purpose: response, comms and postmortem subdomains over
  core; scribe dissolved; legacy incident rebuilt surface by surface
status: To Do
assignee: []
created_date: 2026-10-09 16:41
updated_date: '2026-10-23T17:07:00Z'
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
  - https://github.com/cds-snc/sre-bot/issues/1687
priority: high
type: feature
ordinal: 350000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: contains no implementation. The incident feature is rebuilt by purpose, surface by surface, in app/features/incident/; decisions/incident-management.md and decisions/feature-packages.md hold the decision, this task holds the breakdown. TASK-147 (postmortem as records) and TASK-154 (status lifecycle and close redesign) are new behaviour built on this rebuild, outside it.

DIRECTION: incident subdomains are the phases and audiences of the incident process, named in the domain's words; capabilities are the mechanisms they use; a subdomain is never named for a mechanism. Three subdomains over core/ and common/: response (responders while the incident is open: declare, status, severity, roles, archive, timeline, nudge, alert buttons, summarize), comms (what is said to audiences outside the response: public status updates now; internal updates, senior-management briefs and a status page later, each an audience profile over the same form and approval), postmortem (learning: the report draft, the postmortem meeting, later action items and feedback). scribe/ dissolves: summarize goes to response, draft goes to postmortem, status updates are in comms. The record carries severity (a closed set in common/), the five roles (incident commander, operations lead, communications lead, policy lead, postmortem owner) and keeps declared, detection, impact-start and impact-end so time to detect and time to recover derive from it. Who is on call is a capability (TASK-146), consumed at declare.

ASSUMPTIONS IN FORCE (change them here before the slice that depends on them starts):
- the umbrella lives in app/features/incident/; the package-shape check, enablement and configuration-file settings arrive with TASK-114, TASK-112 and TASK-111 on their own;
- the incident record store is IncidentStore over the records contract (RecordStore) with an in-memory fake, obtained through the svcs registry and the ServiceScopeOpener; the status-update store moves onto the records contract in TASK-145.5.6;
- settings values follow the configuration files (decisions/configuration.md): each owner moves its Google resource ids out of the interim [google_resources] table (TASK-145.6, 145.7, 145.10, 145.12), and a feature value keeps its table and keys when its settings class moves;
- the first writers that persist a Slack tenant (TASK-145.5.7 apply, TASK-145.7) wait for the Slack inbound tenant guard (TASK-157);
- draft and summarize call the text-generation capability (TASK-25.10, with the structured fill from TASK-134) by the time they move;
- each legacy surface is pinned (TASK-36.1 for commands and interactions, TASK-36.3 for jobs) before the slice that rebuilds it; command names, modal fields, replies and i18n keys do not change during the rebuild, apart from three added role pickers and the SEV0 option in the severity pickers;
- the alert buttons register into the webhooks capability's extension point when it exists, otherwise through the Slack registrar with a later move;
- severity is a closed set with levels 0 to 4 (0 for an event spanning several products) or unset; the set is wide because teams use different scales today, the legacy sev-1 to sev-4 values map one to one, and it narrows only if the organisation standardises;
- a subdomain's entry point stays two flat modules, entrypoints/slack.py and entrypoints/slack_views.py; a views split waits for TASK-118;
- renaming a plugin renames its action ids; modals open across that deploy are accepted as broken.

LAYERS, each a single PR under the size gate, merged bottom-up (a gh stack is acceptable within a group); doc-11 holds the queue:
A. In place: TASK-145.1 (the umbrella in features/incident) -> TASK-145.2 (status-update wording and prompt text out of the views module) -> TASK-145.3 (status-update handlers call one service method each) -> TASK-145.4 (comms carved out of scribe as plugin incident.comms).
B. Core, Stack K: TASK-145.5 (coordinator of TASK-145.5.1 to TASK-145.5.10, with TASK-152: record, store over the records contract, severity, five roles, the conversation lookup, common/, the status-update store, the legacy item bridge and the legacy upgrade job) -> TASK-145.6 (resource interfaces with conversation_is_writable: conversation, report absorbing documents/, drive/ and scribe's section writer, product catalog; transcript reader takes the reference).
C. Response, Stack L, after pinning: TASK-145.7 (declare and the alert buttons; meet/ folds into core) -> TASK-145.8 (status, severity, show and update, roles, archive, recreate) -> TASK-145.9 (timeline capture, nudge job; summarize moves in; incident leaves aws_platform). The TASK-145.5.7 upgrade job runs after TASK-145.8 deploys and before TASK-145.9 merges.
D. Postmortem, Stack M, after TASK-138: TASK-145.10 (meeting scheduling over the calendar capability) -> TASK-145.11 (draft moves in; scribe deleted).
E. Cutover: TASK-145.12 (list sheet becomes a write-only projection; the sheet import is removed and the TASK-145.5.7 upgrade job reruns) -> TASK-145.13 (delete app/modules/incident; layers contract response | comms | postmortem exhaustive).
TASK-146.3 (declare invites the on-call person through the on-call capability) joins group C once TASK-146.1 exists.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every subtask is done
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13: the postmortem as records (action items with GitHub issues, the timeline and the narrative document, built dark behind a flag with a UX session and a rollout) is TASK-147, separate from this rebuild because it is new behaviour. TASK-145.5 now waits for the records contract (TASK-108).
<!-- SECTION:NOTES:END -->
