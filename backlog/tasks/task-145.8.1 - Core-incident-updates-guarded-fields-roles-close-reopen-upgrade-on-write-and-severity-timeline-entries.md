---
id: TASK-145.8.1
title: >-
  Core incident updates: guarded fields, roles, close, reopen, upgrade-on-write
  and severity timeline entries
status: In Progress
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T17:10:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.4
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 506000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L3 (approved program in TASK-145.7's plan, section 2; slices in TASK-145.8's plan). IncidentStore gains update_fields, set_roles, close and reopen through upgrade-on-write (plan section 3), and the timeline store (timeline_table, entry_key, ids) with a severity_changed system entry written after the field update. Inert until the cutovers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Guarded update, lost guard (one re-read and retry, then a classified conflict), upgrade-on-write in one pass (binding + marker 2), unreadable legacy item refused with the field named, close/reopen bucket rules, replay of the same change (tested; checks parent AC #7 and the upgrade-on-write AC)
- [x] #2 A severity change appends one timeline entry with a deterministic id after the field update; a failed entry never rolls the field back (tested; checks the severity AC)
- [x] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [x] #4 TimelineStore.append in core/store.py over sre_bot_incident_timeline (timeline_table, entry_key '<posted_at>#<entry_id>'), record store and fake; replaying an entry writes nothing (tested; takes TASK-145.9 AC #5's table, key and append per OQ13)
- [x] #5 plan_item_upgrade writes exactly what the job writes for legacy items (conversation copy, one primary chat binding, record_version 2); no record_version bump (item_upgrade tests unchanged; upgrade-on-write equality test)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-10 (human, as written). Stack L L3, stacked on L5 (stack-l/task-145.7.7-incident-create, #1845); branch stack-l/task-145.8.1-core-updates (human: gh stack add). Inert: no surface calls these operations until L6a-L7b. Builds on L2a/L2b/L5 as shipped (create puts the record only; attach_conversation; set_reference guarded on record_version; INCIDENT_RECORD_CONFLICT; zero or more chat bindings, the API needs none).

## 0. Rulings (human, 2026-11-10)
- Size: kept whole under an approved size exception (~530 production LOC / 6 files incl. docstrings; the timeline store pulled in by OQ13 is the overrun). Not decomposed.
- Retro link: IncidentChanges carries no retrospective link. L6a (TASK-145.8.3) drops "Retro Link" from show and the update modal as a named behaviour change and updates the field-update pin; legacy retrospective_url values stay on the items (Migration rule 5); the bridge already skips it (TASK-145.5.8); the postmortem_meeting reference set by TASK-145.10 replaces it. The record holds typed references only (decisions/incident-management.md:32).

## 1. Program-scope assessment (no other open question)
- Upgrade on write: decided, decisions/incident-management.md:138-139 (rules 3-4: same function, same guard, one update with the change; side records first, marker last). TASK-145.8 plan section 3 (approved 2026-11-09).
- Severity entry: decided, incident-management.md:28 (each change a timeline entry) and :34 (guarded field update then an entry with a deterministic id; a failed entry is logged and retried, never rolls the field back). Entry shape was a gap: section 3 below (typed kind + structured change, rendered at read time); current practice: incident.io records a severity change as a typed field of an incident update (new_severity / to_severity_id, https://docs.incident.io/api-reference/incident-updates-v2.md) and keeps timeline items as their own typed records (https://docs.incident.io/api-reference/incident-timeline-items-v2.md); PagerDuty log entries carry a type per entry (trigger, acknowledge, assign, annotate; https://hexdocs.pm/pagerduty/PagerDuty.LogEntry.html).
- Timeline records under the incident, never a list attribute: decided, incident-management.md:32, check :114. Table sre_bot_incident_timeline, partition incident_id, sort entry_key '<posted_at>#<entry_id>' exists (terraform/dynamodb.tf:153, IAM :309, config/base.toml:200, common/settings.py:36); nothing writes it today. OQ13 (approved with the program, 2026-11-09) moved TASK-145.9 AC #5's table, key and append into L3; captured_entry_id (uuid5 over the captured message) stays with its first user L10b (TASK-145.9.2), reusing this task's namespace.
- Security flag editable by the coordinator: decided, incident-management.md:38; who may flip it is L6a's authorization.
- Status vocabulary and Closed: decided (common/vocabulary.py:9-21 is_open); the open index rule (open_bucket/opened_at) is the record's (incident_items.py:158-176).
- Lost guard error code: reuse INCIDENT_RECORD_CONFLICT (contracts/operations/codes.py:68), PERMANENT_ERROR, after one internal re-read and retry; no new code (one stable 409-class code per record; the store message widens to "changed by another writer or not in the shape this writer owns").
- Unbound open legacy item (plan_item_upgrade returns UnboundOpenItem): refused like an unreadable item (field "conversation"), as the job lists it for a hand fix; legacy items always carry a channel (TASK-145.7.8 notes), so none is expected. R4-R6 (zero bindings) concern new incidents only; changing the job's rule would change what it writes, which this task must not do.
- Upcoming rows checked: L6a/L6b/L7a/L7b consume update_fields/set_status/set_roles/set_reference; L10b appends captured entries through TimelineStore; TASK-165.5 (doc-15 E7) child incidents have their own records and timeline, no shared entry; TASK-145.9.4 renders entries (unknown kind rendered with a labelled fallback, never acted on). No doc-11/doc-15/doc-16 row conflicts.

## 2. Stored shape: unchanged (record_version stays 2)
L3 writes only attributes the v2 shape already has (title, severity as int, detected_at/impact_started_at/impact_ended_at as format_stored_time text, security_incident, the five role attributes, status, open_bucket, opened_at). plan_item_upgrade writes exactly what the job writes for legacy items (conversation copy, one primary chat binding, record_version 2); L3 only renames its private _guard_value to guard_value for reuse (no behaviour change; test_incident_core_item_upgrade_plan.py unchanged). No record_version bump. Timeline items are a new record type with no prior writer.

## 3. Domain-model gate
Changed: TimelineEntry (core/domain.py:357), never stored yet (only test_incident_core_timeline_entry_record.py and the api surface use it). New: TimelineEntryKind, SeverityChange, IncidentChanges.
- Scenario matrix: severity set at declare-time later (unset -> SEV2), raised (SEV3 -> SEV1), cleared (SEV2 -> unset), same value replayed (no entry), changed twice within a second by two people (two entries, distinct ids since from/to differ; same from/to/time is the same change), captured message (L10b, kind message with source_message), manual note (kind message, no source), child incident of a coordinated incident (own record, own timeline), future system kinds (attach failure per incident-management.md:34, status change) added as new kinds.
- Cardinality: entries per incident 0..n; one entry per severity change; author one person; entry belongs to exactly one incident (visibility is the incident's).
- Chosen: one TimelineEntry type with kind (StrEnum: message, severity_changed) and typed payload severity_change: SeverityChange | None (previous, current: Severity | None, must differ); text required non-blank for message, empty for system kinds (rendered per locale at read time, never stored in one language). Rejected: free text only (loses data, one language); a separate SeverityChangeEntry record type (same lifecycle, ownership, visibility and table: reuse by semantics). Unknown stored kind: display-only taxonomy, a reader renders a labelled fallback (TASK-145.9.4); no command acts on entries.
- IncidentChanges: frozen dataclass, each field typed value | None | Keep with Keep.KEEP the default (typed sentinel enum): title (no clear), severity, detected_at, impact_started_at, impact_ended_at, security_incident (no clear). __post_init__: at least one field not KEEP, title non-blank, times aware, severity a Severity or None.

## 4. Steps (files)
1. core/domain.py (~70): TimelineEntryKind, SeverityChange, TimelineEntry.kind (default message) + severity_change with the kind rules; Keep, IncidentChanges.
2. core/adapters/timeline_items.py (new, ~60): TIMELINE_NAMESPACE (uuid5 of a fixed name), entry_key(posted_at, entry_id) = f"{format_stored_time(posted_at)}#{entry_id}", severity_entry_id(incident_id, change, at) = uuid5 over incident id, kind, previous, current and format_stored_time(at), timeline_entry_item(entry): incident_id, entry_key, entry_id, kind, posted_at, author, text when non-empty, source_message map when set, severity_previous/severity_current ints when set.
3. core/adapters/item_upgrade.py (~3): _guard_value -> guard_value (public, reused by the store's guards).
4. core/store.py (~290):
   - timeline_table(name) (partition incident_id, sort entry_key); TimelineStore Protocol append(entry) -> OperationResult[TimelineEntry] (put_if_not_exists; an existing key is a replay, success, nothing written; failures classified as the incident store's); RecordTimelineStore.
   - IncidentStore Protocol: update_fields(incident_id, changes, *, by, at), set_roles(incident_id, roles: Mapping[IncidentRole, str | None]), set_status(incident_id, status, *, at); docstrings state guard, replay, conflict, upgrade on write. Class docstring updated (writes now arrive with 145.7 and 145.8; captured entries with 145.9).
   - RecordIncidentStore gains timeline: TimelineStore (keyword, no default, like bindings). One private _guarded_write(incident_id, operation, desired: Callable[[Incident], list[RecordChange]]) used by all three:
     a. get the raw item (missing -> NOT_AN_INCIDENT; failure classified);
     b. record_version 2: parse; desired changes from the parsed incident; none -> replay, return the stored incident, nothing written; expected = record_version 2 plus guard_value of each changed attribute's raw read value;
     c. otherwise plan_item_upgrade(item, tenants): ItemUpgrade -> put the binding first (put_if_not_exists, replay ok, failure stops before the record), then ONE update: the upgrade's changes merged with the desired ones (desired wins per attribute; a RemoveAttribute drops the upgrade's Set of that attribute), expected = upgrade.expected plus the changed attributes' read values; UnreadableLegacyItem / UnboundOpenItem -> INCIDENT_RECORD_UNREADABLE with the field logged as _end_state logs it; None at a version above 2 -> INCIDENT_RECORD_CONFLICT;
     d. update NOT_FOUND without code -> NOT_AN_INCIDENT; failure classified; data None (lost guard) -> back to a. once, then INCIDENT_RECORD_CONFLICT (log incident_record_changed);
     e. return the parsed updated item.
   - set_status bucket rules: to Closed removes open_bucket and opened_at; Closed to an open status sets open_bucket and opened_at = format_stored_time(at); open to open sets status only.
   - set_roles: only named roles change; None removes the attribute.
   - update_fields: after a successful write that changed severity, append TimelineEntry(kind severity_changed, entry_id severity_entry_id, posted_at at, author by, severity_change(previous, current)); a TRANSIENT_ERROR append is retried once; a failed append logs incident_timeline_entry_failed (incident_id, entry_id) and the field result is returned unchanged.
5. core/adapters/in_memory.py (~90): InMemoryTimelineStore (append idempotent on (incident_id, entry_key); entries(incident_id) for assertions); InMemoryIncidentStore(timeline=None) gains the three operations with the same validation, replay, bucket and severity-entry rules (no version, no lost guard: stated in its docstring).
6. core/api.py (~15): export the new names; build_incident_store passes RecordTimelineStore(records, timeline_table(settings.timeline_table)); docstring names the timeline table. tests/factories/incident.py: record_incident_store gains timeline (defaulting to the configured table).
7. features/incident/README.md: core writes list (update_fields, set_roles, set_status, timeline append).
8. decisions/incident-management.md: change-log line 2026-11-10 (TASK-145.8.1): timeline entries carry a kind with a typed payload, system entries rendered at read time; field writes guarded on record_version and the read values they change, upgrade on write through plan_item_upgrade; retro link not on the record (removed at the show/update cutover; postmortem meeting reference replaces it).

## 5. Test matrix (TDD, failing first; real store parametrized with the fake where behaviour is shared)
- tests/unit/features/incident/core/test_incident_core_incident_store_update_fields.py: field update happy; replay writes nothing; guard holds record_version and the changed attribute's read value (GuardSpy); lost guard once -> retried and succeeds; lost twice -> INCIDENT_RECORD_CONFLICT, record unchanged; missing incident; caller errors (IncidentChanges all KEEP, blank title, naive time) raise.
- ..._update_severity_timeline.py: a severity change appends one severity_changed entry (deterministic id, entry_key, previous/current) after the field update; replay appends none; transient append retried once; failed append logged, field kept.
- ..._upgrade_on_write.py: legacy item -> binding put, then one update carrying the upgrade, the change and record_version 2 (the written item equals the job's plan plus the change); binding failure leaves the item untouched; v1 item raised to 2 with its binding; unreadable legacy item refused, field logged, nothing written; unbound open legacy item refused; item above version 2 -> conflict; set_status Closed on a legacy open item removes the plan's open_bucket/opened_at.
- ..._set_status.py: Open -> In Progress keeps the bucket; -> Closed removes open_bucket and opened_at (leaves list_open); Closed -> Open sets them with opened_at = at; replay no-op.
- ..._set_roles.py: set, replace, clear one role, others untouched; replay no-op.
- test_incident_core_timeline_store_append.py: item shape and key; replay of the same entry writes nothing and succeeds; failure classified.
- test_incident_core_timeline_store_fake.py (fake coverage check).
- test_incident_core_timeline_entry_record.py (extended): kind rules, SeverityChange previous != current.
- test_incident_core_api_build_incident_store.py, test_incident_core_api_surface.py: timeline wiring and exports.

## 6. AC traceability
#1 -> step 4 (a-e, set_status, set_roles), 5 -> update_fields, upgrade_on_write, set_status, set_roles tests. #2 -> steps 1, 2, 4 (update_fields) -> severity_timeline test. #4 -> steps 2, 4 (timeline), 5, 6 -> timeline_store tests. #5 -> step 3 -> item_upgrade tests unchanged + upgrade_on_write equality test. #3 -> gates.

## 7. Blast radius and rollback
Inert: no registered surface calls the new operations; build_incident_store's new timeline argument is the only wiring change (constructs, writes nothing). One git revert restores L5. Once L6a calls them, upgrade on write raises items to version 2 before the job runs (TASK-145.7.8): L5r (TASK-145.8.2) must deploy before L6a (already wired). The upgrade's binding uses the configured Slack tenant (the job also verifies it); a wrong tenant would bind a wrong conversation key, so L6a's PR states production's Slack tenant is configured (it is today, TASK-145.7.8 notes).

## 8. Assumptions and doubts
1. The bridge maps every field L3 writes except the retro link (verified: legacy_items.py maps severity, times, roles, status, security_incident; retrospective_url skipped).
2. DynamoDB rejects two actions on one attribute in one update: the merge in step 4c guarantees one action per attribute (tested with a spy asserting unique attributes).
3. A crash between the field update and the entry append loses that entry (the ADR's retry is in-call); accepted, logged path only for failures; revisit if a durable outbox appears.
4. Size: ~530 production LOC / 6 files incl. docstrings, approved exception (section 0).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (for the full plan): confirm the plan does not change what plan_item_upgrade writes for legacy items (conversation copy, one primary chat binding, record_version 2); any stored-shape change is a record_version bump with its own upgrade step, readers accepting both, and is called out in the plan because it reaches production through upgrade-on-write before the job runs (TASK-145.7.8). Build on L5 as shipped: create puts the record only, attach_conversation, set_reference, INCIDENT_RECORD_CONFLICT, bindings zero or more chat conversations (decisions/incident-management.md Bindings).

2026-11-10 (implementation, TDD on stack-l/task-145.8.1-core-updates): built as planned.
- Domain: TimelineEntryKind (message, severity_changed), SeverityChange (previous != current, members only), TimelineEntry.kind/severity_change with the kind rules (message needs text; system kinds hold no text); Keep + IncidentChanges (named(), validation at construction).
- adapters/timeline_items.py: TIMELINE_NAMESPACE (uuid5 of urn:sre-bot:incident:timeline; fixed for good), entry_key, severity_entry_id, timeline_entry_item. item_upgrade.py: guard_value and UnguardableValueError made public, no behaviour change (item_upgrade tests unchanged).
- store.py: timeline_table, TimelineStore/RecordTimelineStore (put_if_not_exists, replay success); IncidentStore.update_fields/set_roles/set_status; RecordIncidentStore(timeline=) required; one _guarded_write (read, plan, binding put, one update, one re-read on a lost guard, then INCIDENT_RECORD_CONFLICT logged incident_record_changed); upgrade on write merges the plan's changes with the field change (one action per attribute, the change wins); shared pure helpers apply_changes, apply_roles, record_changes, severity_entry, validate_* used by the fake; _store_failure shared by the incident and timeline stores. Conflict message widened to 'changed by another writer or not in the shape this writer owns'.
- A replay on a legacy item writes nothing (no upgrade without a change); the job or the next real change raises it.
- Fake: InMemoryTimelineStore (entries() in key order); InMemoryIncidentStore(timeline=None) with the three writes.
- api.py exports IncidentChanges, Keep, SeverityChange, TimelineEntryKind, TimelineStore; build_incident_store wires RecordTimelineStore on settings.timeline_table. README core row and decisions/incident-management.md change log (2026-11-10, TASK-145.8.1) updated.
- Tests: update_fields, update_severity_timeline, upgrade_on_write, set_status, set_roles, timeline_store_append (fake coverage folded in instead of a separate _fake file), timeline_entry_record extended, api surface/build and constructor tests.
- Size: ~600 production lines added incl. docstrings over 7 code files (domain, store, in_memory, api, item_upgrade, new timeline_items, README) vs the ~530 / 6 estimate; the overrun is store docstrings and the shared helpers the fake reuses.
- Gates (from app/): ruff check . -> All checks passed; ruff format on touched files; lint-imports -> 13 kept, 0 broken; make check-package-shape -> no net-new violations (3 baselined); make check-test-seams -> no net-new (47 / 12 baselined); mypy . -> 41 errors in 14 files, none in touched files (pre-existing: modules/*, features/incident/scheduling, features/incident/meet); pytest tests --ignore=tests/smoke -> 6935 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-10T16:57:00Z

---

Plan approved by the human 2026-11-10 as written (rulings in plan section 0: size exception, retro link dropped at L6a). Implementation starts on stack-l/task-145.8.1-core-updates above L5 (#1845).

---
<!-- COMMENTS:END -->
