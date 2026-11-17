# incident.response

The responders' subdomain while an incident is open (decisions/incident-management.md). It
rebuilds the legacy `modules/incident` surfaces one cutover at a time (TASK-145.7, 145.8).

## Commands

| Command | Does | Code |
| --- | --- | --- |
| `/sre incident status update <status>` | Changes the status of the channel's incident: the record, then the report's status line, the incident list's status cell and a notice in the incident channel. One private reply names the outcome and any write that was skipped or failed. | `entrypoints/slack.py`, `service/status.py` |
| `/sre incident status`, `status show` | The command's help. A bare valid status (`status Closed`, retired after 2025-11-01) answers a pointer to `status update` and changes nothing; TASK-145.13 deletes the pointer. | `entrypoints/slack.py` |

## Status changes

`service/status.py` holds `change_status`, the one status engine. The slash command calls it
today; the update modal (TASK-145.8.3) and close (TASK-145.8.5) call it once they are rebuilt.

- The record write is the commit point: a refused command check or a failed record write
  stops and nothing else is written.
- The report line, the list and the channel follow in that order. Each failure is logged
  (`incident_status_stage_failed`) and reported, never rolls the record back, and the next ones
  still run. Running the same status again repairs them.
- The notice goes to the record's conversation, only when the bot can write to it.

## Layout

- `plugin.py`: the entry point `incident.response` (requirements, the new-incident policy
  check, the status commands, the `incident_response` catalogue, the legacy upgrade job).
- `entrypoints/slack.py`: the Slack commands; replies come from `locales/` in the invoker's
  locale.
- `service/status.py`: `change_status`.
- `providers.py`: the core report, list projection and conversation the services write
  through; tests substitute them here.
- `settings.py`, `legacy_upgrade_job.py`: see the umbrella README.
