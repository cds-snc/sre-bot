---
status: Accepted
date: 2026-10-09
applies: target
scope: Who is on call, where schedules come from, and how the incident feature and the Slack usergroup sync consume them.
---

# On-Call

## Context

`packages/oncall_sync` reads Opsgenie schedules and self-managed rotations and writes the current people into Slack usergroups every five minutes (`rotations.json`, user token per [service-accounts.md](service-accounts.md)). It imports `packages.user_rotations` in three places (`providers.py`, `__init__.py`, `ports.py`), a live breach of "features never import each other". `packages/user_rotations` holds the self-managed rotation logic, one JSON file per rotation, with Slack handlers under `platforms/`. The incident declare flow invites on-call people from a product's Opsgenie schedule reference held in the product catalog. Opsgenie is used by a small subset of teams, its vendor ends the service on 2027-04-05, and no replacement has been chosen. TASK-123 planned `user_rotations` as a `rotations` capability on its own, which would have left "who is on call" split between a capability and a feature.

## Decision

**On-call is a capability**, `app/capabilities/oncall/`. "Who is on call for this schedule right now" has a vocabulary free of any feature, two consumers (incident at declare, the usergroup sync) and vendors behind it, which is [plugin-architecture.md](plugin-architecture.md)'s test. Its public surface is `api.py`: an `OnCallLookup` interface (who is on call now for a schedule reference; the schedule's members), the domain types `Schedule`, `Rotation`, `Shift`, `OnCallPerson` (a person reference, [people-and-accounts.md](people-and-accounts.md)) and `ScheduleReference` (system and id), and the provider function.

**Schedule sources are adapters selected by the reference's system, never by a setting.** Two ship: `opsgenie` (over the client of TASK-25.6, the only importer of `integrations.opsgenie`, marked with its end date) and `rotations` (the self-managed weekly rotations from `user_rotations`, which is deleted as a package). The capability works in full with the self-managed source alone. Growing that source into schedules with shifts, overrides and an escalation chain is the fallback for Opsgenie's end and is an optional enhancement (DRAFT-12), not built before the organisation decides on a replacement.

**Consumers.** `features/oncall_sync/` stays a feature: projecting who is on call into Slack usergroups is organisation configuration over a workplace system. It consumes `capabilities.oncall.api` and owns no schedule adapter. The incident `response` subdomain asks the capability who is on call for the product's `ScheduleReference` at declare and invites them; a missing or failing source invites nobody and says so, never failing the declare.

**Paging is not on-call.** Notifying the person on call is the notifications capability's concern; this capability answers who, not how to reach them.

## Consequences

- Replacing Opsgenie touches one adapter and no feature; the incident umbrella carries no Opsgenie vocabulary.
- `user_rotations`' Slack commands become the capability's own entry points, the one case where a capability has `entrypoints/`.
- Cost: the self-managed source is thin today; teams that leave Opsgenie before DRAFT-12 lands get weekly rotations without overrides or escalation.

## Checks

- import-linter: `integrations.opsgenie` is imported only by `capabilities/oncall/adapters/opsgenie.py`; `features/oncall_sync` and `features/incident` import the capability only through `capabilities.oncall.api`.
- grep: no module outside `capabilities/oncall/` names Opsgenie or a rotation file format.
- Test: the lookup selects the adapter from `ScheduleReference.system`; the in-memory fake covers both sources.
- Boot test: with no Opsgenie settings the capability registers and the self-managed source answers.

## Migration

Tickets: TASK-146 (the capability, `oncall_sync` over it, incident declare through it), after TASK-25.6 (Opsgenie client) and TASK-114 (the capabilities directory and shape check). TASK-123 and TASK-124.2 are superseded by it.

Tolerated until then:
- `packages/oncall_sync` importing `packages.user_rotations` and holding its own Opsgenie adapter and `ports.py`;
- `packages/user_rotations` as a feature with `platforms/`;
- the product catalog holding an Opsgenie-specific schedule value and the legacy declare flow calling Opsgenie directly.

**Changes:**
- 2026-10-09: Accepted (TASK-146). On-call is a capability with two schedule sources; rotations are a source, not a capability; Opsgenie's end is a one-adapter change.
