# On-call

Who is on call for a schedule right now, and the schedule's shifts, in feature-free vocabulary.
`api.py` exposes `OnCallLookup` (`on_call_now`, `get_schedule`, `list_schedules`, each returning an
`OperationResult`), the domain types (`ScheduleReference`, `Schedule`, `Rotation`, `Shift`,
`OnCallPerson`, `Account`), the provider `get_oncall_lookup()` and the synchronous config-time
accessor `configured_rotations()`.

The source is chosen by `ScheduleReference.system`, never by a setting: `rotations` (self-managed
weekly rotations) and `opsgenie` (over the async Opsgenie client). An unknown system returns
`ADAPTER_NOT_FOUND`. With no Opsgenie settings the capability registers and the self-managed
source answers.

Opsgenie support ends 2027-04-05 (decisions/oncall.md): `adapters/opsgenie.py` is the only module
that imports `integrations.opsgenie`, besides the host's settings reads in `server/`.

## Self-managed rotations

A lightweight alternative to Opsgenie for non-critical uses, like tracking who merges dependency
updates this week or who answers user inquiries. Create one JSON file per rotation in
`adapters/rotation_files/` (in-code rosters are tolerated until they become managed content,
decisions/organisation-content.md):

```json
{
  "slack-usergroup-handle": "canadalogin-website-atc",
  "slack-usergroup-name": "CanadaLogin Website ATC",
  "members": ["U01234567", "U07654321"],
  "rotation_type": "weekly",
  "weeks_per_shift": 1,
  "rotation_start": "2026-09-14T09:00:00-04:00"
}
```

`members` is a list of Slack user IDs. The first member starts at `rotation_start`, and each member
receives `weeks_per_shift` weeks before the next member is selected. `rotation_type` supports only
`weekly`. Adding, removing, or reordering members changes subsequent assignments.

Every five minutes, `packages/oncall_sync` reads the current assignment through `api.py` and
updates the Slack UserGroup named by `slack-usergroup-handle`, creating it when missing.

### Slack commands

- `/sre rotations` or `/sre rotations help`: List user-rotation commands.
- `/sre rotations view <usergroup-handle>`: Open the current and next 12 weeks of shifts.

## Classification

generic

## Feature consumers

- features.incident.response

Prose consumers: `packages.oncall_sync` reads the self-managed rotations through `api.py` (its
Opsgenie schedules move onto the capability in TASK-146.2), and the coordination feature (planned,
doc-15 E5).
