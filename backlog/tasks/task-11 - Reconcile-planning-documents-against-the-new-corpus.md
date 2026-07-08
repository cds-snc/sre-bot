---
id: TASK-11
title: Reconcile planning documents against the new corpus
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - governance
  - phase-1
milestone: m-1
dependencies:
  - TASK-10
references:
  - ADR-REVIEW-AND-MIGRATION-PLAN.md
priority: medium
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The root-level analysis documents (ADR-REVIEW-AND-MIGRATION-PLAN.md, architecture-progress-assessment.md, shield-pattern-assessment-analysis.md, claude-research-outcome.md) predate or straddle the new decisions/ corpus and still describe some now-resolved gaps as open (e.g. "transport-slack.md does not exist" - it now does).

Steps:
1. Move the four documents into docs/history/ (or another agreed archive location) with a dated header noting they are point-in-time analyses superseded by decisions/ + the backlog.
2. Where a document is still load-bearing (the migration plan sections referenced by backlog tasks), add a short preface mapping its phases to the backlog milestones instead of rewriting it.
3. Remove tmp.json and other stray analysis artifacts from the repo root if unneeded (plugins-sequence.png, docs/sequenceDiag*.* - confirm with maintainer before deleting).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Repo root contains no unarchived analysis documents; each archived doc carries a superseded-by preface
- [ ] #2 No document in the repo asserts a decision record is missing that now exists in decisions/
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 PR merged; backlog task references still resolve (refs updated to new paths)
- [ ] #2 Maintainer confirmed the disposition of stray artifacts before deletion
<!-- DOD:END -->
