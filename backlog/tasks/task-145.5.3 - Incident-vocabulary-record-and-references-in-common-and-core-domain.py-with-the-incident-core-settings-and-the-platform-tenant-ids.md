---
id: TASK-145.5.3
title: >-
  Incident vocabulary, record and references in common/ and core/domain.py, with
  the incident core settings and the platform tenant ids
status: To Do
assignee: []
created_date: '2026-10-14 23:09'
labels:
  - incident
  - features
dependencies: []
references:
  - decisions/incident-management.md
  - decisions/workplace-systems.md
  - decisions/people-and-accounts.md
  - decisions/feature-packages.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 389000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 4 of Stack K (handoff doc-13). Additive types and settings; no I/O and no consumer yet.

THIS SLICE
- common/vocabulary.py: IncidentStatus (Open, In Progress, Ready to be Reviewed, Reviewed, Closed; every status except Closed counts as open), Severity (levels 0 to 4, wide because teams use different scales), the five role names, StatusUpdateStage moved from core/domain.py (core/api.py keeps exporting it). common/ imports no adapter, store or provider module; import-linter contract (i) gains common below core.
- core/domain.py, frozen dataclasses: Incident (title, product, severity, security flag, declarer, status, declared, detection, impact start, impact end, the five roles) and the typed references (conversation, report, video call, postmortem meeting, external case, source alert), each with system, tenant, vendor id and the vendor link; TimelineEntry as its own record. Times are timezone-aware.
- Tenant (human, 2026-10-14; decisions/workplace-systems.md rules 3 and 4, people-and-accounts.md:45,85): a tenant is the vendor's own identifier, never an invented label. Writers take it from the event payload (Slack team_id, Teams tenantId) from TASK-145.7 on. For mapping legacy items, which carry bare ids, the value comes from platform-owned settings: SLACK_TEAM_ID in app/integrations/slack/settings.py, and the real Google Workspace customer id (not the my_customer API alias). When the vendor is enabled (SLACK_ENABLED), its tenant id is required and validated at boot by the settings validator, with no network call. Google has no enabled flag today; this slice's plan settles how its customer id is validated.
- common/settings.py: incident core settings (incidents and timeline table names, defaulting to the provisioned tables) and the new-incident system policy (incident-management.md:73), which names a system, not a tenant id. Other settings slices arrive with the layers that consume them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 common/vocabulary.py defines IncidentStatus, Severity, the role names and StatusUpdateStage; lint-imports enforces that common/ imports no adapter, store or provider module
- [ ] #2 core/domain.py defines Incident with severity, the five roles and the four timing fields, and every reference type carries system, tenant and vendor id
- [ ] #3 SLACK_TEAM_ID is required and format-checked at boot when SLACK_ENABLED is true, and the Google customer id rule from the plan is enforced, with no network call
- [ ] #4 The incident core settings carry the incidents and timeline table names with the provisioned names as defaults
<!-- AC:END -->
