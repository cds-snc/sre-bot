---
status: Accepted
date: 2026-10-09
applies: target
scope: What the SRE bot owns and what it coordinates for incident management, where the incident record of truth lives, the vocabulary and the subdomains of the incident feature umbrella, and the optional seam for an external case-management platform.
---

# Incident Management

## Context

`app/modules/incident/` (about 4,700 lines, 17 modules) is the largest legacy surface and is built around Google Workspace resources rather than around the incident. The channel name is the key: every command resolves its incident through the Slack channel, and an archived channel cannot be edited, so status and report updates break once a channel is archived. The incident list is a Google Sheet that is appended at declare time, read back for uniqueness checks and listings, and updated on status change (TASK-73 shows a status update that silently never reaches it). The IC and OL roles live in the report document's Drive properties. The DynamoDB item (`models/incidents.py`) stores bare vendor ids and a `report_url` string, is updated by `list_append` for its activity log, and is reached through the provisional `packages/aws_platform` adapter. Retro events drop fields on the way to the Calendar adapter (TASK-86), and several Google writes are replayed by SDK retries (TASK-87).

What users depend on, inventoried on 2026-10-02 (TASK-97): the declare modal and the resources it creates (channel, report from a template, video call, bookmarks, canvas, list row, record, on-call and group invites), a five-step status lifecycle fanned out to the document, the list, the record and the channel, the show and update modals, the IC and OL roles, floppy-disk reactions that capture messages into the report's timeline, daily stale-channel nudges with archive and schedule buttons, retro scheduling with an availability search, the alert buttons under alerts that product infrastructure and the SIEM post into alert channels through the webhooks pipeline, EN and FR, and the `draft`, `summarize` and `status-update` commands.

The shipped new code sits in `features/incident/`: `core/` (record lookup over the legacy table, transcript reader, security reader, the `StatusUpdate` record and its interim DynamoDB store), `comms/` (status updates, TASK-140 to TASK-144, carved out of `scribe` by TASK-145.4), `scribe/` (draft and summarize, TASK-135) and the adapter-only siblings `documents/`, `drive/`, `meet/` and `scheduling/`. `scribe` grouped the use cases that call the model: a subdomain named for a mechanism, which the 2026-10-09 direction below undoes.

Three options were weighed on 2026-10-02: the bot owns incident management (A); an external incident-response platform owns the case and the bot coordinates around it (B); a split with a thin coordination record (C). DFIR-IRIS was the candidate platform: LGPL-3.0 with an AGPL v3 frontend, self-hosted and **requiring PostgreSQL**, a REST API moving from v1 to v2 to v3, user-bound API keys, an English-only UI, a 2023 roadmap pause and no support policy ([docs.dfir-iris.org](https://docs.dfir-iris.org/latest/operations/api/), [roadmap](https://docs.dfir-iris.org/roadmap/)). There is no live open-source comparator for an SRE incident process: TheHive's repository was archived on 2025-12-05 and Netflix Dispatch on 2025-09-03 ([Dispatch](https://github.com/Netflix/dispatch)); Dispatch's module list is the reference used for the expansions below.

Organisation constraints: Government of Canada (EN and FR, WCAG 2.1 AA, Canadian residency), self-hosted open source over SaaS, Slack today and Teams later, and introducing PostgreSQL is a gated infrastructure decision of its own. The GC Notify team is a consumer of this feature. Human direction, 2026-10-01 to 2026-10-09 (TASK-97, TASK-144, TASK-145): the incident is the anchor, not the channel; resources are flexible by kind and by system; an external platform is optional; subdomains follow the phases and audiences of the incident process; the behaviour other teams depend on is preserved while the rebuild runs.

## Decision

**Option A: the bot owns incident management.** The system of record is the **incident record in app storage**, written and read through the storage contract ([plugin-architecture.md](plugin-architecture.md), [cloud-portability.md](cloud-portability.md)). The bot **coordinates** everything that lives in a workplace or external system: the conversation, the report, the video call, the postmortem meeting, on-call and notifications, and optionally an external case. None of those is a record of truth ([workplace-systems.md](workplace-systems.md) rule 5). The incident list sheet survives, if at all, as a write-only projection rebuilt from storage. An external platform is not adopted; the seam for one is kept so a later B-shaped state is reachable without reworking the record, its store or the subdomains.

### Vocabulary

The feature uses the organisation's incident words, and code, catalogues and records use them the same way. **Incident**: an event that disrupts or degrades a service and needs a timely response; a **security incident** also touches confidentiality, integrity or availability and carries the security flag. **Record**: the incident in app storage. **Conversation**: the chat channel, a resource of the incident. **Report**: the incident document, from the postmortem template. **Stage of the process**: detect, respond and assess, recover, learn, improve. **Status**: the five internal values `Open`, `In Progress`, `Ready to be Reviewed`, `Reviewed`, `Closed`. **Severity**: a closed set, levels 0 to 4 (0 is an event spanning several products), or unset. The set is wide on purpose: teams use different scales today (handbook 0 to 3, runbook 1 to 3, the legacy bot 1 to 4), so each team picks the levels it uses; it narrows only if the organisation standardises. The legacy values `sev-1` to `sev-4` map one to one and `none` to unset. **Roles**: incident commander (IC), operations lead (OL), communications lead (CL), policy lead (PL), postmortem owner (PO). **Status update**: the message about the incident for an audience outside the response; its **stage** (Investigating, Identified, Monitoring, Resolved) is a public vocabulary distinct from the status. **Timeline entry**: a message captured into the report. **Audience**: who a communication is for: the service's users, internal staff, senior management. **Postmortem**: the blameless review, its meeting and its report; user-facing labels may still say "retro". **Action item**: a mitigation agreed at the postmortem. Three different things are called "status" in conversation; code never is: `IncidentStatus`, `Severity` and `StatusUpdateStage` are distinct types in `common/`.

### The incident record

The record is keyed by an **app-generated, opaque incident id**; the conversation is a resource, never the key. The legacy table's UUID is that id, so existing records survive the move to the store. The record holds the title, the product, the severity, the security flag and the declarer; the status; the timing fields declared, detection, impact start and impact end, from which time to detect and time to recover derive; the five roles as person references (an email or platform account today; a person id with [people-and-accounts.md](people-and-accounts.md), TASK-83); and **typed references** to its resources, each a frozen dataclass carrying the **system, the tenant and the vendor id** plus the vendor-provided link (never built by formatting a URL): conversation, report, video call, postmortem meeting, external case and source alert. Timeline entries and status updates are **their own records under the incident**, never a list attribute, so nothing is written with a read-modify-write or a vendor list-append.

### The feature umbrella

`features/incident/` follows [feature-packages.md](feature-packages.md): subdomains above `core/` above `common/`, imports one way, `core/` reached only through `core/api.py`. **Subdomains are the stages and audiences of the incident process, named in the domain's words. Capabilities are the mechanisms they use; a subdomain is never named for a mechanism.** The test for where a surface goes: who is it for, and when in the incident does it happen? One command joins the subdomain whose users need it at that point.

| Subdomain | Entry point | For whom, when | Holds |
| --- | --- | --- | --- |
| `response/` | `incident.response` | responders, while the incident is open | declare, status, severity, roles, show and update, archive, recreate resources, timeline capture, canvas, the alert buttons, the stale-channel nudge job, `summarize` (a responder catching up) |
| `comms/` | `incident.comms` | audiences outside the response | status updates: form, optional AI fill, approval, copy-ready text, history, published toggle; one profile per audience; `StatusPagePublisher` and its adapters |
| `postmortem/` | `incident.postmortem` | the postmortem owner and the reviewers, after recovery | the meeting over the calendar capability, `draft` (fill the report for review); later action items and feedback |

**`core/` owns** the record, its domain types and its **store** (`IncidentStore` over the storage contract with an in-memory fake; `StatusUpdateStore` appending each update as its own record with a conditional put); the **shared command check in two parts** (`find_incident_for_conversation` for every command, `conversation_is_writable` only before a write to the conversation, so an archived channel never blocks a record update); the **resource interfaces with two or more consumers**, each with one adapter per system in `core/adapters/` selected by the stored reference, never by a setting: `IncidentConversation` (post, purpose, bookmark, invite, archive, writability; Slack), `IncidentReport` (create from template, placeholders, status text, timeline entry, read sections, write a filled draft copy, link; one Google Docs adapter absorbing `documents/`, `drive/` and scribe's section writer), `IncidentTranscriptReader` (takes the conversation reference), `ProductCatalog` (products, metadata, on-call schedule reference; Drive folders during the migration, app records afterwards), `ExternalCaseRecorder` (the seam below); and the templates and per-system configuration those adapters read at call time. **`common/`** holds the settings tree and the vocabulary with two or more consumers and no I/O: `IncidentStatus`, `Severity`, the role names, `StatusUpdateStage`, and the action ids one subdomain renders and another handles (the nudge's schedule button is registered by `postmortem/` and rendered by `response/`). No subdomain imports another (rule 3); a transition one subdomain raises and another reacts to (the report draft offered at `Ready to be Reviewed`) goes through an extension point declared in `common/`.

Text generation is a capability (TASK-25.10, TASK-134): `response`, `comms` and `postmortem` supply the transcript, the prompt and the post-processing and never a vendor import. Who is on call is the on-call capability ([oncall.md](oncall.md)), consumed at declare. Detection is outside the bot except for the call-incident and ignore buttons that the webhooks capability renders under alerts.

### Communications

A status update is the message about an incident for an audience outside the response, run by `/sre incident status-update`. The first audience is the people who use the affected service, following the pattern product teams already publish (GC Notify's bilingual incident history: a dated summary, the stage with a date and time in ET or HE, what happened, who is affected, "You do not need to take any action" when true). Internal staff and senior management are further **audience profiles** over the same form, approval and history (DRAFT-13), never new subdomains.

- **Fields**: stage, affected service by its public name, user-visible impact, what we are doing (no root-cause speculation), workaround or no action needed, next update time with its date. Stages only move forward. An update follows about every 30 minutes.
- **Writing and drafting**: a responder writes the update in a form prefilled from the latest approved update (blank at the first stage). "Draft with AI" is offered only when text generation is configured; it fills the fields in EN and FR from the conversation since the latest approved update's transcript cutoff. Code decides nothing is new: with no new human messages the prior update is carried forward without a model call. For a security or unknown-flag incident the responder confirms in the form before any model call, and the service refuses without it; a hand-written draft needs no confirmation. Redrafting with instructions is the same button with instructions typed. Each record carries its origin: hand-written, model, model with instructions, carried forward.
- **Where**: in modals private to the responder, never in the conversation: the pending draft with its origin, or "New update", and the approved history; from there the form or an approved update's copy-ready text. The same modal is later reached from the central incident modal; the command stays as a direct way in.
- **Rendering and publishing**: a comms profile turns the stored fields into text (labels, public names, layout, time format, audience). One default profile ships; per-product and per-audience profiles never change the prompt. `StatusPagePublisher` publishes the text; its only adapter returns copy-ready EN and FR text that people proofread and paste by hand. A status-page adapter is DRAFT-10 and needs the communications role's agreement first.

### Postmortem

A postmortem meeting is a meeting about the incident: calendar operations are the `calendar` workplace capability (TASK-138, [workplace-systems.md](workplace-systems.md)), and `postmortem/` holds the incident side only: attendees, the stored meeting reference, the conversation posts, and `draft`, which fills the report from the conversation for the postmortem owner to edit. Action items as records with owners, due dates and reminders (DRAFT-9), meeting management (DRAFT-8) and participant feedback (DRAFT-15) are expansions.

### The incident's primary message and central modal (direction)

The bot's first post in an incident conversation becomes the incident's primary message, kept current by editing it, and its main control opens the central incident modal (today's `/sre incident show`), which gathers the incident's controls, status updates among them, and is meant to match a later Backstage view. Specific commands stay as direct ways in. An expansion after the rebuild (DRAFT-11).

### System selection and the optional external platform

For a **new** incident, the system that creates its report and video call is an incident-feature policy setting in `common/settings.py` naming one configured workplace tenant, defaulting to the only one. An existing incident's resources are reached through the system in each stored reference. **`ExternalCaseRecorder`** in `core/api.py` (open, update, add an entry, close a case) has one feature-owned adapter per system in `core/adapters/` over an `integrations/<system>/` client, never an `app/infrastructure/` package; configuration lists zero or more case-system instances; with none configured the provider returns a no-op recorder and nothing else changes, which is the shipped state. Inbound case events arrive later through the webhooks capability as re-read hints (DRAFT-3 to DRAFT-5).

### Expansions, all optional

Each waits for the people it depends on and is not scheduled. Backed by the organisation's process and needing its roles to adopt them: internal and senior-management updates (DRAFT-13), the status-page adapter (DRAFT-10), action items with reminders (DRAFT-9), a privacy flag with the policy lead notified (DRAFT-14), indicator reporting (DRAFT-1). Reference only, from other incident tools: participant roster, in-incident tasks, feedback (DRAFT-15); products as records (DRAFT-2); second-suite adapters (DRAFT-6).

### What the design rejects

- B and C now: PostgreSQL is gated, the candidate's UI is English-only and its API is moving, and a thin coordination record converges on A.
- A subdomain named for a mechanism (`scribe`, `ai`, `assist`): the model is a capability every subdomain may call. Per-command subdomains (declare, channel, documents, retro, alerts, draft, summary): one command joins the subdomain whose users need it. A nudges subdomain: its buttons belong to two subdomains. A products subdomain: declare depends on the catalog, so it is `core/`. Adapter-only siblings (`documents`, `drive`, `meet`, `scheduling`): adapters live in `core/` or a subdomain.
- Detection and triage before an incident exists (signals, cases), workflows run from the incident, auto-tagging and a web console: Dispatch had all of them and was archived; alert-to-incident is the webhooks capability's job.

## Consequences

- An incident stays editable after its channel is archived; a failed projection write is a retry or a rebuild, not lost data.
- Resource creation, link rendering and vendor behaviour are written once per system in `core/adapters/`; a second suite (Microsoft 365, Teams) is one adapter per interface.
- A new developer finds a surface by asking who it is for and when it happens; the subdomain names read as the process in order.
- Cost: a record-and-store slice, a backfill of structured references and a second reshape of the draft and summary code, which TASK-135 had merged by mechanism. Accepted as the price of a shape that does not need a third reshape.
- Cost: `response/` is large; its `service.py` is orchestration only, because the record, the store and the adapters live in `core/`.
- The postmortem side is where the feature gains the most value after the migration: today one meeting is created and action items are tables in the report.

## Checks

- Review: every incident command resolves its incident through `find_incident_for_conversation`; `conversation_is_writable` is called only before a write to the conversation.
- Review: every reference type in `core/domain.py` has system and tenant fields; grep finds no `docs.google.com`, `drive.google.com` or `slack.com` URL built in the umbrella outside `core/adapters/`.
- grep: no read of the incident list sheet or of a report document as input to a business decision.
- import-linter: the incident layers contract lists `response | comms | postmortem` above `core` above `common` with `exhaustive = true`; `core/` has no `entrypoints/`, no hookimpl and no entry point; no module in the umbrella imports `integrations.openai` or `integrations.opsgenie`.
- grep: `Severity`, `IncidentStatus` and `StatusUpdateStage` are defined once, in `common/`; no subdomain defines a status-like enum.
- Boot test with no case-system instance configured: the incident plugins register and the recorder is the no-op implementation.
- Review: the store writes timeline entries and status updates as records; no `list_append` and no get-then-put in `core/`.
- Test: with no new human messages since the latest approved update, drafting makes no model call; a security or unknown-flag incident makes no model call until the responder confirms; the form has no AI section when text generation is unconfigured and saving and approving still work; no status-update use case posts to the incident conversation.

## Migration

Tickets: TASK-144 (human-first status updates, the starting point), TASK-145 (the umbrella moved to `features/incident/` first, then the rebuild by surface over `response`, `comms` and `postmortem` with scribe dissolved), TASK-146 (the on-call capability), TASK-138 (the calendar capability), TASK-25.10 and TASK-134 (text generation), TASK-36.1 and TASK-36.3 (pinning before each rebuilt surface), TASK-108 and TASK-109 (the store's inside), TASK-83 (person references). Expansions are the drafts named above.

Tolerated until then, each closing in a TASK-145 slice:
- the `scribe` subdomain holding draft and summarize;
- the incident list sheet read for uniqueness checks and listings, and written through `infrastructure.spreadsheets`;
- stored items with bare vendor ids and a `report_url` string; roles in the report's Drive properties; severity stored as the free strings `none` and `sev-1` to `sev-4`;
- `db_operations.py`'s `list_append` and the provisional `aws_platform` DynamoDB adapter;
- `IncidentTranscriptReader` taking a conversation id string; `find_incident_for_conversation` served by a scan of the legacy table;
- `documents`, `drive`, `meet` and `scheduling` as adapter-only siblings, and two Google Docs adapters;
- draft and summarize calling the OpenAI `Summarizer` directly, and `comms`' local `TextGenerator` interface, until TASK-25.10;
- the single Google tenant as the implied system for every new incident.

**Changes:**
- 2026-10-02: Accepted (TASK-97). Option A with the external-platform seam kept optional; calendar consumed as a workplace capability (TASK-138).
- 2026-10-06 to 2026-10-08: external status updates as records in `core/`, shown in modals only, security confirmation before drafting, legacy `updates` command retired (TASK-140).
- 2026-10-09: status updates are written by the responder first; AI drafting is an optional assist inside the form (TASK-144).
- 2026-10-09: subdomains are `response`, `comms` and `postmortem`, named for the process; `scribe` is dissolved; the vocabulary section, severity and the five roles on the record, communications by audience, detection through the webhooks capability, on-call as a capability, and the optional expansions are recorded (TASK-145, TASK-146).
- 2026-10-09: the umbrella moved as it stands from `packages/incident/` to `features/incident/`, the first-mover wiring of `features` into the wheel and the import contracts (TASK-145.1).
- 2026-10-09: status updates carved out of `scribe` as the `comms` subdomain and plugin `incident.comms`; their action and callback ids moved to `incident.comms.status_update.*` (TASK-145.4).
- 2026-10-09: severity widened to levels 0 to 4 because teams use different scales; revisited if the organisation standardises (TASK-145.5).
