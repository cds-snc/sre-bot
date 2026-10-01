---
id: TASK-114
title: >-
  Build the package generator and the CI package-shape check for app/features/
  and app/capabilities/
status: To Do
assignee: []
created_date: '2026-09-24 19:59'
updated_date: '2026-10-01 14:06'
labels:
  - plugin-architecture
  - tooling
milestone: m-7
dependencies:
  - TASK-110
  - TASK-112
references:
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - decisions/plugins.md
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

Amended 2026-10-01 to decisions/feature-packages.md umbrella rules 4 and 5: core/ may do I/O but is not a plugin; common/ does no I/O.

Operator tooling lives in app/bin/ (decisions/migration.md). Follow the existing guardrail-script shape: a script, a make target, a CI step.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The generator creates a feature, a capability, an umbrella subdomain, or an umbrella's core/ in the layout-table shape; plugins get their entry-point line and enablement key, core/ gets neither; a generated package boots and passes the gates unchanged
- [ ] #2 The CI shape check fails on a top-level name outside the feature-packages.md table in any package under app/features/ or app/capabilities/, on a non-empty umbrella __init__.py, on an umbrella core/ with entrypoints/, hookimpls or an entry point, and on an umbrella common/ holding adapters/, a store or a provider module
- [ ] #3 Capability packages are checked for README classification and at least one named feature consumer (plugin-architecture.md Checks)
- [ ] #4 The check is a script under app/bin/ with a make target and a blocking CI step
<!-- AC:END -->
