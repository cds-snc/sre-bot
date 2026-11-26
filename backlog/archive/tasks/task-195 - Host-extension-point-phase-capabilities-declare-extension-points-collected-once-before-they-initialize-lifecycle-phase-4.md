---
id: TASK-195
title: >-
  Host extension-point phase: capabilities declare extension points, collected
  once before they initialize (lifecycle phase 4)
status: To Do
assignee: []
created_date: '2026-11-26T13:18:00Z'
updated_date: '2026-11-26T14:06:00Z'
labels:
  - plugins
  - lifecycle
  - webhooks
dependencies: []
references:
  - decisions/plugins.md
  - decisions/lifecycle.md
  - decisions/plugin-architecture.md
priority: high
ordinal: 552000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Lane B side PR from origin/main (doc-11 row 22.1c), split out of TASK-37.2.1 at its planning (P1, human-approved 2026-11-26). decisions/lifecycle.md phase 4 and plugins.md ('extension points collect strategies at startup ... no capability declares one yet') have no host code. The webhooks capability (TASK-37.2.3) is the first extension point.

Scope:
- contracts/plugins: an ExtensionPoint value type (name, the capability's hookspec class, an initialize callable that receives a per-hook collector, the type it provides) and a register_extension_points(registrar) hookspec, added to the hookspec inventory.
- server/plugins/extension_points.py: after plugin loading, pm.add_hookspecs for each declared spec class (a hookimpl with a bad signature fails boot naming its plugin); after content loading and before feature registration, call each initialize once in the declared order, collecting implementations per plugin through call_hook_per_plugin, and register the returned value in the svcs registry. A disabled capability's extension point never runs. No pluggy hook is called per request.
- server/lifespan.py: the phase, logged as phase=extension_points with counts.
- decisions/plugins.md (hookspec list, the declared capability order: webhooks first), lifecycle.md (phase 4 implemented), Changes lines.

Production: the boot path changes; no capability declares an extension point until TASK-37.2.3, so it is a no-op in production. Blast radius: a defect aborts boot, which is deploy-coupled, so the ECS circuit breaker rolls back. One git revert.
Change notice: FYI for plugin authors (a new host hookspec; capabilities can own extension points), per .claude/skills/delivery-session/change-notice.md.
Size: ~130 production LOC, ~6 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 register_extension_points and the ExtensionPoint value type live in contracts/plugins and are in the hookspec inventory test (test)
- [ ] #2 The host adds each declared spec class once after plugin loading; a hookimpl whose signature does not match fails boot naming its plugin (test)
- [ ] #3 Each extension point's initialize runs once, in the declared order, after content loading and before feature registration, and its value is registered in the service registry (test)
- [ ] #4 A disabled capability's extension point is never declared or called, and no pluggy hook is called per request (test)
- [ ] #5 plugins.md and lifecycle.md record the phase and the declared capability order (review)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-26 (human-approved at row 22.1c planning): folded into TASK-113, which already held the same phase on main with Lane A dependents (TASK-60, 83.15, 131, 165.2, 37.7); this file exists only on Stack W, so a single PR from origin/main could not carry it. Scope, ACs and plan live on TASK-113; TASK-37.2.3 now depends on TASK-113. Archived; the id is not reused.
<!-- SECTION:NOTES:END -->
