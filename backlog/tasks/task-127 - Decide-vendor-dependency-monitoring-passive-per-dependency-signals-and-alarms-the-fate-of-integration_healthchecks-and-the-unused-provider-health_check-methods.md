---
id: TASK-127
title: >-
  Decide vendor dependency monitoring: passive per-dependency signals and
  alarms, the fate of integration_healthchecks, and the unused provider
  health_check methods
status: To Do
assignee: []
created_date: '2026-09-25 14:58'
updated_date: '2026-09-25 15:54'
labels:
  - architecture
  - observability
  - clients
milestone: m-4
dependencies:
  - TASK-92
references:
  - decisions/health-checks.md
  - decisions/observability.md
  - app/jobs/scheduled_tasks.py
priority: medium
ordinal: 275000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ANALYSIS + DECISION-RECORD TASK (no production code). Split out of TASK-92 on 2026-09-25 so the service health model (boot checks, liveness and readiness) could close for TASK-109. Nothing on the critical path waits for this ticket.

Settled already, not reopened here: the only boot-time vendor call is a classified credential check that alerts and never aborts (decisions/lifecycle.md); the container, ECS, ALB and Route53 checks are static and never call a dependency (decisions/health-checks.md); svcs pings are diagnostics only (decisions/dependency-injection.md).

Open questions:
1. The passive signal. Per-dependency request/error/duration counts derived from adapter OperationResult, with low-cardinality vendor/operation/outcome dimensions, emitted through CloudWatch EMF or OpenTelemetry. Choose one, and decide which alarms consume it. A monitor without an alarm is a Well-Architected anti-pattern (https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_withstand_component_failures_monitoring_health.html).
2. Active probes. Whether a scheduled read-only probe is ever justified, for example for a low-traffic integration or to catch expiring credentials. If it is: what it tests (authentication, authorization and reachability, not data semantics; an empty AWS identity store is healthy), how OperationResult statuses map to page or alarm, and that it emits a metric rather than a log line.
3. The four entries of jobs/scheduled_tasks.py integration_healthchecks (google_drive, maxmind, opsgenie, aws identity store): keep, replace or delete each. Results are logs only today. Opsgenie support ends 2027-04-05, so do not invest in a new Opsgenie probe. TASK-64 AC#4, TASK-25.5 and TASK-25.6 touch these entries.
4. DriveProvider.warmup/health_check and DirectoryProvider.health_check have no production callers, and GoogleDriveProvider.health_check always succeeds. Keep each with a stated purpose (for example as an svcs ping), or remove it. State what a capability does when its vendor has no cheap probe endpoint, using Google Sheets as the worked example.
5. Optional: an authenticated operator diagnostics endpoint that runs the svcs pings, never used by the ALB (https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring).

Output: a metrics-and-alarms section in decisions/observability.md, a vendor-dependency section in decisions/health-checks.md or a new record, each with a Checks section, then follow-up tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/observability.md records the per-dependency signal (EMF or OpenTelemetry), its dimensions and the alarms that consume it, citing current sources
- [ ] #2 The decision states whether active vendor probes are allowed, their criteria, what healthy means (empty identity store as the worked example) and how OperationResult statuses map to alarms
- [ ] #3 Each integration_healthchecks entry has a recorded fate, and TASK-64, TASK-25.5 and TASK-25.6 are updated through the CLI where they conflict
- [ ] #4 DriveProvider.warmup/health_check, DirectoryProvider.health_check and GoogleDriveProvider.health_check are kept with a stated purpose or scheduled for removal, and the no-cheap-probe case is decided with Google Sheets as the example
- [ ] #5 Every amended or new record has a mechanically verifiable Checks section; follow-up tasks are created; no production code changes
<!-- AC:END -->
