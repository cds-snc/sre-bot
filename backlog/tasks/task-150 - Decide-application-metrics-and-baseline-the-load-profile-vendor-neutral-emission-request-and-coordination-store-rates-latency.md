---
id: TASK-150
title: >-
  Decide application metrics and baseline the load profile: vendor-neutral
  emission, request and coordination-store rates, latency
status: To Do
assignee: []
created_date: '2026-10-14 19:03'
updated_date: '2026-10-15 17:53'
labels:
  - architecture
  - observability
dependencies: []
references:
  - decisions/observability.md
  - decisions/reliability.md
  - decisions/cloud-portability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1717'
priority: medium
ordinal: 384000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ANALYSIS + DECISION-RECORD TASK (no production code). Start after the doc-11 (Incident delivery map) scope is finished.

## Why
decisions/observability.md covers logs, correlation and log-based alarms only; there is no decision on application metrics. We have no measured load profile, so infrastructure choices cannot be sized: notably the second backend for the coordination contract (ConditionalWriteStore: DynamoDB today; PostgreSQL, Cosmos DB, Redis/Valkey candidates), plus queue and records backends. Azure and OpenShift are short-to-midterm targets, so the mechanism must not bind to CloudWatch.

## Scope (high level)
- Choose the metrics emission mechanism and export path that work on AWS, Azure and OpenShift (e.g. OpenTelemetry metrics SDK with an OTLP or Prometheus exporter versus EMF log-derived metrics) and record it in decisions/observability.md.
- Define the first metric set: inbound rate and latency per transport (HTTP, Slack, webhooks, scheduler), outbound call rate, latency and error class per vendor, and coordination-store claim/complete/release rate, latency and result distribution (NEW, COMPLETED, IN_PROGRESS, INDETERMINATE).
- Collect a baseline load profile (peak and steady rates, p50/p99 latency) for at least two weeks once emitted.
- Boundary with TASK-127: that task owns passive per-dependency health signals and alarms; this one owns the metrics mechanism and load baseline. Reconcile, do not duplicate.

## Out of scope
Dashboards and alarm tuning beyond what the decision needs; choosing the coordination backend itself.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/observability.md records the metrics emission mechanism and export path, with the reason it is portable across AWS, Azure and OpenShift
- [ ] #2 The first metric set is listed with names, units, and labels kept low-cardinality (no user ids, request ids or idempotency keys)
- [ ] #3 Coordination-store metrics cover claim, complete and release rate, latency and the ClaimResult distribution
- [ ] #4 The split of responsibility with TASK-127 is written in both tasks
- [ ] #5 Follow-up implementation tasks exist, each passing the single-PR size gate, including one to capture and record a baseline load profile
<!-- AC:END -->
