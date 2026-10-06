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
| [`core/`](core/) | Shared kernel. `api.py` exposes `IncidentTranscriptReader`, `TranscriptMessage` and `get_incident_transcript_reader`; `adapters/slack.py` is the Slack transcript reader; `domain.py` holds the shared domain types. No hookimpl, not an entry point. | `scribe/` | Stays `core/`. Grows the incident record and `IncidentStore`, the two-part command check (`find_incident_for_conversation`, `conversation_is_writable`) and the resource interfaces with two or more subdomain consumers (`IncidentConversation`, `IncidentReport`, `ProductCatalog`, `ExternalCaseRecorder`), each with one adapter per system in `core/adapters/`. |
| [`scribe/`](scribe/) | Subdomain and plugin (entry point `incident.scribe`): `/sre incident draft` and `/sre incident summarize`. See [`scribe/README.md`](scribe/README.md). | Slack users | Stays `scribe/`: prompts, templates and incident-specific post-processing over the text-generation capability. |
| [`documents/`](documents/) | Adapter-only sibling: `adapters/google_docs.py` (incident report Google Docs operations) and `utils.py` (Docs URL id extraction). | legacy `modules/incident` | Absorbed into the `IncidentReport` Google Docs and Drive adapter in `core/adapters/` (TASK-38.2, TASK-38.3). |
| [`drive/`](drive/) | Adapter-only sibling: `adapters/google_drive.py` (incident folders, files and Drive `appProperties` metadata). | legacy `modules/incident`, `jobs/scheduled_tasks.py` | Absorbed into the same `IncidentReport` adapter in `core/adapters/` (TASK-38.2, TASK-38.3). Roles leave Drive properties for the incident record (TASK-38.4). |
| [`meet/`](meet/) | Adapter-only sibling: `adapters/google_meet.py` (incident video-call spaces). | legacy `modules/incident` | Video-call creation becomes an own adapter of the `lifecycle/` subdomain, its only consumer. |
| [`scheduling/`](scheduling/) | Feature-owned calendar code: `adapters/google_calendar.py` and `availability.py` (free/busy computation for the retro). | legacy `modules/incident` | Becomes the `calendar` workplace capability in `app/capabilities/calendar/` (TASK-138); the retrospective subdomain consumes it and owns no calendar adapter. |

Units the decision record names that do not exist yet:

| Target, not yet created | Holds |
| --- | --- |
| `lifecycle/` (entry point `incident.lifecycle`) | Declare, status, show and update, roles, archive, timeline capture, canvas, recreate resources, the alert buttons, and the stale-channel nudge job (TASK-38). |
| `retrospective/` (entry point `incident.retrospective`) | Attendee selection, availability search and the retro meeting through the calendar capability; later rescheduling, reminders and action items. |
| `common/` | Incident settings tree and no-I/O vocabulary with two or more consumers: status values, action ids one subdomain renders and another handles, and the new-incident system-selection policy setting. |
| `features/incident/` | Where this whole umbrella moves (TASK-124.5). |

## Rules that hold today

- **Layers.** The import-linter contract `incident-umbrella` in
  `app/pyproject.toml` puts `documents | drive | meet | scheduling | scribe`
  above `core`, with `exhaustive = true`: siblings never import each other, and
  `core/` imports none of them. A new folder must be added to that contract.
- **`core/` through `core/api.py` only.** Subdomains import
  `packages.incident.core.api`, never `core.adapters` or `core.domain`.
- **Subdomains are plugins; `core/` never is.** A subdomain registers through
  pluggy hookimpls in its `__init__.py` and one line under
  `[project.entry-points.sre_bot]` in `app/pyproject.toml`
  ([`decisions/plugins.md`](../../../decisions/plugins.md)). The umbrella and
  `core/` have no hookimpl and no entry point.
- **No new adapter-only siblings.** The decision record rejects `documents`,
  `drive`, `meet` and `scheduling` as standalone folders; they are tolerated
  until their migration slices.

## Where does new work go

| You are adding… | Put it in | Notes |
| --- | --- | --- |
| A new AI-assisted text use case over the incident transcript or report (a new draft, summary or rewrite) | `scribe/` | Follow [Adding a use case](scribe/README.md#adding-a-use-case). |
| A change to `/sre incident draft` or `/sre incident summarize` | `scribe/` | See the at-a-glance table in [`scribe/README.md`](scribe/README.md). |
| A resource interface two or more subdomains need (conversation, report, product catalogue, external case) | `core/api.py` + one adapter per system in `core/adapters/` | Adapters are selected by the stored reference, never by a setting. |
| An interface only one subdomain needs | That subdomain's `adapters/` | Moves to `core/` when a second consumer appears. |
| Reading what was said in an incident channel | Use `IncidentTranscriptReader` from `core/api.py` | Do not read Slack history in a subdomain. |
| Google Docs, Drive or Meet operations for an incident | Not `documents/`, `drive/` or `meet/` | Report and Drive work targets the `IncidentReport` adapter in `core/adapters/`; video calls target `lifecycle/`. The siblings take fixes, not new operations. |
| Calendar, availability or meeting scheduling | Not `scheduling/` | The `calendar` capability (TASK-138); the incident side of the retro goes to `retrospective/`. |
| Declare, status, roles, archive, timeline, canvas, alert buttons, nudges | `lifecycle/` (target) | Rebuilt surface by surface in TASK-38; until then that behaviour is in legacy `modules/incident`. |
| Retro attendees, retro meeting, retro action items | `retrospective/` (target) | Expansion drafts under TASK-97. |
| Settings or constants shared by two or more incident subdomains | `common/` (target) | A setting with one consumer stays in that subdomain's `settings.py`. |
| An external case platform (for example DFIR-IRIS) | `ExternalCaseRecorder` (target) in `core/api.py`, adapter in `core/adapters/<system>.py`, client in `app/integrations/<system>/` | Never an `app/infrastructure/` capability. |
