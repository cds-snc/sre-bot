---
id: TASK-94
title: >-
  Match the SRE Bot error and warning alarms on structured log fields instead of
  free-text regex
status: To Do
assignee: []
created_date: '2026-09-15 19:39'
labels:
  - infrastructure
  - observability
  - terraform
milestone: m-4
dependencies:
  - TASK-28.2
references:
  - terraform/local.tf
  - terraform/alarms.tf
  - decisions/observability.md
priority: high
ordinal: 211000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Motivation (production incident 2026-09-15): the "SRE Bot Errors" alarm overstated the failure volume. terraform/local.tf:10-14 builds the error metric filter from a free-text regex (error|exception) and excludes only lines matching level.{0,6}(warning|info). terraform/alarms.tf:1-30 alarms on Sum >= var.error_threshold over 60s. One failed webhook request incremented the metric several times:
- The JSON webhook_posting_error event.
- Each raw traceback line that follows it on stderr. These lines have no level, so the exclusion never applies (root cause and fix in TASK-28.2, AC#6).
- The uvicorn plain-text access line `"POST /hook/... HTTP/1.1" 500 Internal Server Error`.
The warning filter (local.tf:16-24) also matches any line containing "WARNING". legacy_api_endpoint_accessed (api/router.py:29) is logged at warning level on every legacy call, including every /hook POST, which is expected volume rather than a degraded state.

Scope (terraform only, after TASK-28.2 makes every line JSON):
- Replace both free-text patterns with JSON metric filter patterns on the structured level field, e.g. { ($.level = "error") || ($.level = "critical") } and { $.level = "warning" }. Verify the exact syntax against current AWS CloudWatch Logs filter pattern docs at planning.
- Decide (human) how to handle expected-volume warnings such as legacy_api_endpoint_accessed: downgrade the event, exclude it by $.event in the filter, or keep it counted.
- Optionally add a 5xx metric from JSON-rendered uvicorn access records once TASK-28.2 lands.
- Add aws_cloudwatch_query_definition saved queries for triage: errors by event over time (filter level = "error" | stats count(*) by event, bin(5m)); webhook invocations by webhook_id, matched_payload_type and user_agent; and, once TASK-28.3 lands, all records for a request_id.
- Roll out safely: run the new metric filters alongside the old ones and compare before pointing the alarms at them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The error metric filter counts only JSON events whose level is error or critical. A non-JSON line containing Error or Exception does not count, verified with aws logs test-metric-filter sample events recorded in notes
- [ ] #2 The warning metric filter counts only JSON events whose level is warning, and the decision on expected-volume warnings (legacy_api_endpoint_accessed) is recorded and applied
- [ ] #3 Saved Logs Insights query definitions exist for errors by event over time and for per-webhook invocation triage
- [ ] #4 The new metric filters run alongside the old ones before the alarms switch, with the terraform plan output and the comparison recorded in notes
<!-- AC:END -->
