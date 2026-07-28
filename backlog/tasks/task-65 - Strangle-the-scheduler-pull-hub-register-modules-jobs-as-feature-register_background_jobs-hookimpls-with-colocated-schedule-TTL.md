---
id: TASK-65
title: >-
  Strangle the scheduler pull-hub: register modules/ jobs as feature
  register_background_jobs hookimpls with colocated schedule/TTL
status: To Do
assignee: []
created_date: '2026-07-28 16:30'
updated_date: '2026-07-28 17:04'
labels:
  - architecture
  - reliability
  - migration
milestone: m-5
dependencies:
  - TASK-64
references:
  - decisions/reliability.md
  - decisions/plugins.md
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1374'
priority: medium
ordinal: 95000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per decisions/reliability.md (Background jobs) + decisions/plugins.md. The legacy scheduler pull-hub (app/jobs/scheduled_tasks.py::init) hand-imports feature job bodies from across the tree - the inverse of the register_routes / register_slack_listeners push model:
- notify_stale_incident_channels  <- modules.incident.notify_stale_incident_channels
- spending.generate_spending_data <- modules.aws.spending
- provision_aws_identity_center   <- modules.aws.identity_center (calls integrations.aws.identity_store etc.)

Goal: as each of these jobs' OWNING code migrates from app/modules/ to app/packages/ (the m-5 legacy-modules strangler), move its scheduling to a register_background_jobs hookimpl in the owning package, with the job's schedule + Tier + (Tier-2) lease TTL sourced from the FEATURE's own partitioned settings (short, domain-namespaced names, e.g. IncidentSettings.LEASE_TTL_SECONDS / SpendingSettings.LEASE_TTL_SECONDS), and delete the corresponding hand-import + init() registration. When the last Model-A job is strangled: init()'s pull-hub body and the single shared scheduler-owned default lease TTL (introduced in TASK-6) are both removed; only host-owned Tier-1 jobs (heartbeat, integration_healthchecks) remain in the scheduler capability.

Depends on TASK-A (the widened BackgroundJobRegistry that lets a feature hookimpl declare Tier/TTL/schedule declaratively) - without it a feature cannot express a Tier-2 lease through the boundary. Also depends, per job, on that job's owning module-migration task in m-5.

THIS IS A COORDINATOR / PATTERN TASK - it almost certainly must be broken down and will NOT be implemented as a single PR. BREAKDOWN GUIDANCE FOR THE PLANNING CODING AGENT:
1. Identify the specific m-5 modules-strangler task that migrates each of the 3 jobs' owning code (modules.incident -> packages/incident; modules.aws.spending and modules.aws.identity_center -> their target packages). Confirm the exact task IDs before wiring dependencies.
2. Prefer FOLDING the "register this job via register_background_jobs with feature-owned schedule/TTL, delete the init() hand-import" acceptance criteria INTO each of those existing per-feature migration tasks (one job strangled per feature-migration PR), rather than doing a separate cross-cutting PR that touches three unrelated features at once. If a standalone slice is needed instead, create one --dep subtask per job (each --dep TASK-A + the owning migration task).
3. Enforce the single-PR size gate per job. Never strangle all three jobs in one PR.
4. The FINAL cleanup step (remove init()'s pull-hub body + the shared default scheduler TTL, leaving only host Tier-1 jobs) is its own small subtask, gated on all three per-job strangles being Done.

Reference decisions/reliability.md, decisions/plugins.md when implementing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the 3 currently hand-imported jobs (notify_stale_incident_channels, spending.generate_spending_data, provision_aws_identity_center) is registered via its owning feature's register_background_jobs hookimpl once that feature exists as a package; its schedule + Tier + lease TTL live in the feature's own partitioned settings, not the scheduler aggregator
- [ ] #2 The corresponding hand-import and init() registration is deleted as each job is strangled (verified per job)
- [ ] #3 When the last job is strangled, init()'s pull-hub body and the single shared default scheduler lease TTL are removed; only host-owned Tier-1 jobs (heartbeat, integration_healthchecks) remain in the scheduler capability
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 A human-approved plan/decomposition exists before implementation; the planner has confirmed the owning m-5 migration task per job and folded the hookimpl registration into it (or created per-job subtasks), enforcing the single-PR size gate
- [ ] #2 Tests per feature pass; final-cleanup subtask gated on all per-job strangles being Done
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 16:33
---
Placeholder ID resolved: 'TASK-A' in the description = TASK-64 (widened BackgroundJobRegistry). This is a coordinator/pattern task - per the breakdown guidance it should be decomposed by the planning agent, ideally folding each job's register_background_jobs hookimpl registration into that job's owning m-5 modules->packages migration task, one job per PR.
---
<!-- COMMENTS:END -->
