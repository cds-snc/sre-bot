---
id: TASK-113
title: >-
  Add the lifespan extension-point phase: collect each capability's strategies
  once at startup, in declared order, before it initializes
status: Done
assignee: []
created_date: 2026-09-24 19:59
updated_date: '2026-11-26T19:06:00Z'
labels:
  - plugin-architecture
  - plugins
  - lifecycle
  - webhooks
milestone: m-7
dependencies:
  - TASK-107
  - TASK-110
references:
  - decisions/plugin-architecture.md
  - decisions/plugins.md
  - decisions/lifecycle.md
  - https://github.com/cds-snc/sre-bot/issues/1656
priority: high
type: feature
ordinal: 255000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md, plugins.md and lifecycle.md phase 4: for each capability, in its declared order, the host calls that capability's own hookspecs once, collects the returned strategy objects (an ApprovalPolicy, an alert-action handler), and passes them to the capability before it initializes. At runtime the capability awaits the strategies' async methods. pluggy hooks are synchronous and are never called per request. A capability never initializes with an extension point still unfilled.

This replaces the in-process event bus as the way one plugin reacts to another (TASK-30 deletes the bus).

Lane B side PR from origin/main (doc-11 row 22.1c). The first capability that owns hookspecs is now the webhooks capability (TASK-37.2.3, which waits on this task), not the approvals engine (TASK-60, on hold). TASK-195, created at TASK-37.2.1 planning on Stack W with the same scope, is folded into this task (2026-11-26). It carries no speculative extension point: tests use test capabilities.

Scope: contracts/plugins (ExtensionPoint, its registrar and context, the register_extension_points hookspec), server/plugins/extension_points.py (the phase), server/lifespan.py, and lifecycle.md, plugins.md and plugin-architecture.md.
Production: the boot path changes, and the phase is a no-op until TASK-37.2.3. Blast radius: a defect aborts boot, which is deploy-coupled, so the ECS circuit breaker rolls back. One git revert.
Change notice: FYI for contributors (new host hookspec), per .claude/skills/delivery-session/change-notice.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 register_extension_points is on FeatureLifecycleSpecs, and ExtensionPoint, ExtensionPointRegistrar and ExtensionPointContext live in contracts/plugins/extension_points.py; the hookspec inventory test lists the new hook (test)
- [x] #2 Only a capability plugin declares an extension point, at most one, named after its entry point; the host adds each spec class once, and a hookimpl whose signature does not match fails boot with plugin_boot_failed naming its plugin (test)
- [x] #3 Extension points initialize once each in depends_on order (ties in plugin load order); a cycle or a dependency on an undeclared extension point fails boot naming both; each value is registered in the service registry under its provides type, and a duplicate type fails boot (test)
- [x] #4 The phase runs after plugin loading and i18n (and content loading where present) and before feature registration, logging one INFO extension_points_initialized with its counts; a hookimpl or initialize that raises aborts boot before yield naming the right plugin (test)
- [x] #5 A disabled capability's extension point is never declared and its hooks are never collected; collect refuses hooks outside the capability's own spec class and any call after the phase, so no pluggy hook is called per request (test)
- [x] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass (check)
- [x] #7 lifecycle.md, plugins.md, plugin-architecture.md, dependency-injection.md and approvals.md record the phase, the hookspec, depends_on as the declared order, host hookspecs versus capability extension points, the capability's own cardinality check, and the context's resolver and opener, each with a Changes line (review)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-11-26 against origin/main 876f7f7f (doc-11 row 22.1c; TASK-195 folded in, see D0). D0 approved (human, 2026-11-26); D1-D4 revised after the program-scope assessment (PS1-PS6 below); plan approved (human, 2026-11-26).

D0. One task. TASK-195 (created at TASK-37.2.1 planning) duplicates this task, and its file exists only on Stack W's W2 branch (#1891), so a single PR from origin/main cannot carry it. TASK-113 is on main and already holds the Lane A dependents (TASK-60, 83.15, 131, 165.2, 37.7). Decision: this task implements the phase and takes TASK-195's scope; on W2, a follow-up commit archives TASK-195 (its id is not reused) and repoints TASK-37.2.3's dependency to TASK-113.

D1. Contract, contracts/plugins/extension_points.py (new; pluggy markers only, no pluggy import):
- ExtensionPoint[T] (frozen dataclass): specs (the capability's hookspec class), provides (type[T], the svcs key), initialize (Callable[[ExtensionPointContext], T]), depends_on (tuple[str, ...] = (), the entry-point names of capabilities whose values initialize needs first). It has no name field: the host names it after the declaring plugin, so a plugin cannot claim another capability's point.
- ExtensionPointRegistrar Protocol: declare(point).
- ExtensionPointContext Protocol: collect(hook_name, /, **kwargs) -> Mapping[str, Sequence[object]] (each plugin's non-None results by entry-point name, in load order), services: contracts.services.ServiceResolver, valid only during initialize (values registered before the phase, such as the content catalogue and an earlier capability's value; resolving here is wiring at the composition boundary, never inside a service), and service_scopes: contracts.services.ServiceScopeOpener, which the capability hands to its consumers and handlers for their per-invocation scopes (settles dependency-injection.md's 'obtain an opener from their own registration points'). A parameter object, so later fields are additive for implementers (hookspec-deprecation.md).
- contracts/plugins/hookspecs.py: register_extension_points(self, registrar: ExtensionPointRegistrar) -> None on FeatureLifecycleSpecs; docstring: capabilities only, at most one each.

D2. Host, server/plugins/extension_points.py (new), one function run_extension_points(pm, registry, logger):
1. Declare: call_hook_per_plugin(pm, "register_extension_points", logger, registrar=...) with a registrar scoped per plugin. It refuses, failing boot with plugin_boot_failed naming the plugin, a declaration from a plugin whose module is outside capabilities (plugin-architecture.md: an extension point belongs to one capability; features are the extension surface) and a second declaration from the same plugin.
2. Specs: pm.add_hookspecs(point.specs) once per point. pluggy then verifies the already-registered hookimpls (checked empirically on pluggy 1.7.0: PluginValidationError names the plugin). The host maps error.plugin to its entry-point name and logs plugin_boot_failed, phase=extension_points.
3. Order: graphlib.TopologicalSorter over depends_on (standard library), ties in plugin load order. A cycle or a dependency on a capability that declared no point (disabled, or none declared) fails boot naming both. This is the declared order of plugins.md and plugin-architecture.md, declared by dependency as Backstage orders plugin and module initialisation, not a hand-kept list.
4. Initialize: one svcs.Container(registry) for the phase. For each point in order: initialize(context) once, then registry.register_value(point.provides, value). A provides type already registered fails boot. An initialize that raises outside a hook call is logged as plugin_boot_failed for the capability, phase=extension_points; a hookimpl that raises inside collect is attributed to its own plugin by call_hook_per_plugin, as today.
5. The context's collect accepts only hook names on the point's own spec class (not host hooks, not another capability's) and raises once the phase has ended. Capabilities cannot import server/ (import contract b), so collect is their only path to pluggy: no hook is called per request.
6. Log one INFO extension_points_initialized, phase=extension_points, with extension_points (names in order) and implementation_count; DEBUG extension_point_initialized per point with the contributing plugins (observability.md startup logging rule).
- Empty collections: whether a point may be empty is the capability's rule. Its initialize raises, which fails boot naming it. TASK-113's old AC #3 (an extension point with no strategy aborts boot) is reworded this way: the webhooks point is legitimately empty until the incident alert consumer (TASK-37.3), because its default consumer is the capability's own.
- No pm.check_pending(): a feature's hookimpl into a disabled capability stays unverified and is never called. Disabling a capability must not abort boot for a feature that uses it optionally (plugins.md shared-capability rule). A misspelt hookimpl is caught by the contributing feature's own collection test.

D3. server/lifespan.py: run_extension_points after _initialize_translation_service and before register_feature_integrations (end of phase 3, start of phase 5). On origin/main there is no content loading yet. #1889 (TASK-37.1) adds load_provisioned_content at the same spot, and whichever merges second puts content loading first, then extension points (lifecycle.md: content in phase 3, extension points in phase 4).

D4. ADRs (Changes line each): lifecycle.md phase 4 says how (declared by depends_on, one INFO event, a capability decides whether empty is allowed), a Current code bullet, TASK-113 in Migration; plugins.md hookspec list gains register_extension_points, and the Extension points paragraph says the order is declared through depends_on, capabilities only, and that none declares one until the webhooks point (TASK-37.2.3); plugin-architecture.md says the declared order of a capability's initialisation is its extension point's depends_on, and the import order is unchanged. dependency-injection.md: the opener line is settled (the context's service_scopes) and initialize is named as a wiring step that may resolve. approvals.md: 'the host calls the approvals hookspecs' becomes the host collecting through the capability's extension point, and its per-workflow-type boot rule is the capability's initialize check (PS3). plugins.md also separates host hookspecs (FeatureLifecycleSpecs, collected by the host, such as TASK-131's permission declarations) from capability extension points (this phase). webhooks.md (its line naming TASK-37.2.1 for the hookspec) is left to TASK-37.2.3 on the stack, since it differs between main and Stack W.

Tests (TDD, failing first):
- tests/unit/contracts/plugins/test_contracts_hookspecs_inventory.py: the new hook and its params.
- tests/unit/server/plugins/test_server_plugins_extension_points_initialize.py: test capability plugins built in the test; declare and spec once; bad hookimpl signature names the plugin; feature-declared and duplicate declarations refused; depends_on order, cycle and missing dependency; value registered under provides, duplicate provides refused; collect refuses foreign hooks and calls after the phase; a raising hookimpl and a raising initialize name the right plugin; disabled (blocked) capability never declared, its feature hookimpls never called; INFO event counts.
- tests/integration/server/test_lifespan_extension_points_phase.py: phase order in the lifespan (after i18n, before feature registration) and abort before yield.

Files: 4 production (2 new, 2 edited; ~190 LOC), 3 ADRs, 3 test files, this task file. Under the size gate. No settings: the phase has no policy value.

Production: the boot path changes. No capability declares an extension point until TASK-37.2.3, so in production the phase calls register_extension_points per plugin, finds none and logs zero. Blast radius: a defect aborts boot. That is deploy-coupled: the old tasks keep serving and the ECS circuit breaker rolls back (deployment.md). Rollback: one git revert of the PR's merge.
Change notice: FYI for contributors (a new host hookspec; capabilities can own extension points), no action. Dark for callers and users.
Conflicts: #1889 edits hookspecs.py, the inventory test, lifespan.py and plugins.md's hookspec list line; whichever merges second rebases and keeps both sides. Lane A may edit server/plugins or lifespan.py: same rule.

Program-scope assessment (2026-11-26; ADRs, doc-11, doc-15, doc-16, doc-18, prior and upcoming tasks; web sources cited):
PS1 (OQ2 order). Gap: plugins.md:47 and plugin-architecture.md:96 say 'declared order' and never say where it is declared. No prior task settled it (TASK-25.10.2, 2026-11-19: 'capability order stays undeclared until the first capability needs one'). No capability imports another today. Upcoming consumers: webhooks (TASK-37.2.3, no dependency) and approvals (TASK-60, on hold, none named). Practice: Backstage starts up in dependency order from declared deps, a plugin's modules before the plugin, and never from a hand-kept list (backstage.io backend-system architecture: plugins, modules, extension points). Ruling: depends_on with graphlib is the declared order; plugin-architecture.md:96 points to it for capability-to-capability imports. An import-linter layers contract is added by the first task in which one capability imports another.
PS2 (OQ3 empty). Conflict: lifecycle.md phase 4 'never initializes with an extension point still unfilled' and its boot test read as non-empty, while the webhooks point is legitimately empty until TASK-37.3 (plugin-architecture.md:46: a capability is always present). approvals.md:64 needs a per-workflow-type rule (a policy and an effect handler for each type), which no point-level count can express. Practice: Eclipse extension-point schemas declare cardinality per point (minOccurs/maxOccurs), set by the point's owner; Backstage states no rule. Ruling: 'filled' means collected before initialize, and the owning capability's initialize enforces its own cardinality, failing boot naming it. lifecycle.md wording and its Checks line are amended with a Changes line.
PS3 (approvals wording). approvals.md:37 'The host calls the approvals hookspecs once at startup' is reworded to the host collecting through the capability's extension point (D4); its boot test stands as the capability's initialize check. No scope change to TASK-60.
PS4 (OQ4 check_pending). No ADR covers misspelt or unknown hookimpls. plugins.md:43 and :45 (a capability is switched only by its plugin module; disabling one area must not abort boot for another) support leaving a feature's hookimpl into a disabled capability unverified. A feature that cannot run without the capability declares it through register_requirements, which already aborts boot when the capability is not configured (plugins.md, TASK-172). pluggy's check_pending raises for every pending hookimpl not marked optionalhook, so it would turn an optional use into a boot abort. Ruling: no check_pending; plugins.md records the rule and the requirement path.
PS5 (OQ5 resolver). Conflict to resolve: dependency-injection.md 'the resolver is never given to a service'. initialize is the capability's wiring step, not a service: it resolves at the composition boundary as a feature's wiring module does (dependency-injection.md, feature-local wiring) and as a Backstage init receives resolved deps. The resolver is closed after initialize, so no built value can keep it. The same ADR leaves open how webhook consumers and approval handlers obtain an opener ('settled when each is planned'): the context's service_scopes settles it for every capability. Backstage passes declared deps by ref; Python cannot type a ref mapping per key, so the typed get[T] resolver is kept.
PS6 (other consumers). (a) TASK-131 and authorization.md:32 declare permission ids through 'the host's extension point': that is a host hookspec in FeatureLifecycleSpecs, collected by the host like register_requirements, not this phase. TASK-131 keeps its dependency on TASK-113 (the phase must exist first), and the wording is a hand-off recorded in doc-11, not an edit to TASK-131 here. (b) large-scale-incident-analysis.md:1215 and :1557 sketch a playbook-section hookspec declared in the incident umbrella's common/, which feature-packages.md:33 ('hookspecs.py: capabilities only') already forbids. Hand-off to TASK-165.8 planning (Lane A): register the section schemas through a host hookspec, or as content kinds through register_content_kinds, which every subdomain plugin already calls. No change to this task's rule. (c) doc-15, doc-16 and doc-18 add no other extension-point consumer.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-26, implemented (TDD) on task-113-host-extension-points from origin/main 876f7f7f. Production: contracts/plugins/extension_points.py (ExtensionPoint[T], ExtensionPointContext, ExtensionPointRegistrar), the register_extension_points hookspec on FeatureLifecycleSpecs, server/plugins/extension_points.py (run_extension_points: per-plugin registrar refusing non-capabilities and second declarations; add_hookspecs with PluginValidationError attributed to its plugin; graphlib order over depends_on with load-order ties, cycle and undeclared dependency refused; duplicate provides refused; collect limited to the point's own hooks and closed after initialize, resolver closed too, service_scopes kept; one INFO extension_points_initialized, DEBUG per point), and server/lifespan.py (phase 4 after i18n, before feature registration). collect returns one result per contributing plugin (pluggy allows one hookimpl per plugin per hook), typed Mapping[str, object]: the capability validates contributed values. ADRs: plugins.md, lifecycle.md, plugin-architecture.md, dependency-injection.md, approvals.md, each with a Changes line. Tests: inventory test, 18 unit tests (test_server_plugins_extension_points_initialize.py), 2 lifespan integration tests; the ci boot INFO budget rises 10 -> 11 for the new phase event. Gates: ruff clean; check-import-contracts 15 kept; settings ownership, package shape, test seams OK; mypy 33 errors in 11 untouched files, pre-existing, none in touched files. Conflicts to expect: #1889 (hookspecs.py, the inventory test, lifespan.py, plugins.md's hookspec list line); whichever merges second rebases, and content loading goes before run_extension_points.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Merged in #1894 (d886a357, 2026-11-26): lifecycle phase 4 runs each capability's extension point once, in depends_on order, after plugin loading, i18n and provisioned content and before feature registration; register_extension_points, ExtensionPoint, ExtensionPointRegistrar and ExtensionPointContext in contracts/plugins; ADRs updated. All ACs checked; no human post-deploy step (no extension point is declared until TASK-37.2.3).
<!-- SECTION:FINAL_SUMMARY:END -->
