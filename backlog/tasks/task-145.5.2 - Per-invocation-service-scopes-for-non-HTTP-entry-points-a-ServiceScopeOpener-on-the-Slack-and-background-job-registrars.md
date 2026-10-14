---
id: TASK-145.5.2
title: >-
  Per-invocation service scopes for non-HTTP entry points: a ServiceScopeOpener
  on the Slack and background-job registrars
status: To Do
assignee: []
created_date: '2026-10-14 23:08'
labels:
  - plugin-architecture
  - dependency-injection
  - slack
dependencies: []
references:
  - decisions/dependency-injection.md
  - decisions/plugin-architecture.md
  - app/server/services.py
  - 'https://svcs.hynek.me/en/stable/why.html'
  - 'https://svcs.hynek.me/en/stable/integrations/custom.html'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 388000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 3 of Stack K (handoff doc-13). decisions/dependency-injection.md:30-33 says Slack and Teams handlers, webhook consumers and jobs open a container per invocation, and only entry points touch a container. TASK-109 built the registry, but a feature cannot reach it: features may not import server/, and the registry only lives on the FastAPI app (svcs.fastapi.get_registry). dependency-injection.md:61 lists per-call containers as in place, which overstates it. TASK-145.5.5 is the first feature consumer; jobs (TASK-145.5.7, TASK-64, TASK-140.11), webhook strategies (TASK-37.x) and approvals (TASK-60) need the same thing.

DECIDED (human, 2026-10-14)
- One role-named Protocol, ServiceScopeOpener, in app/contracts/services/: open() returns a context manager yielding a ServiceResolver (get(contract: type[T]) -> T). svcs stays out of contracts/ (plugin-architecture.md:42); svcs.Container satisfies the resolver structurally.
- Exposed by the Slack registrar (SlackCommandRegistrar and PluginSlackRegistrar) and by BackgroundJobRegistry, so every non-HTTP entry point uses the same mechanism.
- The server implementation in server/ opens an svcs.Container over the app registry per invocation and closes it on exit, including when the handler raises.
- Sync now: registrar handlers and scheduler jobs are sync until TASK-33 (async Bolt), which adds an async variant.
- Handlers are closures built in register(registrar): open a scope, resolve contracts, build services through the feature's provider functions (which take resolved contracts as arguments), call one service method, close the scope. The container is never handed to a service (svcs: resolving at the entry point is dependency injection; resolving in services is service location).
- decisions/dependency-injection.md records the mechanism and fixes the in-place line.

ALTERNATIVE CONSIDERED, kept for a later review
- A host Bolt middleware opens the container per request and places it in the Bolt context (the svcs custom-integration pattern; the resolved-caller precedent in decisions/platform-entrypoints.md:40). Pros: native for block actions and view listeners, no registrar API change. Cons: does not cover background jobs; host-routed commands would need it threaded through CommandPayload (TASK-141 undecided); a second mechanism beside the job one. Revisit if TASK-141 or TASK-33 changes how Slack listeners are registered.

No feature uses it in this slice; a reference test drives a handler and a job through it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/contracts/services/ defines ServiceScopeOpener and ServiceResolver with no svcs import; contracts/ still imports only what plugin-architecture.md allows
- [ ] #2 SlackCommandRegistrar and BackgroundJobRegistry expose the opener, and the server implementation opens one svcs container per invocation and closes it on success and on raise
- [ ] #3 Resolving an unregistered contract through the opener fails with the registry's not-found error; tests use the fake-registering service_registry fixture
- [ ] #4 decisions/dependency-injection.md records the opener, the resolve-then-pass rule and the middleware alternative, and its in-place line is accurate
<!-- AC:END -->
