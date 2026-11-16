# On-call

Who is on call for a schedule right now, and the schedule's shifts, in feature-free vocabulary.
`api.py` exposes `OnCallLookup` (`on_call_now`, `get_schedule`, `list_schedules`, each returning an
`OperationResult`), the domain types (`ScheduleReference`, `Schedule`, `Rotation`, `Shift`,
`OnCallPerson`, `Account`), the provider `get_oncall_lookup()` and the synchronous config-time
accessor `configured_rotations()`.

The source is chosen by `ScheduleReference.system`, never by a setting: `rotations` (self-managed
weekly rotations, one JSON file each under `rotations/`) and `opsgenie` (over the async Opsgenie
client). An unknown system returns `ADAPTER_NOT_FOUND`. With no Opsgenie settings the capability
registers and the self-managed source answers.

Opsgenie support ends 2027-04-05 (decisions/oncall.md): `adapters/opsgenie.py` is the only module
that imports `integrations.opsgenie`, besides the host's settings reads in `server/`.

## Classification

generic

## Feature consumers

- features.incident.response

Prose consumers, not yet importing `capabilities.oncall.api`: `packages.oncall_sync` until
TASK-146.2 moves it onto the capability, and the coordination feature (planned, doc-15 E5).
