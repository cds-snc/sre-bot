---
id: TASK-97
title: >-
  Decide the incident management architecture: system of record, coordination
  boundary, and whether to back it with an external IR platform (DFIR-IRIS)
status: Done
assignee: []
created_date: '2026-09-16 14:24'
updated_date: '2026-10-08 15:54'
labels:
  - architecture
  - incident
  - phase-5
milestone: m-5
dependencies: []
references:
  - decisions/workplace-systems.md
  - decisions/feature-packages.md
  - decisions/outbound-clients.md
  - app/modules/incident
  - decisions/plugin-architecture.md
  - decisions/incident-management.md
priority: high
ordinal: 222000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ARCHITECTURE DECISION, no implementation. Produces a decisions/ record and an implementation-ready packet; TASK-38 (the rebuild) and TASK-135 (the draft and summary reshape) follow this task.

CONTEXT. modules/incident is the largest legacy surface (4636 LOC, 17 modules). It was designed around Google Workspace and DynamoDB: the incident list lives in a Google Sheet, the report lives in a Google Doc, the retro is a Google Calendar event with a Meet link, and the record in DynamoDB is reached through hand-built AttributeValue dicts. Human direction 2026-09-16: incident is to be redesigned from the ground up, with no assumption that any existing logic survives. A report document may or may not exist. A list of incidents and their statuses almost certainly exists, tracked as app-level database records and definitely not a spreadsheet. A video call probably exists, and which tool provides it is unknown and not yet interesting.

THE QUESTION THIS TASK ANSWERS. What does the SRE bot own, and what does it coordinate?
- Option A - the bot owns incident management. Incident records, statuses, timeline and artifacts are app records in the storage capability, and the bot is the system of record.
- Option B - the bot coordinates, an external IR platform owns the case. DFIR-IRIS (open-source DFIR case management, REST API) was raised as a candidate: a richer and more mature system, feature-complete for case management, timeline, evidence and reporting. The bot would keep what only it can do - conversation lifecycle in Slack or Teams, launching a video call, paging, nudging, notifications, workplace artifacts - and delegate the case itself to the platform API.
- Option C - a split: the bot owns a thin coordination record (which channel, which platform case, which artifacts) and the platform owns the case content.

WHY IT IS WORTH DECIDING EARLY, EVEN THOUGH IMPLEMENTATION COMES LATER. The answer determines whether an app-owned incident domain model, its storage schema and its migration off Google Sheets are worth building at all. Under Option B or C much of that investment is wasted or reduced to a reference record. The decision is cheap; the work it governs is not.

INPUTS TO GATHER
- DFIR-IRIS API surface, auth model, self-hosting and operational cost, licence, data residency, and whether it can be reached from the app deployment. Use web research; do not rely on recall.
- What the current feature actually does that users depend on, separated from how it does it (command surface, notifications, the retro flow, the status lifecycle, metrics reporting).
- Who consumes the incident metrics sheet today and what would replace it.
- The related open defects, which are evidence of the current design rather than work to schedule here: TASK-73 (status updates never reach the sheet), TASK-86 (retro events drop description, reminders and conference requestId), TASK-81 (folder display limit shim), TASK-87 (non-idempotent Workspace writes).

CONSTRAINTS ON WHATEVER IS CHOSEN (these are design inputs, not build steps; they were moved here from TASK-38 on 2026-09-16 because they describe the redesigned feature and not the relocation)
- No record of truth in a workplace document or spreadsheet. Anything the app keeps lives in app storage through the storage capability; a surviving document or sheet is a collaboration space the app references, or a write-only projection never read back into a business decision (decisions/workplace-systems.md rule 5).
- No new app/infrastructure/<service>/ Protocol for a workplace concern (rule 1). Where a workplace system is used, one adapter per system sits behind a feature-owned port, and which system applies is data - the artifact's stored reference, the conversation's platform, the person's linked account - never a global provider setting (rule 3).
- Every stored workplace-artifact reference carries its system and tenant alongside the vendor id; no bare vendor ids, and no human link built by string-formatting a vendor URL (rule 4). modules/incident/core.py:176, :182 and :481 hardcode a docs.google.com URL today.
- Hosting services (storage, queue, idempotency, secrets) are reached only through capability Protocols, so moving the app off AWS to Azure, GCP or on-prem touches no incident code.
- No persisted state is written with a read-modify-write or a vendor list-append.
- An external IR platform, if chosen, is an outbound integration governed by decisions/outbound-clients.md and sdk-typing.md, behind a feature-owned adapter returning OperationResult - never a new infrastructure capability.

HUMAN DIRECTION 2026-10-01 (design inputs; they narrow the question above but do not choose between Options A, B and C)
- The incident is the anchor, not the channel. Today the Slack channel is the source of truth that every incident is recorded against, and an archived channel cannot be edited, so features break once a channel is archived. A bot-owned record keyed by the incident exists under every option, at least as the thin coordination record of Option C. The conversation, the status and the report are resources that record references.
- Resources are flexible by kind and by system: a conversation on a configured platform, the current status, a report that is a Google Doc today and may be a Word document or something else later. Each is a purpose-shaped port with one adapter per system, selected by the stored reference (decisions/workplace-systems.md rules 3 and 4).
- These live in features/incident/core/ (decisions/feature-packages.md umbrella rule 4, amended 2026-10-01), with the shared command check: which incident does this command refer to, and may it still be changed. Split the check in two: every command must map to a known incident; only an operation that writes to the conversation needs the conversation to be writable. A status or report update on an incident whose channel is archived should keep working.
- Subdomains are enablement units, not commands (umbrella rule 2). The packet names the incident subdomains on that basis, including the one TASK-135 makes of draft and summarize, and says what core/ owns.
- Drafting and summarizing are uses of the text-generation capability (decisions/plugin-architecture.md; TASK-25.10, TASK-134); the incident feature supplies the transcript, the prompt or template and incident-specific post-processing.

DEPENDENCIES AND COUPLINGS
- The storage operations incident would need are TASK-27.1 and TASK-27.2.
- Person and linked-account resolution is TASK-83.
- While incident persistence stays on the provisional packages/aws_platform DynamoDB adapter, the seam baseline TASK-25.2.5.5 creates cannot empty, so TASK-88 cannot dissolve packages/aws_platform. Whichever option is chosen must say when incident leaves that adapter.
- TASK-80 asks whether Google Docs should be promoted to an infrastructure DocumentProvider. decisions/workplace-systems.md rule 1 now answers that with no; TASK-80 needs re-scoping or closing, and this task should state the replacement expectation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A decisions/ record is added or amended stating which of the options is chosen, what the SRE bot owns, what it coordinates, and where the system of record lives
- [x] #2 If an external IR platform is chosen, the evaluation is recorded with sourced evidence gathered from current documentation (API surface, auth, hosting, licence, data residency, operational cost) rather than recall, and the integration is scoped as a feature-owned adapter under decisions/outbound-clients.md, never an infrastructure capability
- [x] #3 The constraints listed in the description are carried into the chosen design and each one is either satisfied or recorded as a named, time-boxed divergence
- [x] #4 The user-visible capabilities of today's feature are inventoried separately from their current implementation, so the redesign can drop implementations without silently dropping capabilities
- [x] #5 An implementation-ready packet exists with right-sized backlog tasks under the single-PR size gate, sequenced against TASK-27.1, TASK-27.2, TASK-83 and TASK-38, and stating when incident leaves the provisional packages/aws_platform DynamoDB adapter so TASK-88 can dissolve that package
- [x] #6 The packet names the incident subdomains as enablement units and states what features/incident/core/ owns (record, store, resource ports, the shared command check), following the 2026-10-01 human direction; TASK-135 and TASK-38 are sequenced against it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-02 decision session (architecture mode; no production code, no tests, no git writes).

OUTCOME: decisions/incident-management.md (Accepted 2026-10-02). Option A: the bot owns incident management; the system of record is the incident record in app storage through the storage contract; the conversation, report, video call, retrospective and optional external case are coordinated resources recorded as typed references with system, tenant and vendor id. The external platform seam is ExternalCaseRecorder in core/api.py with a no-op recorder when no case-system instance is configured; DFIR-IRIS evidence is recorded in the record's Context with sources. Subdomains: lifecycle, retrospective, scribe. core/: record, IncidentStore, find_incident_for_conversation and conversation_is_writable, IncidentConversation, IncidentReport, IncidentTranscriptReader, ProductCatalog, ExternalCaseRecorder.

HUMAN ANSWERS APPLIED (2026-10-02, "apply the recommendations"): the metrics sheet stays a write-only projection through the migration and its consumers are asked on DRAFT-1 before it is replaced; the system for a new incident's resources is an incident-feature policy setting defaulting to the only configured tenant; the report and the video call stay default-on at declare; enablement units are the three subdomains; paging and on-call stay a separate decision. AC #2 is read as proposed in comment #4 (integration point specified from sourced evidence; no platform adopted).

AC EVIDENCE
- #1: decisions/incident-management.md, sections Decision (Option A, what the bot owns and coordinates, "the system of record is the incident record in app storage") and "What the design rejects".
- #2: the record's Context paragraph on DFIR-IRIS cites twelve current-documentation URLs for licence, API surface and versions, auth, hosting and datastore, residency, operational cost, reachability and localisation, plus the TheHive and Dispatch comparators; the integration is scoped in "The optional external platform" as a feature-owned adapter in core/adapters/ over integrations/<system>/, never infrastructure. DRAFT-3 and DRAFT-4 carry the later build.
- #3: every constraint in the description maps to a Decision clause (rule 5: record in app storage and a write-only projection; rule 1 and 3: feature-owned interfaces, adapters selected by the stored reference, no global setting; rule 4: reference types with system and tenant and vendor-provided links; hosting through the storage contract; timeline entries as records, no read-modify-write; external platform as outbound adapter). Divergences are named and time-boxed in the record's Migration section, each with its closing slice (TASK-38.2, 38.3, 38.4, 38.5, 38.6, 38.7).
- #4: the capability inventory is below in these notes (45 capability lines with file:line evidence, separated from the implementation column) and summarised in the record's Context, including the five surfaces missing from INVENTORY.md.
- #5: TASK-38.1 to TASK-38.8 created as children of TASK-38, each scoped under the single-PR gate, with dependencies on TASK-124.5, TASK-27.2, TASK-108, TASK-109 (38.1), TASK-36.1 and TASK-37 (38.3), TASK-36.3 and TASK-64 (38.5), TASK-36.1 (38.6); TASK-83.9 and TASK-83.10 follow TASK-38. Incident leaves packages/aws_platform in TASK-38.5 (its AC #3), which is recorded on TASK-88. Expansion drafts DRAFT-1 to DRAFT-7 are under TASK-97 and block nothing in the migration.
- #6: the record's "The feature umbrella" names lifecycle, retrospective and scribe as enablement units with entry points and says what core/ owns, including the two-part command check; TASK-135 (comment) and TASK-135.4 (description, AC #4, plan: scribe) and TASK-38 (description) are sequenced against it; TASK-124.5 and doc-2 Waves 0, 4 and 5 updated.

FILES CHANGED THIS SESSION (not committed): decisions/incident-management.md (new), decisions/workplace-systems.md (Migration cross-reference and Changes line), backlog/docs/doc-2 (Wave 0, 4, 5 lines), backlog tasks 97, 38, 38.1 to 38.8 (new), 124.5, 135, 135.4, 88, 65, 73, 86, 87, drafts DRAFT-1 to DRAFT-7 (new). TASK-80 is archived with its replacement expectation already recorded; the record's Consequences restates it. TASK-81 is archived as superseded by TASK-38 AC #13; TASK-38.3 closes the picker shim.

FOR THE HUMAN: status left at To Do for you to move; DRAFT-1 holds the open question on the metrics sheet consumers.

CAPABILITY INVENTORY (read at c8de7643; capability | how today | evidence | notes)

## A. Capabilities (what users depend on) | How today | Evidence | Notes
1 DECLARE
- Modal: name, product folder, severity (none/sev-1..4), security yes/no, locale toggle; private_metadata carries optional source-alert permalink | Slack modal, i18n EN/FR | incident.py:232-239,:142-144; information_update.py:20-45 FIELD_SCHEMA
- Channel created incident-YYYY-MM-DD-slug, -N on collision, dev prefix outside prod | conversations_create | incident_conversation.py:28-75
- Video call link created and bookmarked | Google Meet create_space | core.py:447-451; packages/incident/meet/adapters/google_meet.py
- Report document created from template, placeholders {{date}},{{name}},{{on-call-names}},{{team}},{{slack-channel}},{{status}} | Docs copy + replace | incident_document.py:24-51; core.py:477-599
- "Incident report" bookmark | bookmarks_add | core.py:514-519
- Row appended to incident list sheet (Date, Name=HYPERLINK doc, Product, Status, Channel=HYPERLINK) | Sheets append Sheet1!A:A | incident_folder.py:270-299
- Record created | DynamoDB put_item via models/incidents.py | db_operations.py:53-100
- On-call users invited from Opsgenie schedule in folder appProperties.genie_schedule | opsgenie.get_on_call_users + users_lookupByEmail | core.py:540-542; on_call.py:12-41
- Security group invited when security=yes (prod only) | usergroups_users_list + conversation_invite | core.py:545-554
- Notify management group invited when product=Notify and SLACK_NOTIFY_MGMT_USER_GROUP_ID set | same | core.py:557-570
- Canvas created in channel with template text | conversations_canvases_create | core.py:454-460 (NOT in INVENTORY.md)
- Source-alert bookmark when declared from an alert | bookmarks_add | core.py:525-530 (NOT in INVENTORY.md)
2 RECORD AND STATUS
- Status lifecycle Open -> In Progress -> Ready to be Reviewed -> Reviewed -> Closed | VALID_STATUS | incident_helper.py:38-44; information_update.py:35-43
- Status update fans out: doc text replace, sheet column D, DynamoDB field, channel message | incident_status.update_status | incident_status.py:11-82 | TASK-73: modal path passes raw channel name, sheet miss silent
3 CHANNEL LIFECYCLE
- Channel purpose "Incident: {name} / {product}" + "IC: @u / OL: @u" footer, 250 chars | conversations_setPurpose | incident_roles.py:34-54 | core.py reconstructs metadata from topic
- Stale channels (no update 14 days, pattern ^incident-\d{4}-) nudged daily 16:00 with archive / schedule-retro / ignore buttons, bilingual | Tier-2 job | jobs/scheduled_tasks.py:108-109; notify_stale_incident_channels.py:10-50
- Archive channel action | archive_channel | incident_helper.py:160
- floppy_disk reaction_added captures message (ts, link, author, forwarded, images, mentions) into the doc timeline section, sorted chronologically; reaction_removed deletes it | Docs fetch + edit | incident_conversation.py:263-389 (NOT in help text)
- Recreate missing resources (bookmarks, sheet row, record) | not public | incident_helper.py:743; core.py:323-430
4 INFORMATION DISPLAY/UPDATE
- Show modal: id, name, report link, meet link, severity, status, created, detection, start impact, end impact, retro link; Slack <!date> formatting | reads DynamoDB | information_display.py:34-183
- Editable: detection_time, start_impact_time, end_impact_time (datetime pickers), status, severity (dropdowns), retrospective_url (text); update writes DynamoDB + doc + sheet(status) + channel message; refreshes modal | information_update.py:59-331 | TASK-73
- /sre incident updates registered but view deferred; incident_updates field unused | incident_helper.py:408
5 ROLES
- IC and OL roles chosen by user_select; stored in the DOC's Drive appProperties (ic_id, ol_id) and in channel purpose; change posts messages | incident_roles.py:13-145 | doc found by channel name via incident_drive.find_document_by_channel_name
6 DOCUMENTS AND FOLDERS
- Status text inside doc replaced case-insensitively | incident_document.py:54-78
- Folder (product) metadata add/view/delete: genie_schedule, ic/ol names, custom keys | Drive appProperties | incident_folder.py:111-268
- Product list for the declare modal loaded from the SRE Drive folder tree | list_folder_files | incident_folder.py:53-58 | TASK-81 LEGACY_FOLDER_DISPLAY_LIMIT=500
- Sheet read: uniqueness check before append; rows read for display/retro | get_incidents_from_sheet | incident_folder.py:387-430
7 RETRO
- Modal: days offset 1-60, attendees multi-select from channel members; emails from Slack profiles | schedule_retro.py:26-99 | TASK-83.9/83.10 move to people
- Freebusy over 60-day window, 1-3 PM Eastern, first free 30-min slot, unavailable users listed | google_calendar.get_freebusy | schedule_retro.py:26-61,:314-346
- Calendar event with Meet, invites, description, reminders | insert_event | schedule_retro.py:313-346 | TASK-86 drops description/reminders/requestId; TASK-87 replay safety
- Channel message with event link, date, time, attendees | chat_postMessage | schedule_retro.py:307
8 ALERTS
- Alert message "call-incident" button opens the declare modal with source metadata | incident_alert.py:26-37
- "ignore-incident" button acknowledges, increments webhook ack counter, rewrites message | webhooks.increment_acknowledged_count | incident_alert.py:39-71
9 ON-CALL
- Opsgenie schedule -> emails -> Slack users; empty when no schedule metadata | on_call.py:12-41
10 METRICS
- No dedicated surface: the Google Sheet is the metrics view (manual pivots); /sre incident list active|stale (active not implemented) | incident_folder.py:387-430; db_operations.py
11 LOCALIZATION
- EN/FR via python-i18n, incident_change_locale toggles en-US/fr-FR | incident.py:30-32,:83-101
12 DRAFT / SUMMARIZE
- /sre incident draft [--limit]: transcript -> per-section model answers -> new doc from template -> link | packages/incident_draft
- /sre incident summarize [--since] [--limit]: transcript -> catch-up summary posted | packages/incident_summary

## B. Record today (models/incidents.py, DynamoDB incidents table)
id (uuid str), channel_id, channel_name, name, user_id, teams list[str], report_url (docs URL), status ("Open" default), created_at (unix str), start_impact_time/end_impact_time/detection_time (ts str or "Unknown"), environment (prod|dev), logs list (list_append), meet_url, incident_commander, operations_lead (Slack user ids), severity, retrospective_url, incident_updates list.
Sheet columns: A Date | B Name (HYPERLINK doc) | C Product | D Status | E Channel (HYPERLINK Slack).

## C. Coupling (modules/incident imports)
integrations.slack: incident.py:14, incident_alert.py:4, incident_conversation.py:12, incident_helper.py:12-20, notify_stale_incident_channels.py:4, schedule_retro.py:8
integrations.sentinel: incident.py:13, incident_alert.py:1, incident_conversation.py:11, incident_helper.py:21, notify_stale_incident_channels.py:1
infrastructure.spreadsheets: incident_folder.py:2
integrations.opsgenie: on_call.py:6
packages.incident.*: incident_roles.py:8, core.py:17-18, incident_helper.py:33, schedule_retro.py:10-17, incident_conversation.py:18, incident_document.py:9-14, information_update.py:18

## D. Hard-coded vendor URLs / ids
incident.py:238 INCIDENT_HANDBOOK_ID docs.google.com; core.py:176,:182,:481 docs.google.com/document/d/{id}/edit; incident_folder.py:216 drive.google.com/drive/u/0/folders/{id}; GOOGLE_RESOURCES env (incident_template_id, incident_list_id, incident_folder_id, sre_calendar_id, incident_handbook_id) via infrastructure/configuration/integrations/google.py

## E. Not in INVENTORY.md
canvas creation; source-alert bookmark; floppy_disk reaction handlers (registered :161-162 but undocumented in help); /sre incident updates stub; recreate-missing-resources.

AMENDMENT 2026-10-02 (human direction after the proposal): a retrospective is a meeting about an incident, and managing calendars is not incident work. The record now says calendar is consumed as a workplace capability: TASK-138 creates app/capabilities/calendar/ from packages/incident/scheduling (availability and meeting creation only; it carries the TASK-86 fix and is the adapter TASK-87.3 waits for), TASK-38.6 depends on it and owns no calendar adapter, and TASK-124.5, TASK-86, TASK-87 and doc-2 Waves 4 and 5 are updated. The retro portion is named as the place the feature gains the most value after the migration: DRAFT-8 (reschedule, modify, cancel, attendee changes, reminders, with the calendar capability's new operations landing with that consumer) and DRAFT-9 (retro action items as records with owners, due dates, completion tracking and an optional typed external-tracker reference; today they are tables at the end of the report with no record of completion). AC #5 and #6 evidence still holds: TASK-138 sits in Wave 4 before TASK-38.6; the subdomain list and core/ contents are unchanged.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @claude
created: 2026-09-16 14:37
---
2026-09-16 (human decision on sequencing): TASK-38 now runs AHEAD of this decision, not the other way round. The de-vendorized core it produces (AC#13: the incident, its status lifecycle, its participants and its artifact references as vendor-agnostic frozen dataclasses) is worth finishing on its own merits and is a direct input here - comparing an app-owned design against an external IR platform is concrete once those concepts exist as types, and speculative before. Hence the dependency on TASK-38.

What can still start immediately, in parallel with TASK-38: the DFIR-IRIS evaluation (API surface, auth, hosting, licence, data residency, operational cost, reachability from the deployment), and the inventory of user-visible capabilities separated from their current implementation. Those are research, not design, and neither waits.

What must NOT start before this decision lands: any new persistence design for incident - a storage schema, a migration off the incident sheet, a richer app-owned domain beyond what TASK-38 needs to de-vendorize what already exists. If an external platform ends up owning the case, that work shrinks to a thin coordination record.
---

created: 2026-09-24 20:05
---
2026-09-24: dependency on TASK-38 removed and inverted. TASK-38 is now the by-surface rebuild and depends on this decision (decisions/migration.md: vendor concepts leave the feature on the way, which needs the system-of-record answer first). The relocation of the shipped incident packages is TASK-124.5 and is independent of this decision. The dead record decisions/layers.md cited in the description is replaced by decisions/plugin-architecture.md; workplace capabilities live in app/capabilities/.
---

created: 2026-10-02 16:13
---
2026-10-02 (human direction for the decision session; narrows the question above):
- The outcome is the desired end state for the incident feature, consistent with the decisions already recorded (workplace-systems.md, feature-packages.md, plugin-architecture.md, outbound-clients.md, migration.md). Those records are not reopened.
- DFIR-IRIS, and any other external incident or case-management platform, is OPTIONAL. The feature must work in full with no external platform. The design keeps a place where one can be attached later, as a feature-owned adapter under decisions/outbound-clients.md, without reworking the incident record, its store or the subdomains.
- The choice is therefore no longer "which of A, B or C" today: it is Option A now, while the code base is solidified and standardized, designed so that a later B-shaped state (an external platform owning case content) stays reachable. Running another platform in parallel carries an operating cost that may not justify the gains it would bring.
- The feature continues as is through the migration: current behaviour is preserved while doc-2's delivery sequence runs. Expanding the feature comes after doc-2 is finished. The packet separates the two parts.
---

created: 2026-10-02 16:25
---
2026-10-02 (proposal on AC #2, for the human to decide; the AC is not reworded): AC #2 is conditional on an external IR platform being chosen. Under the 2026-10-02 direction no platform is chosen, so read literally the criterion is vacuous. Proposed reading: the optional external-platform integration point is specified from sourced evidence gathered from current documentation (API surface, auth, hosting, licence, data residency, operational cost) rather than recall, and is scoped as a feature-owned adapter under decisions/outbound-clients.md, never an infrastructure capability; no platform is adopted. The DFIR-IRIS evidence gathered this session is recorded in the decision record under that reading.
---
<!-- COMMENTS:END -->
