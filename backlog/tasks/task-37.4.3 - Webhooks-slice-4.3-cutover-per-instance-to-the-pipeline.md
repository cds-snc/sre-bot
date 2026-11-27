---
id: TASK-37.4.3
title: 'Webhooks slice 4.3: cutover per instance to the pipeline'
status: To Do
assignee: []
created_date: '2026-11-25T20:48:00Z'
updated_date: '2026-11-27T17:31:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.4.2
  - TASK-145.7.11
references:
  - decisions/webhooks.md
  - decisions/migration.md
  - decisions/security.md
parent_task_id: TASK-37.4
priority: high
ordinal: 545000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The cutover (TASK-168 research packet section 5, row 37.4, and Q8; decisions/webhooks.md Responses and Migration). A single PR from main.

Scope:
- Instances move from legacy to pipeline after shadow parity: N matching deliveries per instance (N set per instance by the human) or reviewed differences (OQ7, OQ24). Canary one SNS instance, then all.
- Acknowledge after persist: a Slack failure now answers 200 (the item is persisted and retried by the sweeper) instead of 500. The TASK-36.2 pins that assert 500 or 503 on a post failure are updated with that reason.
- The TASK-190 padding AC (delivery map row 21).
- The /api/v1/hook mount decision and the WAF scope-down (old TASK-37.4 AC #6; the human production access-log check since 2026-11-03, TASK-37.4 comment #1).
- The TASK-36.2 pin harness rewired (old TASK-37.4 AC #7), keeping the F-G unpatched_app_init restore (TASK-37.4 comment #2).
- The alert button value moves from the raw webhook_id and the alert text to instance_ref plus the inbox item id, coordinated with the incident feature, whose producer moves first in TASK-145.7.11 (Stack L); TASK-145.7.11's scope is unchanged (correction C9 of TASK-37.1's plan).
- TASK-46 fingerprint emission and TASK-7 hardening carried onto the new route; POST only (405) and an unexpected Content-Type answers 415.

Out of scope: deleting the legacy processing and enforcing passthrough hardening (TASK-37.5); the admin surface (TASK-37.6.x).

Size: ~200 production LOC, ~6 files.
Production: prod. Blast radius: every webhook post. Canary one instance, then all.
Revert: flag back to legacy instantly, per instance, no deploy.
Change notice: developer notice, no action needed: redelivered SNS messages post once; failures are retried by the bot (no more 500); new 405 and 415 responses; URLs unchanged. User announcement only if the shadow shows visible rendering differences (escaping) (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Instances move from legacy to pipeline per instance after shadow parity (N matching deliveries or reviewed differences, recorded in the notes): one SNS canary, then all; the flag returns any instance to legacy without a deploy (test + review)
- [ ] #2 A Slack failure after persist answers 200 and the sweeper retries the item; the TASK-36.2 pins that asserted 500 or 503 on a post failure are updated, each with the reason: acknowledge after persist (decisions/webhooks.md) (test)
- [ ] #3 before cutover, the just-under-cap pin pads text and a blocks string, and the route serves it well within the integration budget
- [ ] #4 The WAF Common Rule Set scope-down and the body cap cover both webhook mount points (/hook/ and /api/v1/hook/), or the duplicate mount is dropped by decision; the TASK-163 edge test's public-by-decision set matches the outcome
- [ ] #5 The TASK-36.2 pin harness is rewired at its named steps (mount_webhook_routes mounts through the plugin manager's register_routes as the edge route probe does; set_webhook_bot_state and the webhook_records fake move to the capability's fakes) with every assertion unchanged (test)
- [ ] #6 The alert button value moves from the raw webhook_id and the alert text to instance_ref plus the inbox item id, coordinated with the incident feature (whose producer TASK-145.7.11 moves first); no URL token or alert text is in a button value (test)
- [ ] #7 TASK-46 fingerprint emission and TASK-7 hardening are preserved on the new route; a non-POST method answers 405 and an unexpected Content-Type answers 415 (test)
- [ ] #8 TASK-36 smoke tests pass after cutover (test)
- [ ] #9 The PR body carries the developer change notice (no action needed) (review)
- [ ] #10 The inbox sweeper job (built dark in TASK-37.2.2) registers through register_background_jobs with a lease_ttl from [webhooks], so retry, takeover of an expired lease and dead-lettering run once the first instance is on the pipeline (test)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27 (TASK-37.2.2 planning, human-approved): AC added. TASK-37.2.2 builds the sweeper but registers no job, since the webhooks plugin is enabled in base.toml and a registered job would run against a table that does not exist; AC #2 here already assumes the sweeper runs.

2026-11-27 (TASK-37.2.2 implementation): call capabilities.webhooks.entrypoints.jobs.register_sweeper(registry) from a register_background_jobs hookimpl in plugin.py; its interval and lease come from [webhooks] sweeper_interval_seconds and sweeper_lease_ttl_seconds.
<!-- SECTION:NOTES:END -->
