---
id: TASK-124
title: >-
  Move the existing feature packages from app/packages/ to app/features/, one
  per PR, and delete app/packages/
status: To Do
assignee: []
created_date: '2026-09-24 20:01'
updated_date: '2026-09-24 20:02'
labels:
  - plugin-architecture
  - features
milestone: m-7
dependencies:
  - TASK-88
  - TASK-124.1
  - TASK-124.2
  - TASK-124.3
  - TASK-124.4
  - TASK-124.5
  - TASK-124.6
references:
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
priority: medium
type: task
ordinal: 266000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: contains no implementation. decisions/plugin-architecture.md: "Features already in packages/ move to features/ one per PR, with every importer rewritten, legacy ones included." feature-packages.md accepts the cost: every package renames platforms/ and interactions/ to entrypoints/, and incident_draft and incident_summary move under the incident umbrella.

Children (one PR each): access (umbrella), geolocate, oncall_sync, rant, talent, and the incident umbrella (scheduling, draft, summary).
user_rotations becomes a capability instead (its own ticket). packages/aws_platform is dissolved by TASK-88, not moved.

Rule that keeps each move final: a package moves only once every infrastructure service it uses is reachable as a contract from the service registry, or as a capability's api.py. Its move then adds no import-linter ignore entry, and nothing is moved and then rewired later. Each child's dependencies encode that.

Common acceptance for every child:
- features/<name>/ passes the shape check;
- platforms/ and interactions/ are renamed entrypoints/;
- providers.py resolves contracts from the registry and imports no infrastructure;
- integrations are imported only from adapters/;
- the entry point targets features.<name> (dotted for subdomains), and the enablement key exists;
- the slice's non-secret values live in the TOML files;
- packages/<name> is deleted, with every importer and mock patch string rewritten;
- import-linter ignore entries only shrink.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every child task is Done
- [ ] #2 app/packages/ does not exist; packages is removed from the import-linter root packages, the ruff isort first-party list and the TASK-18 contracts
- [ ] #3 decisions/feature-packages.md and plugins.md no longer list packages/ or platforms/ directories as tolerated
<!-- AC:END -->
