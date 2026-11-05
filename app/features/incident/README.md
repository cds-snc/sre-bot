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
| [`core/`](core/) | Shared kernel. `api.py` exposes `IncidentTranscriptReader`, `TranscriptMessage` and `get_incident_transcript_reader`, the command check `find_incident_for_conversation(store, conversation)` over the `IncidentStore`, and `build_incident_store` and `build_status_update_store`, which entry points call per service scope with the resolved `RecordStore` and the incident core settings (the incident store also with the configured systems); `adapters/slack.py` is the Slack transcript reader; `adapters/google_docs.py` is the umbrella's one Google Docs and Drive adapter (report placeholders and revision-guarded edits, Docs URL id extraction, incident folders, files and Drive `appProperties` metadata, the Drive healthcheck, and scribe's section reader and draft writer), used by legacy `modules/incident`, `jobs/scheduled_tasks.py` and `scribe/providers.py` until the `IncidentReport` interface wraps it (TASK-145.6.2); `domain.py` holds the shared domain types, including the document section types (`DocumentSection`, `SectionDraft`, `DocumentField`, `DraftWriteResult`), the `Incident` record (with `declared_by` and a required `security_incident` bool), `TimelineEntry` and the typed references (exported by `api.py`); `store.py` holds the `IncidentStore` interface (exported by `api.py`: get, find by conversation, list open, read the security flag) and `RecordIncidentStore`, which reads incident items through the records contract with `adapters/incident_items.py` as the item parser, upgrades items without `record_version` through the legacy item bridge (`adapters/legacy_items.py`), and has `InMemoryIncidentStore` in `adapters/in_memory.py` as the fake; `legacy_upgrade.py` holds `LegacyUpgrade`, the legacy upgrade runner (built by `build_legacy_upgrade` in `api.py`; one capped whole-table read, the same bridge, one guarded update per item, one report event per run), registered by `response/` as the incident legacy upgrade job (run procedure below); `store.py` also holds the `StatusUpdateStore` interface and `RecordStatusUpdateStore`, which keeps each public status update (`StatusUpdate`) as its own item under the incident id in the status-updates table through the records contract, with `adapters/status_updates.py` as the item layout and `InMemoryStatusUpdateStore` as the fake. No hookimpl, not an entry point. | `comms/`, `scribe/` | Stays `core/`. Grows the legacy item bridge and the `IncidentStore` writes, the two-part command check (`find_incident_for_conversation`, `conversation_is_writable`) and the resource interfaces with two or more subdomain consumers (`IncidentConversation`, `IncidentReport`, `ProductCatalog`, `ExternalCaseRecorder`), each with one adapter per system in `core/adapters/`. |
| [`common/`](common/) | No-I/O vocabulary and settings: `vocabulary.py` (`IncidentStatus`, `Severity`, `IncidentRole`, `StatusUpdateStage`) and `settings.py` (`IncidentCoreSettings`, the `[incident_core]` slice: the incidents, timeline and status-updates table names, the new-incident system policy, unset by default, and the incident folder, report template and list sheet ids, non-public values set from the environment). Imports nothing from `core/` or the subdomains. | `core/`, `comms/` | Stays `common/`: the incident settings tree and vocabulary with two or more consumers. |
| [`comms/`](comms/) | Subdomain and plugin (entry point `incident.comms`): `/sre incident status-update` and the status-updates modal (public status updates, written by a responder with optional AI help). See [`comms/README.md`](comms/README.md). | Slack users | Stays `comms/`: grows other comms profiles and status-page publishers behind `StatusPagePublisher`. |
| [`scribe/`](scribe/) | Subdomain and plugin (entry point `incident.scribe`): `/sre incident draft` and `/sre incident summarize`. See [`scribe/README.md`](scribe/README.md). | Slack users | Stays `scribe/`: prompts, templates and incident-specific post-processing over the text-generation capability. |
| [`meet/`](meet/) | Adapter-only sibling: `adapters/google_meet.py` (incident video-call spaces). | legacy `modules/incident` | Video-call creation becomes an own adapter of the `lifecycle/` subdomain, its only consumer. |
| [`response/`](response/) | `settings.py` (`IncidentResponseSettings`, the `[incident_response]` slice: the declare path's Slack ids, the handbook id, a non-public value set from the environment, and the upgrade job's `upgrade_mode`, `upgrade_interval_minutes` and `upgrade_lease_ttl_seconds`); `plugin.py`, the entry point `incident.response` (the module, not the package, because the host configuration phase and the legacy modules read `settings.py` before plugins load): it requires the Slack and Google Workspace tenants and registers the incident legacy upgrade job unless `upgrade_mode` is `off`; `legacy_upgrade_job.py`, one run of that job (one service scope, `build_legacy_upgrade` from `core/api.py`). | legacy `modules/incident`; the host configuration phase (`settings.py`) | The response subdomain: the rebuild of declare, status, roles and the live incident moves in (TASK-145.7, 145.8). |
| [`postmortem/`](postmortem/) | Settings only: `settings.py` (`IncidentPostmortemSettings`, the `[incident_postmortem]` slice: the retro calendar id, a non-public value set from the environment). No hookimpl, not an entry point. | legacy `modules/incident` | The postmortem subdomain: the retro meeting and the report move in (TASK-145.10, 145.11). |
| [`scheduling/`](scheduling/) | Feature-owned calendar code: `adapters/google_calendar.py` and `availability.py` (free/busy computation for the retro). | legacy `modules/incident` | Becomes the `calendar` workplace capability in `app/capabilities/calendar/` (TASK-138); the retrospective subdomain consumes it and owns no calendar adapter. |

Units the decision record names that do not exist yet:

| Target, not yet created | Holds |
| --- | --- |
| `lifecycle/` (entry point `incident.lifecycle`) | Declare, status, show and update, roles, archive, timeline capture, canvas, recreate resources, the alert buttons, and the stale-channel nudge job (TASK-38). |
| `retrospective/` (entry point `incident.retrospective`) | Attendee selection, availability search and the retro meeting through the calendar capability; later rescheduling, reminders and action items. |
| `features/incident/` | Where this whole umbrella moves (TASK-124.5). |

## Rules that hold today

- **Layers.** The import-linter contract `incident-umbrella` in
  `app/pyproject.toml` puts `comms | documents | drive | meet | postmortem | response | scheduling | scribe`
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
  `drive`, `meet` and `scheduling` as standalone folders; they are tolerated
  until their migration slices.

## Legacy upgrade run procedure

The incident legacy upgrade job upgrades every incident item without `record_version` to the
end-state shape (`core/legacy_upgrade.py`; decisions/incident-management.md, Migration). It is
registered by `response/plugin.py` and ships with `[incident_response] upgrade_mode = "off"`, so
nothing runs until an environment switches it on in its own configuration file.

- **When.** The first run in an environment follows TASK-145.8's deploy there: the upgrade writes
  status, severity, `security_incident` and the two legacy roles in their end-state form, and
  TASK-145.8 removes the last legacy reader of those attributes. Run it again after TASK-145.12
  removes the sheet import, the last legacy writer. Running it, with a report of nothing pending,
  is a precondition of TASK-145.9 merging.
- **Where it runs.** `[scheduler] enabled` must be true (production sets it). The job is a
  leased interval job: one replica runs it, every `upgrade_interval_minutes` (30), under a lease
  of `upgrade_lease_ttl_seconds` (900). The first run is one interval after the task starts, so
  every deploy restarts that wait; to see a report sooner, lower the interval in the same change.
- **Dry run first, per environment.** A PR sets `upgrade_mode = "dry_run"` under
  `[incident_response]` in that environment's file (production: `config/production.toml`, which
  the deploy workflow ships; never a console change). After the deploy, read the
  `incident_legacy_upgrade_report` event: `pending`, `unmatched_status`, `unreadable`, `dropped`
  and `tenant_check` (the verified tenant, or a message naming the expected and received ids). The first production dry run confirms the
  `auth.test` org-token shape (D10 of TASK-145.5.7): `tenant_check` is verified; a mismatch is
  fixed in configuration (`[slack.tenant] enterprise_id`), not in code.
- **A blocked dry run.** Any unmatched status or unreadable item fails the run, logged at error,
  so the error alarm fires on every run. Switch the mode back to `off`, fix the listed items by
  hand in the table, then dry run again.
- **Apply.** A PR sets `upgrade_mode = "apply"`. Confirm that a later report shows `pending` 0
  (a run cut short by throttling ends `write_failed`, and the next run resumes: every write is
  guarded on `record_version` absent), then a PR sets the mode back to `off`.
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
| A resource interface two or more subdomains need (conversation, report, product catalogue, external case) | `core/api.py` + one adapter per system in `core/adapters/` | Adapters are selected by the stored reference, never by a setting. |
| An interface only one subdomain needs | That subdomain's `adapters/` | Moves to `core/` when a second consumer appears. |
| Reading what was said in an incident channel | Use `IncidentTranscriptReader` from `core/api.py` | Do not read Slack history in a subdomain. |
| Google Docs, Drive or Meet operations for an incident | `core/adapters/google_docs.py`; not `meet/` | Report and Drive work goes behind the `IncidentReport` interface over that adapter (TASK-145.6.2); video calls target `lifecycle/`. `meet/` takes fixes, not new operations. |
| Calendar, availability or meeting scheduling | Not `scheduling/` | The `calendar` capability (TASK-138); the incident side of the retro goes to `retrospective/`. |
| Declare, status, roles, archive, timeline, canvas, alert buttons, nudges | `lifecycle/` (target) | Rebuilt surface by surface in TASK-38; until then that behaviour is in legacy `modules/incident`. |
| Retro attendees, retro meeting, retro action items | `retrospective/` (target) | Expansion drafts under TASK-97. |
| Settings or constants shared by two or more incident subdomains | `common/` (target) | A setting with one consumer stays in that subdomain's `settings.py`. |
| An external case platform (for example DFIR-IRIS) | `ExternalCaseRecorder` (target) in `core/api.py`, adapter in `core/adapters/<system>.py`, client in `app/integrations/<system>/` | Never an `app/infrastructure/` capability. |
