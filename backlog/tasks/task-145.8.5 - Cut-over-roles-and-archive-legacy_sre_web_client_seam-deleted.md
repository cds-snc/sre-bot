---
id: TASK-145.8.5
title: Cut over roles and archive; legacy_sre_web_client_seam deleted
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-16T15:51:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.7.2
  - TASK-145.8.1
  - TASK-145.8.2
references:
  - decisions/incident-management.md
  - decisions/migration.md
  - decisions/transport-slack.md
parent_task_id: TASK-145.8
priority: medium
type: feature
ordinal: 510000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L7a. Five roles on the record, purpose from the record, no Drive role properties; archive button incident.response.archive with archive_channel as a legacy alias (L1); one Sentinel event, none on a refused archive (migration.md cutover bug-fix rule added here); the roles purpose output kept as pinned. legacy_sre_web_client_seam and baseline line 20 deleted once no pin requests it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The roles and archive pins pass with assertions unchanged; the seam fixture and its baseline entry are gone (checks parent ACs #2, #4, #10 and the bug-fix AC)
- [ ] #2 The Sentinel-once and silent-refusal fixes are named changes of kind (a) under decisions/migration.md step 4 (amended by TASK-145.8.4), each pinned and listed in the PR body
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [ ] #4 The PR body states the revert target: one git revert restores the legacy surface, and the L5r rollback guard (TASK-145.8.2) keeps it reading and writing upgraded items correctly (decisions/incident-management.md Migration rule 1)
- [ ] #5 close_incident is repointed through response's change_status; modules/incident/incident_status.py, its tests and incident_document.update_incident_document_status are deleted (moved from TASK-145.8.4, OQ1 2026-11-16)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): the migration.md amendment (step 4 named changes of kinds a-d, rule 1 planned legacy edits, rule 2 modules may import features/capabilities one-way, per-command 'never both', Consequences) rides with L6b; this task applies kind (a) instead of adding the bug-fix rule.

---
<!-- COMMENTS:END -->
