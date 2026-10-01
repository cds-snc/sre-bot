---
id: TASK-107.2
title: >-
  Move I18nResourceSpec to app/contracts/i18n/ and add the I18nResourceRegistrar
  Protocol
status: To Do
assignee: []
created_date: '2026-10-01 14:47'
updated_date: '2026-10-01 14:59'
labels:
  - plugin-architecture
  - plugins
milestone: m-7
dependencies:
  - TASK-107.1
references:
  - decisions/plugins.md
  - decisions/i18n.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-107
priority: high
ordinal: 294000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack A layer 8b (slice 2 of TASK-107). register_i18n_resources is typed on the concrete infrastructure I18nResourceRegistry, which contracts cannot import (contract c). I18nResourceSpec (frozen dataclass) moves to contracts/i18n/ with an I18nResourceRegistrar Protocol (register(spec)); the infrastructure registry implements it. Every importer is rewritten, no re-export.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/contracts/i18n/resources.py defines I18nResourceSpec (fields and validation unchanged) and I18nResourceRegistrar (Protocol: register(spec) -> None) and imports nothing from the app
- [ ] #2 infrastructure/i18n/resources.py keeps I18nResourceRegistry, imports the spec from contracts, and structurally satisfies I18nResourceRegistrar; infrastructure.i18n no longer exports I18nResourceSpec
- [ ] #3 The 4 contract (b) ignore entries 'packages.{access.sync,geolocate,incident_draft,incident_summary} -> infrastructure.i18n.resources' are deleted and no ignore entry is added
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack A layer 8b. Applies decisions/plugin-architecture.md (contracts is a leaf; infrastructure implements contracts Protocols) and decisions/i18n.md (resources registered through a hookspec in contracts/). Mechanical move plus one new Protocol; no behaviour change.

Why: register_i18n_resources is typed on the concrete infrastructure.i18n I18nResourceRegistry (infrastructure/plugins/specs.py:15,54). Contract (c) forbids contracts importing it, so the hookspec needs a Protocol, and the Protocol's argument type, I18nResourceSpec, must be in contracts too.

Found call sites:
- Definition: app/infrastructure/i18n/resources.py:16 (I18nResourceSpec frozen dataclass), :44 (I18nResourceRegistry, the implementation); re-exported at infrastructure/i18n/__init__.py:22,35.
- Production importers of I18nResourceSpec (8): packages/access/sync/__init__.py:14, packages/geolocate/__init__.py:6, packages/incident_draft/__init__.py:11, packages/incident_summary/__init__.py:11 (all `infrastructure.i18n.resources`), server/lifespan.py:29,202 (via infrastructure.i18n), infrastructure/i18n/service.py:44 (docstring example), infrastructure/i18n/__init__.py.
- Test importers (3 files): tests/unit/infrastructure/i18n/test_resources.py:7, tests/unit/infrastructure/i18n/test_service_startup.py:7, tests/integration/packages/geolocate/test_i18n_integration.py:5.
- I18nResourceRegistry stays in infrastructure (importers: specs.py, manager.py, lifespan.py:28,189; tests test_i18n_hook_discovery.py:3). Its users are untouched in this layer.
- import-linter (b): pyproject.toml "packages.{access.sync,geolocate,incident_draft,incident_summary} -> infrastructure.i18n.resources" (4 entries) go away.

Steps:
1. app/contracts/i18n/__init__.py (docstring only) and app/contracts/i18n/resources.py: I18nResourceSpec moved verbatim (validation unchanged) and I18nResourceRegistrar(Protocol) with register(self, spec: I18nResourceSpec) -> None. No app imports.
2. infrastructure/i18n/resources.py imports the spec from contracts.i18n.resources and keeps the registry; infrastructure/i18n/__init__.py stops exporting I18nResourceSpec; service.py docstring example updated.
3. Rewrite the 4 package hookimpls and server/lifespan.py to import the spec from contracts.i18n.resources.
4. infrastructure/plugins/specs.py: register_i18n_resources(self, registry: I18nResourceRegistrar); docstring updated.
5. pyproject.toml: delete the 4 contract (b) entries. Add none.
6. Rewrite the 3 test imports in place.

Tests first:
- app/tests/unit/contracts/i18n/test_i18n_contracts_resource_spec_validation.py: spec validation (empty owner/path, bad format) via the contracts import; AST scan that contracts/i18n imports no app module.
- app/tests/unit/contracts/i18n/test_i18n_contracts_registrar_protocol.py: the concrete I18nResourceRegistry is assignable to I18nResourceRegistrar (mypy) and a hookimpl registers through a fake registrar.
- Existing test_resources.py, test_service_startup.py, test_i18n_integration.py, test_i18n_hook_discovery.py stay green (import lines only).

Verify: rg "I18nResourceSpec" app shows contracts.i18n as the only source; lint-imports 8 kept, contract (b) 57 -> 53 ignored; gates.
AC map: #1 step 1 + Protocol tests; #2 steps 2-3 + rg; #3 step 5 + lint-imports; #4 gates.
Size: 12 production files (2 new, 10 edited: resources.py, i18n/__init__.py, service.py, 4 hookimpls, lifespan.py, specs.py, pyproject.toml), about 80 LOC, mostly moved lines and one-line import swaps. One subsystem. File count passes the gate only because the no-shim rule forces every importer into this change; do not split.
Blast radius: type-level; the dataclass is unchanged. Rollback: git revert.
Assumption: nothing else constructs I18nResourceSpec outside app/ and tests; verify with rg at the repo root.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: Guillaume Charest
created: 2026-10-01 14:59
---
Plan approved 2026-10-01 (Guillaume Charest, in session), as written. See the TASK-107 approval comment for the decisions confirmed across layers 8a-8d.
---
<!-- COMMENTS:END -->
