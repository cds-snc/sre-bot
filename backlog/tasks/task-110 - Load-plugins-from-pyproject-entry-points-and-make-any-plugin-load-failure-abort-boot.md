---
id: TASK-110
title: >-
  Load plugins from pyproject entry points and make any plugin load failure
  abort boot
status: To Do
assignee: []
created_date: '2026-09-24 19:59'
updated_date: '2026-09-25 15:54'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-107
  - TASK-35
  - TASK-14
references:
  - decisions/plugins.md
  - decisions/lifecycle.md
  - decisions/toolchain.md
priority: high
type: feature
ordinal: 252000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugins.md: discovery comes from entry points declared in pyproject.toml, loaded by pm.load_setuptools_entrypoints. Every mature pluggy host uses a declared list, never a folder scan. An entry-point target that will not import, or a hookimpl that raises during a hook call, aborts the lifespan.

Today auto_discover_plugins walks packages/ and modules/ with pkgutil.walk_packages and logs and skips a package that fails to import, so a broken feature silently does not load. No entry points are declared.

Scope:
- declare one entry point per plugin module under the host's group (the namespace constant from TASK-107);
- use dotted names for umbrella subdomains ("access.request");
- targets are the current flat import paths (packages.*) and are repointed to features.* or capabilities.* by each package move;
- replace the filesystem walk with load_setuptools_entrypoints;
- make import errors and raising hookimpls fatal in every layer (decisions/plugins.md); skipping a feature with invalid settings and the credential checks are TASK-126, which builds on this;
- add the CI check that every package shipping hookimpls has an entry-point line;
- running from bare, unsynced source loads zero plugins and fails loudly.

Packaging: load_setuptools_entrypoints reads installed-distribution metadata, so the image must install the app as a distribution (TASK-14).

legacy modules/: they keep their hand-written registration until each surface is rebuilt (decisions/migration.md). TASK-35 settles one registration path per module first. The walk is removed entirely, so any modules/ hookimpl still reached only by the walk must be on the legacy list by then.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 pyproject.toml declares an entry point for every current plugin, with dotted <feature>.<subdomain> names for umbrella subdomains; umbrella packages have none
- [ ] #2 Lifespan registers plugins only through pm.load_setuptools_entrypoints; no pkgutil/walk_packages discovery remains, and pm.register() for a first-party plugin appears only in test fixtures
- [ ] #3 Boot tests: a poisoned entry point aborts boot; a raising hookimpl aborts boot; every expected plugin is registered
- [ ] #4 CI check: every package shipping hookimpls has a matching entry-point line
- [ ] #5 decisions/plugins.md and decisions/lifecycle.md drop the filesystem-walk tolerance in the same PR
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
