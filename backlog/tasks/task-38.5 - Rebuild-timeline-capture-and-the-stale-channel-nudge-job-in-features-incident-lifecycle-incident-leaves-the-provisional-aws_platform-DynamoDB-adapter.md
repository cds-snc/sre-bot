---
id: TASK-38.5
title: >-
  Rebuild timeline capture and the stale-channel nudge job in
  features/incident/lifecycle; incident leaves the provisional aws_platform
  DynamoDB adapter
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
updated_date: '2026-10-08 15:01'
labels:
  - migration
  - phase-5
  - incident
milestone: m-5
dependencies:
  - TASK-38.4
  - TASK-36.3
  - TASK-64
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - decisions/reliability.md
parent_task_id: TASK-38
priority: medium
ordinal: 310000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of TASK-38 (migrate, third lifecycle slice). Rebuilds the floppy-disk reaction_added and reaction_removed handlers (message captured into the report's timeline and into the record's timeline entries; removal deletes both), the ack-only reaction fallbacks, and the notify_stale_incident_channels job, then deletes modules/incident/db_operations.py.

JOB: registered by lifecycle through the register_background_jobs hookimpl with its schedule, Tier-2 classification and lease TTL from the lifecycle settings slice (reliability.md, the TASK-65 pattern); the hand-import in app/jobs/scheduled_tasks.py is deleted. Stale detection reads the store (incidents with no timeline entry or status change for the configured window), not a channel-name regex; the nudge message carries the archive action id and the schedule-retro action id from common/vocabulary. Safe to run twice.

EXIT FROM aws_platform: after this slice no module under app/modules/incident imports db_operations or packages.aws_platform; the seam baseline entries for incident are removed, which is the condition TASK-88 needs to dissolve packages/aws_platform.

Legacy registrations and the job hand-import are removed in the same PR; pinned by TASK-36.1 (reactions) and TASK-36.3 (job).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 reaction_added and reaction_removed with the floppy-disk emoji write and delete a timeline entry on the record and the matching entry in the report; both are handled by features/incident/lifecycle
- [ ] #2 notify_stale_incident_channels is registered by a lifecycle register_background_jobs hookimpl with Tier-2 lease and TTL from the lifecycle settings slice; the hand-import in app/jobs/scheduled_tasks.py is gone; running the job twice in one window posts one nudge per incident
- [ ] #3 modules/incident/db_operations.py is deleted; no module under app/modules/incident imports packages.aws_platform; the aws_platform seam baseline has no incident entry
- [ ] #4 The TASK-36.1 and TASK-36.3 pinning tests for these surfaces are green before and after the cutover with no assertion change
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; no baseline grew; the seam baseline only shrank
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Legacy incident rows still carry the incident_updates attribute (every row has it, mostly an empty list; two incidents have real text). TASK-140.7 leaves the data in place and the Incident model ignores the key on read. Decide its fate here: drop, backfill or carry over.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 20:51
---
2026-10-02 production bug fix on the legacy floppy-disk handlers. It is a stopgap; this slice replaces it. Carry these findings into the plan.

BUG: one saved message appeared 4 times in the incident report timeline. The handler rewrites the whole timeline section by index from a document read. Several runs for the same message each read the document before the previous write was visible, and each applied its full rewrite. What fired 4 runs was not established (Slack redelivery or repeated clicks while nothing appeared).

STOPGAP NOW IN modules/incident (to delete with the legacy handlers):
- incident_document.update_timeline_section(document_id, rewrite): one snapshot per attempt for text, indexes and revision; the write is guarded by writeControl.requiredRevisionId; a rejected or timed-out write re-reads and re-evaluates; at most TIMELINE_UPDATE_ATTEMPTS = 3, a module constant, not a setting.
- incident_conversation.rearrange_by_datetime_ascending keeps one entry per (timestamp, permalink), so the next save in a channel collapses whole-line duplicates left by the bug.
- get_timeline_section and replace_text_between_headings are gone; extract_timeline_section and build_timeline_replacement are their pure replacements.
- Tests: app/tests/unit/modules/incident/test_incident_timeline_update.py runs both handlers against an in-memory document that enforces the revision guard.

WHAT THE REBUILD SHOULD SETTLE (not fixed by the stopgap):
- Source of truth. AC#1 already puts timeline entries on the record. Render the report section from the record's entries (keyed by channel and message ts) instead of parsing the document back into entries; that makes a save idempotent by key and removes the text round trip.
- Event dedupe. The handlers act on every reaction_added delivery and on every user who adds the reaction. Decide whether a (channel, message ts) claim through the idempotency primitive is needed once the record is the source of truth.
- Concurrent human edits. requiredRevisionId also rejects the write when a person types in the report between the read and the write. Three attempts cover it today; a busy document can exhaust them and the save is dropped with only an error log.
- Timeout. The rewrite sends about three requests per entry and can exceed GOOGLE_API_TIMEOUT_SECONDS (10 s) on a long timeline. The timeout is out of scope for TASK-87; decide here whether to write only the changed entry or to give this write a longer timeout.
- Index units. build_timeline_replacement counts Python characters, the Docs API counts UTF-16 code units, so a message with an emoji outside the BMP shifts every later index. packages/incident/scribe already handles this.
- Unmatched entries. The fallback branch inserts the whole remaining text for each entry that fails the pattern.
- User feedback. A failed save is only logged; the user sees nothing and tends to click again.
---
<!-- COMMENTS:END -->
