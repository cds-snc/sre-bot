---
id: TASK-135
title: >-
  Reshape incident_draft and incident_summary into one incident subdomain over
  packages/incident/core
status: To Do
assignee: []
created_date: '2026-10-01 14:05'
updated_date: '2026-10-01 20:28'
labels:
  - plugin-architecture
  - features
  - slack
milestone: m-7
dependencies:
  - TASK-26.1
  - TASK-25.10
  - TASK-97
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - decisions/outbound-clients.md
  - decisions/platform-transports.md
priority: medium
type: task
ordinal: 294000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human decision 2026-10-01 (decisions/feature-packages.md, umbrella rules 2 to 5): a subdomain is a unit you would enable, own or delete on its own, not one command; what every subdomain of a feature works on lives in the feature's core/, which may do I/O and is imported only through core/api.py; subdomains never import each other.

TODAY (verified 2026-10-01, after TASK-26.1.2)
- packages/incident_draft and packages/incident_summary are two top-level packages, each one slash command (/sre incident draft, /sre incident summarize).
- Each defines its own IncidentChannelPort in service.py, its own SlackIncidentChannel in adapters/slack.py and its own provider function, for the same lookups. The ports return raw Slack payloads (Mapping[str, Any]) and take a pre-formatted Slack timestamp.
- The handlers gather the inputs themselves before calling the service: platforms/slack.py is 484 lines in incident_draft and 351 in incident_summary, and holds the transcript building (history fetch, display-name resolution, own-bot and system-message filtering, ordering, timestamps). The feature-packages.md handler rule is one service call and about 30 lines.
- Each declares its own TranscriptMessage.

TARGET
- packages/incident/core/ holds the incident conversation port and its Slack adapter. The port is shaped by what the feature needs and returns domain types: read a conversation's transcript since a point in time, up to a limit, as an ordered sequence of TranscriptMessage. Name resolution, ordering and the filtering of the bot's own and system messages happen behind the port. No Slack payload, SDK type or Slack timestamp format crosses it. core/api.py is its only public surface; core/ has no entrypoints/, no hookimpls and no entry point.
- One incident subdomain holds both use cases: two handlers, two service functions. Each handler makes one service call. Each service function reads the transcript through core/api.py and calls the text-generation capability (TASK-25.10).
- packages/incident_draft and packages/incident_summary are deleted, with every importer and mock patch string rewritten.
- Behaviour-preserving: command names, arguments and replies unchanged, pinned by the TASK-36 legacy_surface suite.

MUST NOT PREJUDGE TASK-97. This task puts only the conversation transcript port in core/. The incident record, its status lifecycle, the channel-to-incident resolution and the report port arrive with the TASK-97 packet and TASK-38. The subdomain's name and whether the report document port (IncidentDocumentPort, one consumer today) belongs in core/ come from that packet.

QUESTIONS FOR THE PLANNER (raise them in chat, do not decide them in the plan)
- The subdomain's name, if the TASK-97 packet does not give one.
- Whether the adapter-only packages packages/incident/documents, drive and meet (no hookimpls, built for modules/incident) fold into core/ here or with TASK-38.

SIZE. This is likely over the single-PR gate. A natural split: (1) core/ with the domain-typed transcript port, both packages repointed to it; (2) transcript gathering moved from the handlers into the services; (3) the two packages merged into one subdomain. Decompose at planning.

Waits for TASK-26.1 (the handlers are re-signed onto the Slack registrar and reply Protocols first), TASK-25.10 (the capability the services call) and TASK-97 (subdomain names and what core/ owns).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/incident/core/ exposes, through core/api.py only, a conversation port that returns an ordered sequence of TranscriptMessage; no Slack payload, SDK type or Slack timestamp string crosses the port, and one Slack adapter implements it
- [ ] #2 core/ has no entrypoints/, no hookimpls and no entry point; an import-linter layers contract for packages.incident lists the subdomains as independent siblings above core, with exhaustive = true
- [ ] #3 /sre incident draft and /sre incident summarize are two handlers in one subdomain; each handler makes one service call, and the transcript is gathered by the service through core/api.py
- [ ] #4 packages/incident_draft and packages/incident_summary no longer exist; one TranscriptMessage type remains; no channel port, Slack adapter or provider function is duplicated
- [ ] #5 Command names, arguments and replies are unchanged: the TASK-36 legacy_surface suite is green before and after with no assertion change
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; import-linter ignore entries only shrank
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From review (2026-10-01, #1518 and #1519): the reviewer read 'port' as a network port and asked for IncidentChannelReader. The replacement interface this task puts in packages/incident/core/ takes a role name, not a Port suffix (for example IncidentTranscriptReader, since it reads a conversation's transcript; confirm the name at planning), and its provider function follows (no get_..._port). Where this task's description and ACs say 'port', read 'interface'; the ACs are not reworded. Docstrings written here say 'interface'. The same rule for every other Port-suffixed Protocol is TASK-136; IncidentChannelPort is left to this task and excluded there.
<!-- SECTION:NOTES:END -->
