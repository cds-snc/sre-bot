# Incident

The incident feature umbrella. Its target shape is decided in
[`decisions/incident-management.md`](../../../decisions/incident-management.md):
subdomains above `core/` above `common/`, imports one way, `core/` reached only
through `core/api.py`. This page maps what is here today to that target, and
says where new incident work goes.

Most of today's incident behaviour still lives in the legacy
`app/modules/incident/`. It is the code being migrated, not a pattern to copy.

## Folders

| Folder | Current role | Used today by | Target (`decisions/incident-management.md`) |
| --- | --- | --- | --- |
| [`core/`](core/) | Shared kernel. `api.py` exposes `IncidentTranscriptReader` (async; reads a conversation by its `ConversationReference`; classified `OperationResult`s), `TranscriptMessage` and `get_incident_transcript_reader`, `IncidentConversation` (async writes to the conversation by its reference: post, set purpose and read it back with `purpose`, link bookmark, invite chat account ids, archive, `is_writable`; no create yet, TASK-145.7 adds it with the first working-surface binding) and `get_incident_conversation`, `conversation_is_writable(conversations, conversation | None)`, the check before every write to a conversation, `IncidentReport` (async apart from `link`; the report the record's `ReportReference` names: create from template in [incident_core] `folder_id`, placeholders, the status line (`set_status_text`), read sections, draft copy, link) and `get_incident_report`, `VideoCall` (async `create` of the incident's video call, returning a `VideoCallReference`; `link`) and `get_video_call`, `LegacyRolesReader` with `get_legacy_roles_reader` and `read_incident_roles(incident, legacy)` (an incident's five roles: the record's, else the report's Drive properties `ic_id` and `ol_id` through the legacy-only `adapters/legacy_roles.py`, read-only, deleted by TASK-145.13), the async command check `find_incident_for_conversation(store, conversation)` over the `IncidentStore`, and `build_incident_store` and `build_status_update_store`, which entry points call per service scope with the resolved `RecordStore` and the incident core settings (the incident store also with the configured systems); `adapters/slack.py` is the Slack transcript reader, on the async read client, and `SlackIncidentConversation`, which writes on the Slack write handle (rate-limited requests only are retried) and maps the not-writable Slack codes to `CONVERSATION_NOT_WRITABLE`; `adapters/google_docs.py` is the umbrella's one Google Docs and Drive adapter (report placeholders and revision-guarded edits, Docs URL id extraction, incident folders, files and Drive `appProperties` metadata through the gateway's Drive service, the Drive healthcheck, and scribe's section reader and draft writer) with `GoogleDocsIncidentReport`, the `IncidentReport` over it (each method's blocking call offloaded with `asyncio.to_thread`); every service is built with scopes only, never a delegation subject or credentials; legacy `modules/incident` and `jobs/scheduled_tasks.py` call its module functions until TASK-145.13; `adapters/google_meet.py` is `GoogleMeetVideoCall`, the `VideoCall` over Google Meet (the blocking request offloaded with `asyncio.to_thread` inside the adapter, SDK retries off), and the legacy `create_space` that the legacy declare calls until its cutover; `domain.py` holds the shared domain types, including the document section types (`DocumentSection`, `SectionDraft`, `DocumentField`, `DraftWriteResult`), the `Incident` record (with `declared_by` and a required `security_incident` bool), `IncidentChanges` (a field update, `Keep.KEEP` for unchanged), `TimelineEntry` with `TimelineEntryKind` and `SeverityChange`, and the typed references (exported by `api.py`); `store.py` holds the `IncidentStore` interface (async; exported by `api.py`: get, find by conversation, list open, read the security flag, create (the end-state record alone, the commit point; idempotent on the incident id), `attach_conversation` (a chat binding, then a primary's conversation copy on the record, guarded on `record_version`) and `set_reference` (one reference map, guarded on `record_version`), and the field writes `update_fields`, `set_roles` and `set_status` (each one update guarded on `record_version` and the read values it changes, one re-read on a lost guard, a replay writes nothing; an item below version 2 is upgraded on write through `plan_item_upgrade`, its binding put first; closing removes the open-index attributes, reopening sets them; a severity change then appends a `severity_changed` timeline entry); an incident has zero or more chat bindings and the HTTP API needs none; no caller until TASK-145.7.9 and the TASK-145.8 cutovers) and `RecordIncidentStore`, which runs each call's blocking `RecordStore` work in one `asyncio.to_thread` and reads and writes incident items through the records contract with `adapters/incident_items.py` as the item writer and parser, upgrades items without `record_version` through the legacy item bridge (`adapters/legacy_items.py`), and has `InMemoryIncidentStore` in `adapters/in_memory.py` as the fake (`InMemoryIncidentReport` is the report's, `InMemoryIncidentConversation` the conversation's); `legacy_upgrade.py` holds `LegacyUpgrade`, the legacy upgrade runner (built by `build_legacy_upgrade` in `api.py`; one capped whole-table read, the per-item plan `plan_item_upgrade` in `adapters/item_upgrade.py` over the same bridge, per item the binding put into the bindings table and then one guarded update raising `record_version` to 2, one report event per run), registered by `response/` as the incident legacy upgrade job (run procedure below); `store.py` also holds the `TimelineStore` interface and `RecordTimelineStore`, which appends each timeline entry (`TimelineEntry`: a kind, `message` with text or `severity_changed` with its `SeverityChange`, rendered at read time) as its own item under the incident id at `entry_key` `'<posted_at>#<entry_id>'` in the timeline table, idempotent on that key, with `adapters/timeline_items.py` as the item layout and system entry ids and `InMemoryTimelineStore` as the fake; and the `StatusUpdateStore` interface (async) and `RecordStatusUpdateStore`, which runs each call in one `asyncio.to_thread` and keeps each public status update (`StatusUpdate`) as its own item under the incident id in the status-updates table through the records contract, with `adapters/status_updates.py` as the item layout and `InMemoryStatusUpdateStore` as the fake. No hookimpl, not an entry point. | `comms/`, `scribe/` | Stays `core/`. Grows the `IncidentStore` writes and the resource interfaces with two or more subdomain consumers still to come (`ProductCatalog`, `ExternalCaseRecorder`), each with one adapter per system in `core/adapters/`. |
| [`common/`](common/) | No-I/O vocabulary and settings: `vocabulary.py` (`IncidentStatus`, `Severity`, `IncidentRole`, `StatusUpdateStage`) and `settings.py` (`IncidentCoreSettings`, the `[incident_core]` slice: the incidents, timeline and status-updates table names, the new-incident system policy, unset by default, and the incident folder, report template and list sheet ids, non-public values set from the environment). Imports nothing from `core/` or the subdomains. | `core/`, `comms/` | Stays `common/`: the incident settings tree and vocabulary with two or more consumers. |
| [`comms/`](comms/) | Subdomain and plugin (entry point `incident.comms`): `/sre incident status-update` and the status-updates modal (public status updates, written by a responder with optional AI help). See [`comms/README.md`](comms/README.md). | Slack users | Stays `comms/`: grows other comms profiles and status-page publishers behind `StatusPagePublisher`. |
| [`scribe/`](scribe/) | Subdomain and plugin (entry point `incident.scribe`): `/sre incident draft` and `/sre incident summarize`. See [`scribe/README.md`](scribe/README.md). | Slack users | Stays `scribe/`: prompts, templates and incident-specific post-processing over the text-generation capability. |
| [`response/`](response/) | Subdomain and plugin: `/sre incident status update` and the status engine `change_status`, and `/sre incident roles manage` with its modal and the roles engine `assign_roles` (see [`response/README.md`](response/README.md)); `settings.py` (`IncidentResponseSettings`, the `[incident_response]` slice: the declare path's Slack ids, the handbook id, a non-public value set from the environment, and the upgrade job's `upgrade_mode`, `upgrade_interval_minutes` and `upgrade_lease_ttl_seconds`); `plugin.py`, the entry point `incident.response` (the module, not the package, because the host configuration phase and the legacy modules read `settings.py` before plugins load): it requires the Slack and Google Workspace tenants, registers the status and roles commands and the `incident_response` catalogue, and registers the incident legacy upgrade job unless `upgrade_mode` is `off`; `legacy_upgrade_job.py`, one run of that job (one service scope, `build_legacy_upgrade` from `core/api.py`). | Slack users; legacy `modules/incident`; the host configuration phase (`settings.py`) | The response subdomain: the rebuild of declare, status, roles and the live incident moves in (TASK-145.7, 145.8). |
| [`postmortem/`](postmortem/) | Settings only: `settings.py` (`IncidentPostmortemSettings`, the `[incident_postmortem]` slice: the retro calendar id, a non-public value set from the environment). No hookimpl, not an entry point. | legacy `modules/incident` | The postmortem subdomain: the retro meeting and the report move in (TASK-145.10, 145.11). |
| [`scheduling/`](scheduling/) | Feature-owned calendar code: `adapters/google_calendar.py` and `availability.py` (free/busy computation for the retro). | legacy `modules/incident` | Becomes the `calendar` workplace capability in `app/capabilities/calendar/` (TASK-138); the retrospective subdomain consumes it and owns no calendar adapter. |

Units the decision record names that do not exist yet:

| Target, not yet created | Holds |
| --- | --- |
| `lifecycle/` (entry point `incident.lifecycle`) | Declare, status, show and update, roles, archive, timeline capture, canvas, the alert buttons, and the stale-channel nudge job (TASK-38). |
| `retrospective/` (entry point `incident.retrospective`) | Attendee selection, availability search and the retro meeting through the calendar capability; later rescheduling, reminders and action items. |
| `features/incident/` | Where this whole umbrella moves (TASK-124.5). |

## Legacy floppy-disk timeline capture (until TASK-145.9.2)

The legacy reaction handlers still write to the report's Google Doc. A capture is the
exact reacted-to message (`reactions.get`, thread replies included), keyed by its
channel and full Slack timestamp; removal targets that key. Each rewrite is guarded by
the snapshot's `requiredRevisionId`: a lost guard or an unconfirmed write is re-read
and recomputed, at most three writes and no sleep, and the SDK owns transport retries
([outbound-clients.md](../../../decisions/outbound-clients.md)). A failed or unconfirmed
save or removal posts a bilingual ephemeral notice to the reacting user; look for
`incident_timeline_update_failed` and `incident_timeline_notice_failed`. Delivery is
not durable: recover a missing entry from Slack and the document's version history.

## Rules that hold today

- **Layers.** The import-linter contract `incident-umbrella` in
  `app/pyproject.toml` puts `comms | postmortem | response | scheduling | scribe`
  above `core` above `common`, with `exhaustive = true`: siblings never import each other, and
  `core/` imports none of them. A new folder must be added to that contract.
- **`core/` through `core/api.py` only.** Subdomains import
  `features.incident.core.api`, never `core.adapters` or `core.domain`.
- **Subdomains are plugins; `core/` never is.** A subdomain registers through
  pluggy hookimpls in its `__init__.py` and one line under
  `[project.entry-points.sre_bot]` in `app/pyproject.toml`
  ([`decisions/plugins.md`](../../../decisions/plugins.md)). The umbrella and
  `core/` have no hookimpl and no entry point.
- **No new adapter-only siblings.** The decision record rejects `documents`,
  `drive`, `meet` and `scheduling` as standalone folders; `scheduling` is
  tolerated until its migration slice.

## Legacy upgrade run procedure

The incident legacy upgrade job brings every incident item below `record_version` 2 to it
(`core/legacy_upgrade.py`, over the per-item plan in `core/adapters/item_upgrade.py`;
decisions/incident-management.md, Migration). For an item without `record_version` it runs the
legacy bridge, puts the item's binding and stamps marker 2; for an item at 1 (the end-state shape
without a binding) it puts the binding and raises the marker to 2; an item at 2 or above is not
touched. Per item the binding is put first (`put_if_not_exists`, an existing binding is never
overwritten) and one guarded update, with the marker last, follows, so a crash between the two
converges on the next run. It is registered by `response/plugin.py` and ships with
`[incident_response] upgrade_mode = "off"`, so nothing runs until an environment switches it on in
its own configuration file.

- **When.** A dry run writes nothing, so it may run in an environment as soon as the binding step
  (TASK-145.7.4) is deployed there; production runs one from TASK-145.7.8. The first apply follows
  the last TASK-145.8 reader cutovers (TASK-145.8.3 and TASK-145.8.5.3) deployed and soaked there,
  and a dry run with no blocker: the upgrade writes status, severity and `security_incident` in their
  end-state form, and TASK-145.8 removes the last legacy reader of those attributes. The roles are not
  among the attributes it carries over: no legacy writer set them, they lived in the report's Drive
  properties, which `read_incident_roles` bridges and TASK-145.7.12 maps into the record in a later
  rerun, items already at 2 included. Running it, with a report of nothing pending, is a
  precondition of TASK-145.9 merging.
- **Legacy writers.** Each of these still creates legacy-shaped items, so the job must run again
  after the last one is gone (Migration rule 6):
  - the legacy declare, `app/modules/incident/core.py:36` (`initiate_resources_creation`), removed
    by TASK-145.7.10;
  - the dev add-incident command, `app/modules/dev/incident.py:104`, removed by TASK-145.12.2;
  - the sheet import, `app/modules/incident/incident_folder.py:541` (`create_missing_incidents`,
    reached by `load_incidents` at `app/modules/dev/incident.py:47`), removed by TASK-145.12.2.

  All three write through `db_operations.create_incident`. Recreate, a fourth, was retired with
  `/sre incident create` by TASK-145.8.6. The field updaters
  (`information_update.py:322`, `incident_status.py:59`, through `update_incident_field`) create no
  items and are removed by TASK-145.8.3 and TASK-145.8.5 (close is the last caller of
  `incident_status.py`; the slash status path left it in TASK-145.8.4).
- **Rerun rule.** After TASK-145.12.2 deploys, run the job again (`dry_run`, then `apply`) and
  confirm `pending` 0 and `unbound` empty before TASK-145.13 deletes the job. Items written by a
  legacy writer after the last run have no marker and no binding.
- **Where it runs.** `[scheduler] enabled` must be true (production sets it). The job is a
  leased interval job: one replica runs it, every `upgrade_interval_minutes` (30), under a lease
  of `upgrade_lease_ttl_seconds` (900). The first run is one interval after the task starts, so
  every deploy restarts that wait; to see a report sooner, lower the interval in the same change.
- **Dry run first, per environment.** A PR sets `upgrade_mode = "dry_run"` under
  `[incident_response]` in that environment's file (production: `config/production.toml`, which
  the deploy workflow ships; never a console change). After the deploy, read the
  `incident_legacy_upgrade_report` event. Report keys: `mode`, `outcome`, `failures`, `cap`,
  `scanned`, `already_upgraded` (at marker 2 or above), `to_upgrade` (planned: legacy items and
  items at 1), `upgraded` (legacy items written), `marker_raised` (items at 1 raised),
  `bindings_put` (bindings created), `bindings_existing` (bindings found already present),
  `binding_skipped` (planned items with no binding: a Closed item without a conversation),
  `guard_lost`, `pending` (planned and not written), `unbound`, `unmatched_status`, `unreadable`,
  `dropped` and `tenant_check` (the verified tenant, or a message naming the expected and received
  ids). A dry run counts the plan and writes nothing, so its `bindings_put` is 0. The first
  production dry run confirms the `auth.test` org-token shape (D10 of TASK-145.5.7):
  `tenant_check` is verified; a mismatch is fixed in configuration (`[slack.tenant]
  enterprise_id`), not in code. `already_upgraded` is not 0 in production: the rebuilt writers
  upgrade each legacy item they write (upgrade on write). Read the event, read-only:
  `aws logs filter-log-events --region ca-central-1 --log-group-name /ecs/sre-bot-app --filter-pattern '"incident_legacy_upgrade_report"' --start-time $(( ($(date +%s) - 7200) * 1000 )) --query 'events[].message' --output text`.
  The mode stays `dry_run` until the apply PR replaces it. Each run also logs one
  `incident_legacy_field_dropped` warning per dropped field (the shared bridge's read-path
  warning), so a run with ten or more drops sets off the warning alarm every interval; if it does,
  a PR sets the mode to `off` until TASK-145.7.12 keeps a batch run's drops in its report only.
- **A blocked dry run.** Any unmatched status, unreadable item or `unbound` item fails the run,
  logged at error, so the error alarm fires on every run. `unbound` lists, by id only, the open
  items without a conversation: set their `channel_id` or mark them Closed by hand in the table.
  Switch the mode back to `off`, fix the listed items, then dry run again. If two items share one
  `channel_id`, the conversation lookup was already ambiguous and stays so: fix it by hand.
- **Apply.** A PR sets `upgrade_mode = "apply"`. Confirm that a later report shows `pending` 0
  (a run cut short by throttling ends `write_failed`, and the next run resumes: each update is
  guarded on `record_version` at its read value, absent or 1, and a binding already put reports
  as `bindings_existing`), then a PR sets the mode back to `off`.
- **Locally.** `INCIDENT_RESPONSE__UPGRADE_MODE=dry_run` and `SCHEDULER__ENABLED=true` in
  `app/.env`; the plugin needs the Slack and Google Workspace tenants, as `incident.scribe` does.
- **Removal.** TASK-145.13 deletes the job's registration in `plugin.py`, `legacy_upgrade_job.py`
  and the three `upgrade_*` keys once a production run reports nothing pending.

## Where does new work go

| You are adding… | Put it in | Notes |
| --- | --- | --- |
| A new AI-assisted text use case over the incident transcript or report (a new draft, summary or rewrite) | `scribe/` | Follow [Adding a use case](scribe/README.md#adding-a-use-case). |
| A change to `/sre incident draft` or `/sre incident summarize` | `scribe/` | See the at-a-glance table in [`scribe/README.md`](scribe/README.md). |
| A change to `/sre incident status-update`, its modal, the approval or the copy-ready text | `comms/` | See [`comms/README.md`](comms/README.md). |
| A change to an incident's status (`/sre incident status update`, later the update modal and close) | `response/service/status.py` (`change_status`) | The record first, then the report line, the list and the channel; see [`response/README.md`](response/README.md). |
| A resource interface two or more subdomains need (conversation, report, product catalogue, external case) | `core/api.py` + one adapter per system in `core/adapters/` | Adapters are selected by the stored reference, never by a setting. |
| An interface only one subdomain needs | That subdomain's `adapters/` | Moves to `core/` when a second consumer appears. |
| Reading what was said in an incident channel | Use `IncidentTranscriptReader` from `core/api.py` with the record's `conversation` | Do not read Slack history in a subdomain. |
| Writing to an incident channel (post, purpose, bookmark, invite, archive) | `IncidentConversation` from `core/api.py`, after `conversation_is_writable` on the record's conversation | Do not call Slack's write methods in a subdomain; feature writes use the rate-limit-only write handle. |
| Google Docs, Drive or Meet operations for an incident | `core/adapters/google_docs.py`, `core/adapters/google_meet.py` | New report work goes behind the `IncidentReport` interface, video-call work behind `VideoCall`; `create_space` takes fixes, not new operations. |
| The incident list sheet (a row per incident, its status cell) | `core/adapters/google_sheets.py`, `core/adapters/list_rows.py` | Behind `IncidentListProjection`: write-only, rows keyed by incident id; nothing reads the sheet back. |
| Calendar, availability or meeting scheduling | Not `scheduling/` | The `calendar` capability (TASK-138); the incident side of the retro goes to `retrospective/`. |
| Declare, status, roles, archive, timeline, canvas, alert buttons, nudges | `lifecycle/` (target) | Rebuilt surface by surface in TASK-38; until then that behaviour is in legacy `modules/incident`. |
| Retro attendees, retro meeting, retro action items | `retrospective/` (target) | Expansion drafts under TASK-97. |
| Settings or constants shared by two or more incident subdomains | `common/` (target) | A setting with one consumer stays in that subdomain's `settings.py`. |
| An external case platform (for example DFIR-IRIS) | `ExternalCaseRecorder` (target) in `core/api.py`, adapter in `core/adapters/<system>.py`, client in `app/integrations/<system>/` | Never an `app/infrastructure/` capability. |
