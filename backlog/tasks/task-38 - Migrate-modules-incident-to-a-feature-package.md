---
id: TASK-38
title: Migrate modules/incident to a feature package
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-16 14:38'
labels:
  - migration
  - phase-5
milestone: m-5
dependencies:
  - TASK-36
  - TASK-37
  - TASK-27.2
references:
  - decisions/migration.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1292'
  - decisions/workplace-systems.md
  - decisions/people-and-accounts.md
priority: medium
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second strangler target (largest user surface; 51 files, plus the incident_helper legacy-list entry). Same recipe as task-37; the webhooks migration (task-37) establishes the pattern to copy.

SEQUENCING (human, 2026-09-03): this task runs AFTER the TASK-25* vendor-integration cleanup. Its exact position in the queue is decided once that cleanup is done, so treat the m-5 milestone and the TASK-36/TASK-37 dependencies as necessary-but-not-sufficient.

STRUCTURE DECIDED (2026-09-03, decisions/feature-packages.md "Complex features: an umbrella directory, never a flat prefix"). incident is genuinely complex (app/modules/incident is 4636 LOC across 17 modules), so it is an umbrella, not a single flat package and not a family of flat incident_* packages:

  app/packages/incident/
  |-- __init__.py   EMPTY (0 bytes) - namespace only, no hookimpls, no entry-point line
  |-- common/       shared kernel: incident domain vocabulary + IncidentSettings tree, no I/O
  \-- <subdomain>/  each shaped like the feature-packages layout table; each is a plugin

Entry-point names carry the dotted prefix ("incident.draft" = "packages.incident.draft", never "draft") because entry-point names are a flat per-group registry.

Candidate subdomain split (to be confirmed during planning, not settled here): declare/ (core.py + incident.py), channel/ (incident_conversation, incident_status, information_display, information_update, incident_roles), documents/ (incident_document, incident_folder), retro/ (schedule_retro), alerts/ (incident_alert, notify_stale_incident_channels), plus draft/ summary/ relocated in and the already-correct scheduling/. db_operations.py and utils.py land in common/.

RECONCILIATION OWED BY THIS TASK. decisions/migration.md rule 5's open shape/naming question is now closed, which makes two shipped packages named deviations this task must relocate:
- packages/incident_draft  -> packages/incident/draft
- packages/incident_summary -> packages/incident/summary
These are import-path + entry-point-name changes with no runtime surface change. Sequence the incident_draft move AFTER TASK-25.1.6.6, which rewrites the same 1704-line test file's patch targets - otherwise those strings get rewritten twice. Note that a rename is NOT sufficient on its own: unittest.mock patch string literals fail at patch time rather than import time, so every "packages.incident_draft..." / "packages.incident_summary..." patch target must be swept too (TASK-25.1.6.2 hit exactly this).

ALREADY CORRECT, NOT THIS TASK'S WORK: app/packages/incident/scheduling/ is created directly in its umbrella position by TASK-25.1.6.2 (redirected 2026-09-03), which also creates the empty app/packages/incident/__init__.py. This task inherits that umbrella rather than creating it, and must not regress it.

Settings consolidation onto a common/settings.py IncidentSettings tree (ACCESS-style, INCIDENT_{SUB}_{FIELD}) renames INCIDENT_SUMMARY__* and incident_draft's aliased env vars. That touches terraform/SSM, so it is deployment-coordinated and belongs in this task's series, not in a layout-only PR.

Steps:
1. Confirm smoke coverage of every incident command/action (task-36 inventory).
2. Fill out app/packages/incident/ as an umbrella per decisions/feature-packages.md (copy the access/ shape); confirm the subdomain split before writing code.
3. Slack handlers via register_slack_commands hookspec; parsing via the shared parser; rendering via the shared renderer; locales/ EN+FR per decisions/i18n.md (parity gate from task-21 applies).
4. Relocate incident_draft and incident_summary into the umbrella, repoint their entry-point names to the dotted form, and sweep mock patch string literals.
5. Consolidate settings onto common/settings.py; coordinate the env-var rename with terraform/SSM.
6. Cut over, delete app/modules/incident/, smoke green pre/post, command names unchanged.
7. Add "packages.incident" as a container on TASK-18's contract (e) with exhaustive = true, and land it green as the final step.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/incident/ matches the layout; handlers pass the five-step review
- [ ] #2 Smoke tests pass pre and post cutover; command names and responses unchanged
- [ ] #3 app/modules/incident/ deleted; legacy list entry removed; baselines never grew
- [ ] #4 EN/FR catalogues complete (parity check green)
- [ ] #5 app/packages/incident/__init__.py is empty (no hookimpls, no re-exports, no entry-point line); every subdomain declares its own entry point under the dotted name incident.<subdomain>
- [ ] #6 Shared incident vocabulary lives in packages/incident/common/ with no I/O and at least two subdomain consumers per item; no subdomain imports another subdomain
- [ ] #7 TASK-18 contract (e) gains a packages.incident container with exhaustive = true and lint-imports is green
- [ ] #8 packages/incident_draft and packages/incident_summary no longer exist; their code, tests and locales live under packages/incident/ and no packages/incident_* directory remains anywhere under app/packages/
- [ ] #9 The packages/incident/{documents,drive,meet,scheduling} Google adapters return frozen domain dataclasses instead of dicts once their modules/incident callers move into the package (decisions/sdk-typing.md item 3; handed off by TASK-25.1.6 AC#3)
- [ ] #10 No module under packages/incident/ imports a vendor SDK or an app/integrations client outside its own adapters/ directory; whichever external systems the redesign turns out to use, each is reached through a feature-owned adapter, enforced by the lint-imports contract from AC#7 plus review
- [ ] #11 No workplace concern gains a new app/infrastructure/<service>/ Protocol (decisions/workplace-systems.md rule 1); where the redesigned feature uses a workplace system there is one adapter per system behind a feature-owned port whose surface is only what the feature actually does, and which system applies is data - the artifact's stored reference, the conversation's platform, the person's linked account - never a global provider setting (rule 3)
- [ ] #12 Incident owns a partitioned settings module naming its own resources per decisions/configuration.md; no incident setting is read from a root aggregator and no vendor-specific resource configuration (for example get_google_resources_config) is read outside an adapter
- [ ] #13 The core incident concepts (the incident itself, its status lifecycle, its participants and its artifact references) are expressed as vendor-agnostic frozen dataclasses in packages/incident; no raw vendor payload, SDK type or DynamoDB AttributeValue shape crosses out of an adapter into domain or application code, so a later change of backend or workplace suite touches adapters only
- [ ] #14 Relocation stays behaviour-preserving and introduces no new persistence design: the record of truth is left where it is, and deciding where it should live is owned by TASK-97
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke suite green post-cutover
- [ ] #2 PR series references decisions/migration.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-03 16:15
---
SCOPE UPDATE (2026-09-03): description rewritten and 4 ACs added following the umbrella-vs-flat architecture review. decisions/feature-packages.md now carries the umbrella rule and decisions/migration.md rule 5 was amended to point rule-5 relocations at their final umbrella position; this task inherits the resulting reconciliation debt (relocating incident_draft / incident_summary / incident_scheduling). Original AC #1-#4 untouched.

SIZE WARNING for whoever plans this: this task was already the largest strangler target (4636 production LOC, 17 modules) and now also owns three package relocations plus a deployment-coordinated env-var rename. It will not survive the single-PR size gate. Expect decomposition into at least: (i) umbrella skeleton + relocate the three incident_* packages, (ii) one slice per subdomain built + cut over, (iii) settings-tree consolidation with the terraform/SSM change, (iv) modules/incident deletion + the TASK-18 container line. Do that breakdown before any code.

IMMEDIATE, FREE ACTION OUTSIDE THIS TASK: TASK-25.1.6.2 is in flight on branch feat/incident_retro_helpers_relocation with its tests written but app/packages/incident_scheduling/ not yet created (only app/tests/{unit,integration}/packages/incident_scheduling/ exist). Creating it directly as app/packages/incident/scheduling/ costs one directory name today versus a rename PR later. Flagged on TASK-25.1.6.2.

OPEN QUESTION for the human: whether the three relocations should be split out of this task into their own near-term task rather than waiting for m-5. They are independent of TASK-36/TASK-37 (this task's dependencies), they are pure import-path changes, and every week they stay flat is another week of new code keyed to the wrong paths. The one real cost is the incident_draft test file (1704 lines, 135 mock references), which argues for sequencing after TASK-25.1.6.6. Not created unilaterally - say the word and I will.

CANDIDATE SUBDOMAIN SPLIT is a proposal only. The mapping in the description came from module sizes and names, not from reading the call graph. Validate it against actual cohesion during planning; incident_conversation.py (464) and core.py (601) in particular may not fall where the names suggest.
---

created: 2026-09-03 16:29
---
SCOPE CORRECTION (2026-09-03): TASK-25.1.6.2 was redirected to create app/packages/incident/scheduling/ directly, so incident_scheduling is no longer a relocation this task owns - it also creates the empty umbrella app/packages/incident/__init__.py that this task inherits. AC#6 replaced accordingly (now covers incident_draft and incident_summary only, plus a no-packages/incident_*-anywhere sweep). Description updated with the human sequencing decision: this task runs after the TASK-25* vendor-integration cleanup, exact position TBD once that is done. Also recorded the mock-patch-string-literal hazard: renaming directories alone is insufficient because patch targets are strings that fail at patch time, not import time - TASK-25.1.6.2 hit this with 10 patch targets.
---

created: 2026-09-10 15:45
---
ARCHITECTURE CONSTRAINT ADDED 2026-09-10 (human-directed). Do not introduce new infrastructure services for workplace concerns: calendar, documents, files, directory, mail, notifications, people or identity. That means no new app/infrastructure/<service>/ package, Protocol or factory.

Why: the organization will run Google Workspace with Slack and Microsoft 365 with Teams side by side for the long term. Three Draft decision records describe the direction:
- decisions/workplace-systems.md
- decisions/capability-packages.md
- decisions/people-and-accounts.md

Until those are accepted:
- keep vendor behavior in feature Path B adapters (app/packages/<feature>/adapters/);
- the existing infrastructure/directory, drive and spreadsheets providers stay usable, including changes needed to finish migrating their current consumers;
- do not create capability packages yet.

Incident scheduling, documents, Drive, Meet and Sheets needs stay in incident Path B adapters during this migration. Moving incident records into storage, and recording each incident's origin as (platform, tenant, channel_id), are expected follow-ups under the Draft records. Do not add infrastructure services for them.
---

author: @claude
created: 2026-09-16 13:47
---
2026-09-16 review of TASK-25.2.5: TASK-27 added as a dependency. The incident persistence this task absorbs (modules/incident/db_operations.py, incident_folder.store_update) uses DynamoDB scan with FilterExpression, an update of a single field, and a list_append on the logs attribute. The StorageService Protocol has no scan, no update and no list-append equivalent, so this task cannot move incident onto the storage capability until TASK-27 defines those in capability terms. Until then the callers stay on the provisional packages/aws_platform DynamoDB adapter that TASK-25.2.5 builds.
---

author: @claude
created: 2026-09-16 14:00
---
2026-09-16 (human direction, recorded during the TASK-25.2.5 review): this task must break incident's tight coupling to specific vendor SDKs, not just relocate it. The rule: a business feature makes no direct call to a vendor SDK client unless interfacing with that vendor IS the feature's purpose - managing AWS resources, or writing a Google Docs document. Everything else it needs (storage, queue, idempotency, identity) goes through a capability Protocol.

Incident today fails that on one axis and already passes on another.

PASSES. packages/incident/{documents,drive,meet,scheduling}/adapters/google_{docs,drive,meet,calendar}.py already exist. Creating and editing the incident report document, its Drive folder, its Meet link and its retro calendar event ARE the feature's purpose, so a Google-specific Path B adapter is the correct end state (decisions/workplace-systems.md rule 2, decisions/layers.md Path B). AC#9 already asks those adapters to return frozen domain dataclasses. Nothing to undo.

FAILS. Google Sheets is being used as the incident database. modules/incident/incident_folder.py:283 append_values, :317 read_values, :341 update_values and :379 read_cells treat INCIDENT_LIST as the incident list, through infrastructure/spreadsheets - a workplace system sitting in the infrastructure tier and being read back as a source of truth. decisions/workplace-systems.md rule 5 allows a spreadsheet to be a collaboration space the app holds a reference to, or a projection the app writes and never reads back; this is neither. Its Migration section already names this work: move incident records into storage, and move the consumers of infrastructure/{directory,drive,spreadsheets} onto capability packages or feature adapters. New AC#11 and AC#12 pin it.

ALSO. modules/incident imports integrations.slack (users, channels) and integrations.sentinel directly in six files. Slack is a transport (decisions/platform-transports.md) and Sentinel is observability; neither is the incident feature's purpose, so neither belongs in feature code as a direct integrations import. New AC#10 covers this through the lint-imports contract.

TWO CONSEQUENCES FOR PLANNING.
1. Dependency: decisions/workplace-systems.md is still status Draft, applies target. These ACs assert its rules, so either it is accepted first, or this task's plan records that it is implementing a draft record and which rules it commits to.
2. Size: the Sheets-to-storage record move is a data migration with its own backfill and cutover, and is a separate slice from the package relocation - workplace-systems.md Migration already lists it as its own ticket. Expect this task to decompose with that slice standing alone, and note it also needs TASK-27.2's storage operations, which is why the dependency was retargeted there.
---

author: @claude
created: 2026-09-16 14:05
---
2026-09-16 (human correction to the review comment above): the Google adapters are NOT the end state on their own. The intent is that incident works across workplace platforms - the report document, its folder, the meeting link and the retro event must support more than one provider, so an organization running Microsoft 365 is not locked out. The earlier comment framed Google-specific Path B adapters as correct-and-finished for those four concerns; that is wrong, and AC#14-#16 correct it.

WHAT THAT DOES AND DOES NOT MEAN, against decisions/workplace-systems.md (Draft, applies target).
- It does NOT mean a vendor-neutral infrastructure Protocol. Rule 1 bars a new app/infrastructure/<service>/ contract for documents, files, calendar or mail, on the lowest-common-denominator argument and because routing is organization policy that infrastructure must not hold.
- It does NOT mean a configuration switch selecting the provider. Rule 3: configuration names each workplace tenant the instance works with, and never selects the provider for a workplace concern. Both suites can be live at once - that is the record's premise, Google Workspace with Slack beside Microsoft 365 with Teams.
- It DOES mean a feature-owned port inside packages/incident with one adapter per system, and selection driven by data: the artifact's stored reference for an existing incident, and a decided rule (conversation platform, declarer's linked account, or org policy) for a new one. That is rule 2 plus the data-not-configuration clause.

CONCRETE DEFECTS THIS HAS TO CLEAR
- modules/incident/incident_document.py imports packages.incident.documents.adapters.google_docs and packages.incident.drive.adapters.google_drive directly as module-level functions; there is no port, so there is nowhere for a second implementation to attach.
- modules/incident/core.py:176, :182 and :481 build https://docs.google.com/document/d/{document_id}/edit from a bare id. Rule 4 requires the stored reference to carry its system and tenant, and the human link to come from the adapter that owns that system.
- INCIDENT_TEMPLATE comes from get_google_resources_config() at feature import time; a template is per-system and belongs behind the adapter.
- modules/incident/incident_conversation.py:238-245 parses a Google Docs document id out of a bookmark link.

OPEN DESIGN QUESTION FOR THIS TASK'S PLAN (not blocking the package relocation, blocking the multi-provider work): what selects the system for a brand-new incident. The conversation platform is available immediately; the declarer's linked account needs TASK-83; an explicit org-policy setting is the simplest and is compatible with rule 3 as long as it is policy for THIS feature and not a global provider switch. Decide it before building the second adapter, not after.
---

author: @claude
created: 2026-09-16 14:13
---
2026-09-16 (human clarification, supersedes the structural assumptions in the two comments above): incident, like every business feature, will be redesigned from the ground up. No existing logic is assumed to survive. A report document may or may not exist. A meeting link may or may not exist, and which tool provides it is unknown and not interesting yet. A list of incidents and their statuses almost certainly exists, but it is tracked as app-level database records - definitely not a spreadsheet. The app itself runs on hosting infrastructure that is AWS today and could be Azure, GCP or on-prem later, and each business feature owns its own settings and its own resources.

WHAT THIS CHANGES ON THIS TASK. The acceptance criteria added earlier named specific artifacts (report document, folder, meeting, scheduling ports; an activity log data model; specific incident_folder.py call sites) and so prejudged the design. They are removed and replaced by AC#11-#17, which are constraints on whatever design emerges rather than a description of it:
- AC#11 makes the end-state shape an explicit output of a recorded design step, with nothing carried over by default.
- AC#12 no vendor SDK or integrations client outside a feature-owned adapter, whatever the systems turn out to be.
- AC#13 no record of truth in a workplace document or spreadsheet, and no consumer of the three workplace providers currently misplaced in infrastructure/.
- AC#14 no new infrastructure Protocol for a workplace concern; adapter per system behind a feature-owned port; system selection is data, not a global setting.
- AC#15 hosting services only through capability Protocols, so a move off AWS touches no incident code.
- AC#16 partitioned incident settings; no vendor resource configuration outside an adapter.
- AC#17 no read-modify-write and no vendor list-append for persisted state.
AC#10 (stored artifact references carry system and tenant, no bare vendor id, no hand-built vendor URL) is kept because it holds for any artifact the design chooses to keep.

TENSION TO RESOLVE BEFORE PLANNING. This task is still titled and scoped as a strangler relocation - same recipe as TASK-37, with AC#1 asserting a layout and AC#2 asserting that command names and responses are unchanged pre and post cutover. A ground-up redesign is a different piece of work with a different risk profile, and the two cannot share one set of acceptance criteria: a redesign that keeps every command name and response is not a redesign. Recommendation, for a human decision: keep TASK-38 as the behaviour-preserving relocation that gets incident out of modules/ and under the import contracts, and open a separate architecture task (feature-architecture packet, likely amending or adding a decisions record) that owns the redesign and carries AC#11-#17. Alternatively retitle and re-scope TASK-38 itself as the redesign and let the relocation become its first slice. Not decided here.
---

author: @claude
created: 2026-09-16 14:25
---
2026-09-16 (human decision): TASK-38 stays the strangler relocation, and the redesign moves to TASK-97 (incident management architecture: system of record, coordination boundary, and whether to back it with an external IR platform such as DFIR-IRIS). Pure relocation was judged too little value on its own, so this task's floor is raised: relocate AND de-vendorize the core concepts. That is AC#13 - the incident, its status lifecycle, its participants and its artifact references become vendor-agnostic frozen dataclasses, with every raw vendor payload, SDK type and AttributeValue shape stopped at an adapter boundary. That work keeps its value under every option TASK-97 might choose, including one where an external platform becomes the system of record and the bot keeps only workplace coordination.

MOVED TO TASK-97 (they describe the redesigned feature, not the relocation): records of truth out of documents and spreadsheets; stored artifact references carrying system and tenant; hosting services reached only through capability Protocols; no read-modify-write or vendor list-append for persisted state; and the design step that decides which artifacts exist at all.

KEPT HERE because they cost nothing extra during a relocation and constrain it correctly: no vendor SDK or integrations client outside a feature-owned adapter (AC#10), no new infrastructure Protocol for a workplace concern (AC#11), partitioned incident settings (AC#12), and the explicit statement that no new persistence design is introduced here (AC#14).

SEQUENCING NOTE. TASK-97 is a decision, not an implementation, and it is worth making before this relocation finishes rather than after: if an external platform ends up owning the case, an app-owned incident domain model and its storage migration shrink to a thin coordination record. Nothing in this task blocks on it, but anything here that starts to look like new persistence design should stop and wait for it.
---

author: @claude
created: 2026-09-16 14:38
---
2026-09-16 (human decision, corrects the sequencing note in the comment above): this task runs AHEAD of TASK-97 and is not gated on it. The de-vendorization in AC#13 is worth finishing on its own merits, and it makes TASK-97's comparison concrete rather than speculative, so TASK-97 now depends on this task. The earlier note that TASK-97 should be decided before this relocation finishes is withdrawn.

What still holds from that note: no NEW persistence design starts here. AC#14 already says so. De-vendorizing the concepts that already exist is in scope; inventing a storage schema, migrating off the incident sheet, or growing an app-owned domain beyond what today's behaviour needs is not, and waits for TASK-97.

TASK-80 was archived on 2026-09-16 as superseded by decisions/workplace-systems.md rule 1. Its replacement expectation - a capability package with one adapter per system if document I/O is ever needed by more than one feature, never an infrastructure Protocol - is recorded on the archived task and is consistent with AC#10 and AC#11 here.
---
<!-- COMMENTS:END -->
