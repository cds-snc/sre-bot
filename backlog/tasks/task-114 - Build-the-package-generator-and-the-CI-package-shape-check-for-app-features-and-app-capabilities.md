---
id: TASK-114
title: >-
  Build the package generator and the CI package-shape check for app/features/
  and app/capabilities/
status: To Do
assignee: []
created_date: 2026-09-24 19:59
updated_date: '2026-11-06T03:00:00Z'
labels:
  - plugin-architecture
  - tooling
milestone: m-7
dependencies:
  - TASK-110
  - TASK-112.2
references:
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - decisions/plugins.md
  - https://github.com/cds-snc/sre-bot/issues/1657
priority: medium
type: feature
ordinal: 256000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md ("One package shape, enforced by tooling") and feature-packages.md: a generator creates new packages in the layout-table shape, and a CI shape check rejects any top-level name outside the table in a package under features/ or capabilities/, including each umbrella subdomain and an umbrella's core/. The table grows only by amending feature-packages.md. Its success criterion: a new contributor runs the generator and is productive in an afternoon.

The generator emits, for a feature, a capability or an umbrella subdomain:
- the layout (__init__.py with hookimpls, README.md, settings.py, service.py, entrypoints/, and so on; api.py and hookspecs.py for capabilities);
- the entry-point line in pyproject.toml, with a dotted name for subdomains;
- the enablement key in the base configuration file;
- an empty umbrella __init__.py when creating an umbrella;
- on request, an umbrella's core/ (the layout without entrypoints/ and hookimpls, with api.py as its public surface, no entry-point line and no enablement key) and common/.

decisions/feature-packages.md umbrella rules 4 and 5: core/ may do I/O but is not a plugin; common/ does no I/O.

Operator tooling lives in app/bin/ (decisions/migration.md). Follow the existing guardrail-script shape: a script, a make target, a CI step.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The generator creates a feature, a capability, an umbrella subdomain, or an umbrella's core/ in the layout-table shape; plugins get their entry-point line and enablement key, core/ gets neither; a generated package boots and passes the gates unchanged
- [ ] #2 The CI shape check fails on a top-level name outside the feature-packages.md table in any package under app/features/ or app/capabilities/, on a non-empty umbrella __init__.py, on an umbrella core/ with entrypoints/, hookimpls or an entry point, and on an umbrella common/ holding adapters/, a store or a provider module
- [ ] #3 Capability packages are checked for README classification and at least one named feature consumer (plugin-architecture.md Checks)
- [ ] #4 The check is a script under app/bin/ with a make target and a blocking CI step
- [ ] #5 The generator asks for the plugin's product area (one of decisions/product-scope.md's four) and writes the enablement key into that area's [plugins.<area>] table in base.toml, and adds the entry-point module to the import-linter protected-plugins contract
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-06 (human). Coordinator: split into two PRs, one concept each (human: fewer PRs, up to ~20 production files, split only where the concept changes):
- TASK-114.1 package-shape check, baseline, make target, blocking CI step, and the 2026-11-06 ADR amendments (AC #2, #3, #4). ~320 LOC, 5 production files.
- TASK-114.2 the generator for every kind: feature, capability (the first creates app/capabilities/), umbrella, subdomain, core/, common/ (AC #1, #5). ~650 LOC, ~16 files (accepted exception on LOC; one concept). Waits on 114.1.
- TASK-186 (new) reshapes incident/comms into the amended table; waits on 114.1; gates 145.13.
This task's ACs are checked when both subtasks are Done.

Rulings (assessed against the ADRs, doc-11, doc-15 and prior tasks; written to the ADRs in 114.1's PR):
OQ1 gap: the table had no home for a subdomain's own Protocols or for a growing service/domain (comms ports.py and six helpers, oncall_sync ports.py; 145.4 carried them flat). Amend feature-packages.md: interfaces.py; service.py and domain.py may grow into packages of the same name. TASK-186 reshapes comms; TASK-124.2 renames oncall_sync's ports.py. Sources: hexagonal Python keeps the domain's Protocols in their own module beside it (dioxide docs, dev.to elpic); a module growing into a same-name package is accepted practice (Django ticket 25127).
OQ2 settled by plugins.md 2026-11-04 (an entry point may name a plugin submodule); the layout table gains plugin.py, allowed only where an entry point names it.
OQ3 settled (umbrella rule 1, Checks): umbrella __init__.py strictly empty; 114.1 empties cloud_operations/__init__.py.
OQ4 conflict (plugin-architecture.md "needed now" vs TASK-83.4 shipping people with no consumer, an expand step): amend to "needed now, or its first consumer is a queued task"; until it merges, the capability is a baseline entry naming it (people: TASK-165.2 or TASK-83.9, whichever merges first). No README escape hatch.
OQ5 no ADR: tomlkit document edits (Nx generators: structured edits over string replacement), verified with tomllib before writing; string.Template files; no copier (its value is template updates; the shape check guards drift).
OQ6 settled: api.py and hookspecs.py capability-only, api.py also in an umbrella core/.
OQ7: two promised checks exist nowhere (plugins.md: hookimpls imply an entry-point line; feature-packages.md: dotted subdomain names, was grep and review); both join 114.1.
OQ8: two PRs (above); dependents repointed: 25.10, 138, 146.1, 119, 122, 123, 125, 60, 62, 63, 83.4, 37.1, 39, 40 -> 114.2; 124.1, 124.2, 124.3, 124.4, 124.6 -> 114.1; 145.13 -> 186.
OQ9 gap: a capability consumed by two or more product areas takes its key in a [plugins.shared] table no area switch turns off (Backstage treats cross-plugin engines as shared services, not switchable plugins); one consumed by one area uses that area's table (oncall precedent, text generation -> incident_response). Rule written in 114.1 (plugins.md, product-scope.md); the table is built by the first cross-area capability task (83.4 or 122).

Correction 2026-11-06: TASK-138 is superseded (TASK-169 D5); its dependency was repointed to 114.2 harmlessly, but the scheduling/availability.py baseline entry belongs to TASK-145.10 (AC added). Archived TASK-123, 124.2 and 124.5 still name TASK-114 (read-only; TASK-146.2 AC #2 already removes oncall_sync's ports.py).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-29 (TASK-172): the generator's __init__.py template includes a register_requirements hookimpl stub (decisions/plugins.md and feature-packages.md 2026-10-29): a plugin states each vendor or capability it cannot run without there, none it uses optionally.

2026-10-29 (TASK-175 planning, human): register_requirements returns Requirement declarations the host resolves (decisions/plugins.md, feature-packages.md); the generator's __init__.py stub returns an empty list instead of resolving and raising.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-23T19:22:00Z

---

2026-10-23: waits on TASK-112.2 (plugin key shape: [plugins.<area>] tables mapping entry-point name to bool), not the whole of TASK-112.

---
<!-- COMMENTS:END -->
