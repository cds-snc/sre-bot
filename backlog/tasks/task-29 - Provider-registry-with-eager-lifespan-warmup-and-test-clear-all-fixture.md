---
id: TASK-29
title: Provider registry with eager lifespan warmup and test clear-all fixture
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - infrastructure
  - phase-4
  - di
milestone: m-4
dependencies: []
references:
  - decisions/dependency-injection.md
  - decisions/testing.md
priority: medium
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/dependency-injection.md (Eager composition). Today providers are lazy lru_cache functions; nothing guarantees phase-2 population - a forgotten warmup means first construction mid-request; and tests have no one switch to clear all cached singletons.

Steps:
1. Small registry in app/infrastructure/ (a decorator, e.g. @provider, appending the function to a module-level list; the decorator wraps lru_cache).
2. Lifespan phase 2 invokes every registered provider - construction and settings validation at boot, fail fast (a poisoned provider aborts before yield).
3. Autouse fixture in app/tests/conftest.py clearing every registered provider cache between tests (unblocks the decisions/testing.md substitution model).
4. Convert existing get_* providers to the decorator; concrete class names appear only in providers.py files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Lifespan phase 2 invokes the registry; a poisoned provider fails boot before yield (test)
- [ ] #2 Autouse clear-all fixture exists and demonstrably isolates two tests overriding the same provider
- [ ] #3 grep: concrete service class names appear only in providers.py files
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All existing providers registered; tests green
- [ ] #2 PR references decisions/dependency-injection.md
<!-- DOD:END -->
