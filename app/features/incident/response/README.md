# incident.response

The responders' subdomain while an incident is open (decisions/incident-management.md). It
rebuilds the legacy `modules/incident` surfaces one cutover at a time (TASK-145.7, 145.8).

## Commands

| Command | Does | Code |
| --- | --- | --- |
| `/sre incident status update <status>` | Changes the status of the channel's incident: the record, then the report's status line, the incident list's status cell and a notice in the incident channel. One private reply names the outcome and any write that was skipped or failed. | `entrypoints/slack.py`, `service/status.py` |
| `/sre incident roles manage` | Opens the roles modal (callback `incident.response.roles`): five user pickers, the incident commander and operations lead required, the communications lead, policy lead and postmortem owner optional, preselected from the record. The submission writes the five roles to the record, announces each role whose holder changed and rewrites the channel purpose's `IC: ... / OL: ...` line. | `entrypoints/slack_roles.py`, `service/roles.py` |
| `/sre incident roles`, `roles show` | The command's generated help (the `roles show` stub is retired). | `entrypoints/slack_roles.py` |
| `/sre incident close` and the stale notice's archive button | Closes the channel's incident and archives its channel: joins the channel, sets the status to Closed (the record, the report line, the list and a notice), posts the archived notice, archives the channel and sends one `incident_channel_archived` event. The button is the legacy attachment `archive_channel`, registered as `incident.response.archive` with the alias scoped to its `archive` value; its texts are English then French, since a button press names no locale. | `entrypoints/slack_archive.py`, `service/archive.py`, `adapters/sentinel.py` |
| `/sre incident status`, `status show` | The command's help. A bare valid status (`status Closed`, retired after 2025-11-01) answers a pointer to `status update` and changes nothing; TASK-145.13 deletes the pointer. | `entrypoints/slack.py` |

## Status changes

`service/status.py` holds `change_status`, the one status engine. The slash command and
the archive call it today; the update modal calls it once it is rebuilt (TASK-145.8.3).

- The record write is the commit point: a refused command check or a failed record write
  stops and nothing else is written.
- The report line, the list and the channel follow in that order. Each failure is logged
  (`incident_status_stage_failed`) and reported, never rolls the record back, and the next ones
  still run. Running the same status again repairs them.
- The notice goes to the record's conversation, only when the bot can write to it.

## Roles

`service/roles.py` holds `assign_roles`, the one roles engine; the modal's submission calls it.

- The record write (`IncidentStore.set_roles`, all five roles in one guarded write) is the
  commit point: a refused command check or a failed record write stops and nothing is posted.
- Then, only when the incident's conversation is writable, one announcement per role whose
  holder differs from what the modal showed, in role order, and the purpose's `IC: ... / OL: ...`
  line (`purpose_with_roles`: appended after a space and a newline, or replaced in place, cut to
  250 characters, as the legacy command wrote it). Failures are logged and told to the
  submitter privately, never roll the record back.
- What the modal shows is `read_incident_roles` (`core/api.py`): the record's roles, or for an
  incident with no role on the record the report's Drive properties `ic_id` and `ol_id` through
  the legacy-only `LegacyRolesReader`. Nothing writes those properties. TASK-145.7.12 backfills
  them into the record and TASK-145.13 deletes the reader and the read (`providers.legacy_roles_reader`).

## Archive

`service/archive.py` holds `archive_incident`; `/sre incident close` and the archive button call it.

- Find the conversation's incident (a refusal writes nothing and sends no event), join the
  channel (`IncidentConversation.join`: no call when the bot is a member), then `change_status`
  to Closed: the record write is the commit point.
- A failed join never stops the record: the incident is closed, the archived notice and the
  archive are skipped as `not_joined` and the reply says so.
- Then the archived notice and the archive; `incident_channel_archived` is sent once, only after a
  successful archive, through `adapters/sentinel.py` (`{event, message}` with the incident,
  conversation, user and time only; TODO(TASK-122): the audit capability's sink).

## Layout

- `plugin.py`: the entry point `incident.response` (requirements, the new-incident policy
  check, the status, roles and close commands, the archive button, the `incident_response` catalogue,
  the legacy upgrade job).
- `entrypoints/slack.py`: the status commands and the registration; `entrypoints/slack_roles.py`:
  the roles command and modal; `entrypoints/slack_archive.py`: close and the archive button;
  `entrypoints/scope.py`: the service scope they open. Replies come from `locales/` in the
  invoker's locale, or English then French when the payload names none.
- `service/status.py`: `change_status`; `service/roles.py`: `assign_roles`; `service/archive.py`:
  `archive_incident`.
- `interfaces.py`: `ArchiveEventSink` and `ArchivedEvent`; `adapters/sentinel.py` implements it.
- `providers.py`: the core report, list projection, conversation and legacy roles reader, and
  the archive event sink, the services use; tests substitute them here.
- `settings.py`, `legacy_upgrade_job.py`: see the umbrella README.
