---
id: TASK-135
title: >-
  Reshape incident_draft and incident_summary into one incident subdomain over
  packages/incident/core
status: In Progress
assignee: []
created_date: '2026-10-01 14:05'
updated_date: '2026-10-02 18:01'
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
- [x] #1 packages/incident/core/ exposes, through core/api.py only, a conversation port that returns an ordered sequence of TranscriptMessage; no Slack payload, SDK type or Slack timestamp string crosses the port, and one Slack adapter implements it
- [x] #2 core/ has no entrypoints/, no hookimpls and no entry point; an import-linter layers contract for packages.incident lists the subdomains as independent siblings above core, with exhaustive = true
- [x] #3 /sre incident draft and /sre incident summarize are two handlers in one subdomain; each handler makes one service call, and the transcript is gathered by the service through core/api.py
- [x] #4 packages/incident_draft and packages/incident_summary no longer exist; one TranscriptMessage type remains; no channel port, Slack adapter or provider function is duplicated
- [x] #5 Command names, arguments and replies are unchanged: the TASK-36 legacy_surface suite is green before and after with no assertion change
- [x] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; import-linter ignore entries only shrank
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Decomposed for the single-PR size gate (as one change: about 30 production files across two packages, a new core/ and the import contracts, mixing a refactor with a package move). Four subtasks, each its own branch and PR:
- TASK-135.1: add packages/incident/core/ (TranscriptMessage, IncidentTranscriptReader, its provider and Slack adapter) and the incident umbrella layers contract. Nothing consumes it yet.
- TASK-135.2: incident_summary onto core. The service gathers through core/api.py, the handler makes one service call, and the package's channel interface, adapter and provider are deleted.
- TASK-135.3: incident_draft onto core, the same way, keeping a draft-only IncidentReportLinkLookup for the report bookmark.
- TASK-135.4: merge both packages into one subdomain under packages/incident/ and delete them. Mechanical move.

Why not the three slices the description suggests: 'core/ plus both packages repointed' alone is about 17 production files, and repointing the handlers first and moving the gathering second would rewrite the same handler code and tests twice. Cutting per package keeps each PR inside the gate and touches each handler once.

Order and blockers: 135.1 first; 135.2 and 135.3 are independent of each other and both follow 135.1; 135.4 follows both and is blocked on the TASK-97 decision for the subdomain's name. TASK-26.1 is done. TASK-25.10 blocks no slice: the summarizer call is not touched by the reshape, and whichever of the two lands second updates its import path and one import-linter entry.

Delivery (doc-2): standalone single PRs from main, no stack. 135.2 and 135.3 do not build on each other, and 135.4 waits on work outside the chain.

Decisions (human, 2026-10-02):
- The replacement for IncidentChannelPort is IncidentTranscriptReader, provider get_incident_transcript_reader.
- Filtering of the bot's own and system messages is a caller choice on the reader: draft filters and summarize does not, as today.
- The report-bookmark lookup stays out of core/ as the draft-only IncidentReportLinkLookup; report resolution belongs to the TASK-97 packet.
- packages/incident/documents, drive and meet do not fold into core/ here (TASK-38).
- 135.2 and 135.3 each add one temporary feature-independence ignore entry, both removed by 135.4.
- The merged subdomain has one service.py.
- draft_incident_document and summarize_transcript keep their signatures; the legacy_surface suite stubs them and asserts their positional arguments, so a gathering function is added above each.

AC map: #1 -> 135.1; #2 -> 135.1 (contract with core and the existing siblings) and 135.4 (the subdomain added); #3 -> 135.2 and 135.3 (one service call, gathering in the service) and 135.4 (one subdomain); #4 -> 135.2 and 135.3 (duplicates removed, one TranscriptMessage) and 135.4 (packages deleted); #5 and #6 -> every slice. The test-name renames from the TASK-136 notes land in 135.2 (incident_summary) and 135.3 (incident_draft). This task is done when its four subtasks are done.

Subdomain name (TASK-97, 2026-10-02): scribe. TASK-135.4 is unblocked.

Delivery (doc-2), superseding the line above (human, 2026-10-02): one stack of four layers, TASK-135.1 -> TASK-135.2 -> TASK-135.3 -> TASK-135.4, bottom-up, one task per layer and PR. The reason for standalone PRs is gone: TASK-135.4 waited on TASK-97, which was decided on 2026-10-02, so no layer waits on work outside the chain. 135.2 and 135.3 stay independent in content; the stack orders them summary first, then draft. Handoff doc under backlog/docs/stacks/.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From review (2026-10-01, #1518 and #1519): the reviewer read 'port' as a network port and asked for IncidentChannelReader. The replacement interface this task puts in packages/incident/core/ takes a role name, not a Port suffix (for example IncidentTranscriptReader, since it reads a conversation's transcript; confirm the name at planning), and its provider function follows (no get_..._port). Where this task's description and ACs say 'port', read 'interface'; the ACs are not reworded. Docstrings written here say 'interface'. The same rule for every other Port-suffixed Protocol is TASK-136; IncidentChannelPort is left to this task and excluded there.

From TASK-136 (2026-10-02): TASK-136.2 renames IncidentDocumentPort to IncidentDocumentStore and get_incident_document_port to get_incident_document_store, so where this task's text says IncidentDocumentPort, read IncidentDocumentStore once that slice merges. TASK-136 leaves the 'Summarizer port' / 'Port reading ...' prose in incident_summary (service.py, README.md, platforms/slack.py) alone because this task rewrites that package: write 'interface' there.

From TASK-136 (2026-10-02, human decision): the test-side names for the channel interface must be renamed by this task, together with IncidentChannelPort and get_incident_channel_port. They are the ports-and-adapters jargon TASK-136 retires, not network ports, and TASK-136 left them alone only because this task owns the channel interface and its tests. As of f182ecd2:
- tests/unit/packages/incident_draft/test_incident_draft_slack.py: the patch-target constant _CHANNEL_PORT (:31, used :77), the mock variable mock_port (:77, :82), and the helper docstring 'fake incident channel port' (:36).
- tests/unit/packages/incident_summary/test_incident_summary_slack.py: _CHANNEL_PORT (:27, used :59 and :71), mock_port (:59, :62, :71, :74), the test name test_handler_dispatches_with_channel_port_and_parsed_args (:52), and the helper docstring 'fake incident channel port' (:31).
- tests/integration/legacy_surface/conftest.py patches get_incident_channel_port (2 occurrences); it follows the provider-function rename.
Name them after the role name chosen for the replacement interface (for example _CHANNEL_READER / mock_reader if it is a Reader). When this task is done, rg -i 'port' over the incident tests and packages must find nothing; if any of these tests survive the reshape under a new path, the rename goes with them. This is what closes TASK-136 AC #5, whose only remaining exceptions are then genuine network ports (app/bin/dev-token.py, the aws_sns_notification auto_mitigation module and its test), which stay as they are.

2026-10-02: all five slices are implemented and committed on Stack G (handoff: doc-4), each In Progress with every AC checked, waiting for review and merge. Status here stays In Progress; a human moves it to Done once the stack has merged.

Delivery as built: five layers, not four. TASK-135.4 was split after implementation for review size (human, 2026-10-02): TASK-135.4 adds packages/incident/scribe/ unregistered (6178aa7e) and TASK-135.5 registers it and deletes packages/incident_draft and packages/incident_summary (5c5bcd37). Layers 1 to 3: 0724af46 (TASK-135.1), 9f57c514 (TASK-135.2), d902d38c (TASK-135.3).

ACs verified at 5c5bcd37, the top of the stack:
- #1: packages/incident/core/api.py exposes IncidentTranscriptReader, TranscriptMessage and get_incident_transcript_reader; signatures carry str, int, bool, datetime and TranscriptMessage only; one Slack adapter implements it (TASK-135.1). The interface took a role name, IncidentTranscriptReader, per TASK-136; the AC's word 'port' predates that rule.
- #2: core/ has no entrypoints/ and no hookimpl (rg hookimpl over packages/incident/core: no match) and pyproject declares no entry point; the incident-umbrella layers contract lists documents, drive, meet, scheduling and scribe above core with exhaustive = true, and lint-imports keeps it.
- #3: both handlers live in packages/incident/scribe/platforms/slack.py, each makes one service call, and the service gathers the transcript through core/api.py.
- #4: packages/incident_draft and packages/incident_summary are gone; the only TranscriptMessage class is packages/incident/core/domain.py; the one remaining Slack lookup outside core is the draft-only IncidentReportLinkLookup (human decision, 2026-10-02).
- #5: legacy_surface 17 passed before and after every layer; the only edits to its files are import paths, patch targets and the harness wiring, with no assert line changed.
- #6: ruff clean; mypy 65 errors, the baseline count, none in touched files; lint-imports 9 contracts kept; pytest tests --ignore=tests/smoke 6 failed, 3678 passed, the 6 being the known TASK-90 order leaks. Import-linter ignore entries naming the two packages went from 6 on main to 4 naming the subdomain; both temporary entries are gone.

Open for the reviewer (details on TASK-135.4 and TASK-135.5): one i18n resource registration instead of two; three registration unit tests changed body; the classes of rg hit kept in app/ (settings getter names, the Google Docs named-range prefix, test names).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 16:46
---
2026-10-02 (TASK-97 decided, decisions/incident-management.md): the merged subdomain is scribe; TASK-135.4 is unblocked. Answers to the questions this task left to the packet: IncidentDocumentStore moves into core/ as the Google adapter behind the IncidentReport interface in TASK-38.2, and IncidentReportLinkLookup is retired there (scribe reads the report reference from the record after find_incident_for_conversation); IncidentTranscriptReader keeps the conversation id string through 135.1 to 135.4 and takes a ConversationReference in TASK-38.2; packages/incident/documents, drive, meet and scheduling fold into core/, lifecycle/ and retrospective/ in TASK-38.2, 38.3 and 38.6, never here.
---
<!-- COMMENTS:END -->
