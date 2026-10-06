---
status: Accepted
date: 2026-10-02
applies: target
scope: What the SRE bot owns and what it coordinates for incident management, where the incident record of truth lives, the shape of the incident feature umbrella, and the optional seam for an external case-management platform.
---

# Incident Management

## Context

`app/modules/incident/` (about 4,700 lines, 17 modules) is the largest legacy surface and is built around Google Workspace resources rather than around the incident. The channel name is the key: every command resolves its incident through the Slack channel, and an archived channel cannot be edited, so status and report updates break once a channel is archived. The incident list is a Google Sheet that is appended at declare time, read back for uniqueness checks and listings, and updated on status change (TASK-73 shows a status update that silently never reaches it). The IC and OL roles live in the report document's Drive properties. The DynamoDB item (`models/incidents.py`) stores bare vendor ids and a `report_url` string, is updated by `list_append` for its activity log, and is reached through the provisional `packages/aws_platform` adapter. `core.py:176`, `:182` and `:481` build `docs.google.com` links from a bare id. Retro events drop fields on the way to the Calendar adapter (TASK-86), and several Google writes are replayed by SDK retries (TASK-87).

The capability inventory taken on 2026-10-02 (TASK-97 notes) lists what users depend on, separately from how it is done: the declare modal and the resources it creates (channel, report from a template, video call, bookmarks, canvas, list row, record, on-call and group invites), a five-step status lifecycle (`Open`, `In Progress`, `Ready to be Reviewed`, `Reviewed`, `Closed`) fanned out to the document, the list, the record and the channel, the show and update modals, the IC and OL roles, floppy-disk reactions that capture messages into the report's timeline, daily stale-channel nudges with archive and schedule-retro buttons, retro scheduling with an availability search, the alert buttons rendered by the webhooks pipeline, EN and FR, and the `draft` and `summarize` commands. Five of those surfaces are not in the legacy inventory: the canvas, the source-alert bookmark, the floppy-disk handlers, the recreate-missing-resources path and the `updates` command, which adds free-text updates through a modal and lists them by reading the item and rewriting its `incident_updates` list with a `SET` (`incident_folder.py`); two incidents have ever used it.

Three options were weighed: the bot owns incident management (A); an external incident-response platform owns the case and the bot coordinates around it (B); a split with a thin coordination record (C). DFIR-IRIS was the candidate platform. Its current documentation, read on 2026-10-02, says: LGPL-3.0 (`iris-web`, the Python client; the v3 frontend is AGPL-3.0-or-later), self-hosted by docker compose and **requiring PostgreSQL** (12 on v2.4, 18 on v3) with RabbitMQ and a Celery worker; a REST API whose v1 endpoints are deprecated in API v2.1.0 and removed in IRIS v3, leaving `/api/v2/cases`, `/notes`, `/tasks`, `/events`, `/iocs` and `/assets`; user-bound Bearer API keys where renewing revokes the previous key, so a service account and a non-overlapping key swap are needed; a native webhooks module that posts on case, note, task and event hooks with undocumented auth and retry behaviour; an English-only UI (multi-language request open since 2022); a 2023 roadmap note pausing new features, no support or LTS policy, and a stale v1-shaped Python client. Sources: [docs.dfir-iris.org/latest/operations/api](https://docs.dfir-iris.org/latest/operations/api/), [API reference v2.1.0](https://docs.dfir-iris.org/latest/_static/iris_api_reference_v2.1.0.html), [changelog](https://docs.dfir-iris.org/latest/changelog/), [getting started](https://docs.dfir-iris.org/latest/getting_started/), [IrisWebHooks](https://docs.dfir-iris.org/latest/operations/modules/natives/IrisWebHooks/), [users and service accounts](https://docs.dfir-iris.org/latest/operations/access_control/users/), [configuration](https://docs.dfir-iris.org/latest/operations/configuration/), [roadmap](https://docs.dfir-iris.org/roadmap/), [issue #147](https://github.com/dfir-iris/iris-web/issues/147), [iris-web](https://github.com/dfir-iris/iris-web), [iris-frontend](https://github.com/dfir-iris/iris-frontend), [iris-client issue #12](https://github.com/dfir-iris/iris-client/issues/12). There is no live open-source comparator for an SRE incident process: TheHive's repository was archived on 2025-12-05 and TheHive 5 is private-source freemium ([TheHive](https://github.com/TheHive-Project/TheHive), [StrangeBee FAQ](https://strangebee.com/blog/faq-for-thehive-5s-upcoming-distribution-model/)), and Netflix Dispatch was archived on 2025-09-03 ([Dispatch](https://github.com/Netflix/dispatch)).

Organisation constraints: Government of Canada (EN and FR, WCAG 2.1 AA, Canadian residency), self-hosted open source over SaaS, Slack today and Teams later, and introducing PostgreSQL is a gated infrastructure decision of its own. The GC Notify team is a consumer of this feature.

Human direction, 2026-10-01 and 2026-10-02 (recorded on TASK-97): the incident is the anchor, not the channel; resources are flexible by kind and by system; an external platform is optional and the feature must work in full without one; the current behaviour is preserved while the delivery sequence in doc-2 runs, and the feature expands afterwards.

## Decision

**Option A: the bot owns incident management.** The system of record is the **incident record in app storage**, written and read through the storage contract ([plugin-architecture.md](plugin-architecture.md), [cloud-portability.md](cloud-portability.md)). The bot **coordinates** everything that lives in a workplace or external system: the conversation, the report, the video call, the retrospective event, paging and notifications, and optionally an external case. None of those is a record of truth ([workplace-systems.md](workplace-systems.md) rule 5). The incident list sheet survives, if at all, as a write-only projection rebuilt from storage. An external platform is not adopted; the seam for one is kept, as described below, so a later B-shaped state (a platform holding case content) is reachable without reworking the record, its store or the subdomains.

### The incident record

The record is keyed by an **app-generated, opaque incident id**. The conversation is a resource of the incident, never its key. The legacy incidents table's UUID `id` is that id: the store keeps it, so records keyed by it today survive the move to the store. The record holds:

- the title, the product, the severity, the security flag and the declarer;
- the status, from a closed set the feature owns;
- the timing fields: declared, detection, impact start, impact end;
- the roles: incident commander and operations lead, as person references (an email or platform account today; a person id once [people-and-accounts.md](people-and-accounts.md) is adopted, TASK-83);
- **typed references** to its resources, each a frozen dataclass carrying the **system, the tenant and the vendor id**, plus the vendor-provided link where one exists (rule 4; a link is never built by string-formatting a vendor URL):
  - conversation: platform, tenant, channel id;
  - report: system, tenant, document id (optional);
  - video call: system, tenant, space id (optional);
  - retrospective: system, tenant, event id (optional);
  - external case: system, instance, case id, case uuid (optional);
  - source alert: platform, tenant, channel, message id (optional).

Timeline entries and incident updates are **their own records under the incident**, never a list attribute on the incident item, so no persisted state is written with a read-modify-write or a vendor list-append. The storage layout that realises this is decided in the record-and-store slice's plan, not here.

### The feature umbrella

`features/incident/` follows [feature-packages.md](feature-packages.md): subdomains above `core/` above `common/`, imports one way, `core/` reached only through `core/api.py`.

**`core/` owns:**

- the record, its domain types and its **store**: an `IncidentStore` interface, its implementation over the storage contract, and an in-memory fake; likewise the `StatusUpdate` record and its `StatusUpdateStore`, which appends each update as its own record under the incident id with a conditional put;
- the **shared command check, in two parts**: `find_incident_for_conversation` maps a command's conversation to a known incident's id or returns a classified refusal, and every command applies it; `conversation_is_writable` is applied only by operations that write to the conversation. A status or report update on an incident whose channel is archived keeps working;
- the **resource interfaces with two or more subdomain consumers**, each purpose-shaped, with one adapter per system in `core/adapters/`, selected by the stored reference and never by a setting:
  - `IncidentConversation`: post, set purpose, bookmark, invite, archive, writability; Slack adapter;
  - `IncidentReport`: create from a template, replace placeholders, set the status text, append a timeline entry, link; Google Docs and Drive adapter, which absorbs today's `packages/incident/documents` and `drive` and the `IncidentDocumentStore`;
  - `IncidentTranscriptReader` (TASK-135.1), which takes the record's conversation reference in the end state;
  - `ProductCatalog`: the product list and each product's on-call schedule; a Drive-folders adapter during the migration, app records afterwards;
  - `ExternalCaseRecorder`: open, update, add an entry, close an external case; see the seam below.
- the templates and per-system resource configuration those adapters need, read inside the adapters.

**`common/`** holds the incident settings tree and vocabulary with two or more consumers and no I/O: the status values, and the action ids one subdomain renders and another handles.

**Subdomains are enablement units** (rule 2), with dotted entry points (rule 6):

| Subdomain | Entry point | Holds | Own adapters |
| --- | --- | --- | --- |
| `lifecycle/` | `incident.lifecycle` | declare, status, show and update, roles, archive, timeline capture, canvas, recreate resources, the alert buttons registered into the webhooks capability, and the stale-channel nudge job | video-call creation (one consumer) |
| `retrospective/` | `incident.retrospective` | attendee selection, availability search and the retro meeting, through the calendar capability; later rescheduling, changes, cancellation, reminders and action items | none |
| `scribe/` | `incident.scribe` | `draft` and `summarize` (TASK-135) and external status updates; prompts, templates and incident-specific post-processing over the text-generation capability | `StatusPagePublisher` adapters (one consumer) |

**A retrospective is a meeting that happens to be about an incident.** Managing calendars is not incident work, so meeting scheduling is the `calendar` workplace capability ([workplace-systems.md](workplace-systems.md): calendar is a capability, one adapter per system, the person's calendar home or the stored reference selects the system). `app/capabilities/calendar/` grows out of `packages/incident/scheduling` (TASK-138) with the operations incident uses now, availability and meeting creation; update, reschedule and cancel arrive with their first consumer. The retrospective subdomain holds the incident side only: who attends, which incident, the stored `RetrospectiveReference`, and the conversation posts.

The nudge's "schedule retro" button carries an action id that `retrospective/` registers and `lifecycle/` only renders, through a constant in `common/`; no subdomain imports another (rule 3). Drafting and summarizing are uses of the text-generation capability (TASK-25.10, TASK-134); the feature supplies the transcript, the instructions or template and the post-processing.

### External status updates

A status update is the public message about an incident for the people who use the affected service: a `scribe/` use case run by `/sre incident status-update`. It follows the patterns product teams already publish: GC Notify's bilingual incident history (a dated summary, the stage with a date and time in ET or HE, what happened, who is affected, "You do not need to take any action" when true) and GC Sign In's notices to relying parties in Eastern time.

- **Stage** is a public vocabulary, separate from the internal status: Investigating, Identified, Monitoring, Resolved (Enquête en cours, Problème identifié, Sous surveillance, Résolu; only Résolu is attested in GC Notify's history, the rest are the team's choice). Stages only move forward.
- **Fields**: stage, affected service by its public name, user-visible impact, what we are doing (no root-cause speculation), workaround or no action needed, and the next update time with its date. An update follows about every 30 minutes; the incident never goes silent.
- **Drafting**: the text-generation capability fills the fields in EN and FR from the conversation since the latest update. Code, not the model, decides nothing is new: with no new human messages the prior update is carried forward as "no new information, next update by", without a model call.
- **Approval**: a responder edits and approves the draft in a modal; a security incident needs a second confirmation. Nothing is published unapproved. Drafts and approved updates are `StatusUpdate` records in `core/`, never the `incident_updates` attribute.
- **Rendering and publishing**: a comms profile turns the stored fields into text (labels, public service names, layout, time format). One default profile, modelled on GC Notify's pattern, ships first; per-product profiles keyed by the `ProductCatalog` product come later and never change the prompt. `StatusPagePublisher` in `scribe/` publishes the text; its first adapter returns copy-ready EN and FR text to the approver, and a status page is one more adapter.

Sources, read on 2026-10-06: [Statuspage incident communication tips](https://support.atlassian.com/statuspage/docs/incident-communication-tips) (updates every 30 minutes, plain terms), [GC Notify incident history](https://articles.alpha.canada.ca/notification-gc-notify/system-status/), [GC Sign In service management](https://connect.canada.ca/en/discover/service.html), and [Rootly AI](https://docs.rootly.com/ai/ai-summaries) ("You review and edit the draft before submitting").

### System selection for a new incident

An existing incident's resources are reached through the system named in each stored reference. For a **new** incident, the system that creates its report and video call is an **incident-feature policy setting** in `common/settings.py`, which names one of the configured workplace tenants and defaults to the only one configured. This is feature policy, not a global provider switch (rule 3). It may later be replaced by the declaring conversation's platform or the declarer's linked account without changing the record.

### The optional external platform

- **Interface:** `ExternalCaseRecorder` in `core/api.py`, returning `OperationResult`. Operations: open a case for an incident and return its reference; update it (status, severity, title); add an entry (timeline, note, report link); close it.
- **Adapter:** `features/incident/core/adapters/<system>.py`, a feature-owned adapter under [outbound-clients.md](outbound-clients.md), calling a client built by `integrations/<system>/` (factory with explicit timeout and retry, `classify_<system>_error`). Never an `app/infrastructure/` capability. For DFIR-IRIS the adapter targets the `/api/v2` surface directly with a service-account Bearer key; the stale Python client is not used.
- **Enablement:** configuration lists **zero or more case-system instances** in the incident settings tree, each with its system, instance name, base URL and a secret reference, the way rule 3 names workplace tenants. Which instance an existing incident uses is its stored external-case reference. Which one a new incident uses is the policy setting above. Nothing is enabled by a global flag.
- **None configured:** the provider returns a no-op recorder; the external-case reference stays empty; no link is rendered; every other capability works. This is the shipped state.
- **Inbound:** events from the platform (case or note changes) arrive later through the webhooks capability as hints that trigger a re-read through the recorder; they never write state directly. No polling is built.

### What the design rejects

- B now: PostgreSQL is gated, the UI is English-only, the API is moving to v3, the project has no support policy, and a second tool would reach the feature's consumers. The parallel platform's operating cost is not justified today.
- C now: a thin coordination record still needs status and timeline for the chat-native workflows, so it converges on A, and there is no platform to delegate to.
- Per-command subdomains (declare, channel, documents, retro, alerts, draft, summary, scheduling): rule 2.
- A nudges subdomain: its buttons would need both `lifecycle/` and `retrospective/`.
- A products subdomain: declare depends on the catalog, so it belongs in `core/`.
- Keeping `documents`, `drive`, `meet` and `scheduling` as adapter-only siblings: they are not enablement units, and rule 4 puts adapters in `core/` or a subdomain.
- `writing` or `assist` as the merged subdomain's name: `scribe` is the feature's own word.

## Consequences

- Features break less: an incident stays editable after its channel is archived, and a failed projection write is a retry or a rebuild, not lost data.
- Resource creation, link rendering and vendor behaviour are written once per system in `core/adapters/`; a second suite (Microsoft 365, Teams) is one adapter per interface and no subdomain change.
- Cost: a record-and-store slice and a backfill of structured references, with the sheet reduced to a projection. Those are the price of a record of truth in app storage.
- Cost: `lifecycle/` is large. Its `service.py` is orchestration only, because the record, the store and the resource adapters live in `core/`; a `lifecycle/` module that grows vendor code is misplaced.
- An external platform can be attached by adding a client package, one adapter and one configured instance. Its inbound events add a webhooks-capability registration. The record and the subdomains do not change.
- Paging and on-call (Opsgenie, which ends on 2027-04-05) are coordinated resources outside this record and are a separate decision.
- The retro portion is the thinnest part of today's workflow and is where the feature gains the most value after the migration. Today one meeting is created and nothing can move, change or cancel it, and the retrospective's action items are tables at the end of the report with no record of whether they were done unless someone pastes a tracker link. The expansion drafts make retro meeting management complete (reschedule, modify, cancel, attendees, reminders) and make action items records of the incident, with owners, due dates, completion and an optional typed reference to an external tracker. The report then carries them as a projection.
- The replacement expectation of the archived TASK-80 holds: document I/O is the `IncidentReport` interface in `core/` with one adapter per system; it becomes a capability only when a second feature needs it, and never an infrastructure Protocol.

## Checks

- Review: every incident command resolves its incident through `find_incident_for_conversation`; `conversation_is_writable` is called only before a write to the conversation; no subdomain re-implements the lookup.
- Review: every reference type in `core/domain.py` has system and tenant fields; grep finds no `docs.google.com`, `drive.google.com` or `slack.com` URL built in `features/incident/` outside `core/adapters/`.
- grep: no read of the incident list sheet or of a report document as input to a business decision; `infrastructure.spreadsheets` and `capabilities/spreadsheets` imported only by the projection writer.
- import-linter: the `features.incident` layers contract lists `lifecycle | retrospective | scribe` above `core` above `common` with `exhaustive = true`; `core/` has no `entrypoints/`, no hookimpl and no entry point.
- Boot test with no case-system instance configured: the incident plugins register and the recorder is the no-op implementation.
- Review: `ExternalCaseRecorder` adapters live in `core/adapters/` and import `integrations/<system>/` only; no `app/infrastructure/<system>/` package exists for a case platform.
- Review: the incident store writes timeline entries as records; no `list_append` and no get-then-put in `core/store.py`.
- Test: a status update is stored only as a `StatusUpdate` record, never on the incident item; with no new human messages since the latest update, drafting makes no model call.

## Migration

Tickets: TASK-135 (the `scribe` subdomain over `core/`, in `packages/incident/`), TASK-140 (external status updates), TASK-124.5 (the umbrella to `features/incident/`), TASK-138 (the calendar capability from `packages/incident/scheduling`), TASK-38 and its slices TASK-38.1 to TASK-38.8 (the surface-by-surface rebuild, behaviour-preserving and pinned by TASK-36.1 and TASK-36.3), after TASK-27.1, TASK-27.2, TASK-108 and TASK-109 for the store and TASK-83 for person references. Incident leaves the provisional `packages/aws_platform` DynamoDB adapter when the last legacy module importing `db_operations` is deleted (TASK-38.5), which lets TASK-88 dissolve that package. The expansion tickets (the metrics replacement, products as app records, the external case recorder and its first adapter, inbound case events, second-suite adapters, internal timeline updates, per-product status-update profiles and status-page adapters, retro meeting management, retro action items as records) are drafts under TASK-97 and start after doc-2's sequence is finished.

Tolerated until then, each closing in the slice named:
- the incident list sheet read for uniqueness checks and listings (TASK-38.7);
- `infrastructure.spreadsheets` as the list's writer (TASK-38.7, or TASK-121 if it lands first);
- stored items with bare vendor ids and a `report_url` string (backfilled in TASK-38.7);
- `db_operations.py`'s `list_append` and the provisional `aws_platform` DynamoDB adapter (TASK-38.5);
- roles stored in the report's Drive properties (TASK-38.4);
- `IncidentTranscriptReader` taking a conversation id string (TASK-38.2);
- `packages/incident/documents`, `drive` and `meet` as adapter-only siblings (TASK-38.2, TASK-38.3), and `scheduling` as a feature-owned calendar adapter (TASK-138);
- the retro flow limited to creating one meeting, and action items as tables in the report (expansion drafts);
- the single Google tenant as the implied system for every new incident, until the policy setting exists (TASK-38.3);
- `find_incident_for_conversation` served by an adapter that pages through a scan of the legacy incidents table by channel id and returns its UUID, until the store replaces it (TASK-38);
- the legacy `/sre incident updates` command and the `incident_updates` attribute, retired once status updates ship (TASK-140).

**Changes:**
- 2026-10-02: Accepted (TASK-97). Option A with the external-platform seam kept optional; subdomains `lifecycle`, `retrospective` and `scribe`; `core/` contents and the two-part command check per the 2026-10-01 direction.
- 2026-10-02: calendar is consumed as a workplace capability (TASK-138), the retrospective subdomain owns no calendar adapter, and the retro expansion (meeting management, action items as records) is named.
- 2026-10-06: external status updates are a `scribe` use case with records under the legacy UUID in `core/`, a publisher and comms profiles, and an interim lookup over the legacy table (TASK-140).
