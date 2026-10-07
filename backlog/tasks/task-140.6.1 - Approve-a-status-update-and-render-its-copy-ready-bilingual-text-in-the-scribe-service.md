---
id: TASK-140.6.1
title: >-
  Approve a status update and render its copy-ready bilingual text in the scribe
  service
status: To Do
assignee: []
created_date: '2026-10-07 18:52'
updated_date: '2026-10-07 19:02'
labels:
  - incident
dependencies:
  - TASK-140.10.2
parent_task_id: TASK-140.6
priority: high
type: feature
ordinal: 337000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Platform-neutral slice of TASK-140.6, no Slack code. Adds StatusPagePublisher (scribe/publisher.py) with a pure render_copy_ready(update, labels_en, labels_fr) that TASK-140.8 reuses, the copy-ready adapter (scribe/adapters/copy_ready.py), and get_draft_for_review plus approve_status_update (scribe/status_update_approval.py). Approval: all four fields in each language non-blank after trim; target must be the latest record, a DRAFT, at the given sequence; stage may not be below the latest non-draft record's stage; next_update_at recomputed only when the stage changes; StatusUpdateStore.transition(..., expected_state=DRAFT) to APPROVED with approver, approved_at, en, fr, stage. A repeated identical submit is success; a different concurrent approval is PERMANENT_ERROR STATUS_UPDATE_CONFLICT. Approval stops at APPROVED: no PUBLISHED write. Copy-ready text is structured plain text (label lines, a blank line between sections) that pastes cleanly into plain-text and Markdown targets.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 approve_status_update stores APPROVED with approver, approved_at and the edited EN, FR and stage, and never sets PUBLISHED
- [ ] #2 Blank or whitespace-only fields in either language are refused before any write, naming the fields
- [ ] #3 A stage below the latest approved stage, a stale sequence or a non-draft target is refused; a repeated identical submit succeeds; a different concurrent approval returns STATUS_UPDATE_CONFLICT
- [ ] #4 The copy-ready publisher returns EN and FR structured plain text identical to render_copy_ready, with no side effects
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
