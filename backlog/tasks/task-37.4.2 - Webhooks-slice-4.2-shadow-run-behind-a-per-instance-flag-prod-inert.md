---
id: TASK-37.4.2
title: 'Webhooks slice 4.2: shadow run behind a per-instance flag (prod, inert)'
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
  - TASK-37.4.1
  - TASK-37.2.4
  - TASK-198
references:
  - decisions/webhooks.md
  - decisions/migration.md
parent_task_id: TASK-37.4
priority: high
ordinal: 544000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The shadow run before cutover (TASK-168 research packet section 5, row 37.4s, and Q8). A single PR from main.

Scope: the capability serves POST /hook/{webhook_id} (and /api/v1/hook/{webhook_id} while that mount stands, see TASK-37.4.3) through register_routes, behind a per-instance three-state OpenFeature flag legacy | shadow | pipeline, evaluated with instance_ref in context, default legacy. In shadow the legacy path stays primary; the new pipeline verifies, decodes, matches, extracts and renders, persists nothing that dispatches and posts nothing, and emits webhook_shadow_result: instance_ref, the kind matched by each path, and a structural digest of both renders (block count, field names, text length and hash), never the text. The shadow also fingerprints the passthrough-hardening fields per instance (enforced in TASK-37.5) and finds instances that receive more than one protocol (they stay legacy until split).

Out of scope: moving any instance to pipeline (TASK-37.4.3).

Size: ~150 production LOC.
Production: prod, inert. Callers see no change.
Revert / blast radius: set the flag to legacy, no deploy; or one revert.
Change notice: none (inert); an internal ops note only (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The capability serves the webhook route through register_routes and a per-instance flag (legacy | shadow | pipeline, default legacy) selects the path (test)
- [ ] #2 In shadow the legacy path answers and posts as today, and the pipeline posts nothing and dispatches nothing (test)
- [ ] #3 webhook_shadow_result carries instance_ref, the kind matched by each path and structural digests of both renders, and never message text or payload values (test)
- [ ] #4 The passthrough-hardening fields and instances receiving more than one protocol are fingerprinted per instance (test)
- [ ] #5 The TASK-36.2 pins pass unchanged with every instance on legacy or shadow (test)
- [ ] #6 An internal ops note says how to move an instance to shadow and how to read the results (review)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-27 (TASK-37.2.2 planning, human-approved): mounting the route needs the inbox table (TASK-37.2.4, row 22.3a) and the received-bytes body cap with a ceiling above the SNS cap (TASK-198, row 22.3b), both merged first.

2026-11-27 (TASK-37.2.2 implementation): the router is capabilities/webhooks/entrypoints/http.py (router, get_ingress), built and tested but not included; include it through register_routes here. Each new-path delivery logs webhook_received with the instance_ref and the passthrough-hardening fingerprint (field names only), which AC #4 can aggregate.
<!-- SECTION:NOTES:END -->
