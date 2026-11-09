---
id: TASK-114.4
title: >-
  Package generator reads the layout manifest and emits only the parts a package
  uses
status: To Do
assignee: []
created_date: '2026-11-09T15:41:00Z'
updated_date: '2026-11-09T15:42:00Z'
labels:
  - tooling
milestone: m-3
dependencies:
  - TASK-114.3
references:
  - decisions/feature-packages.md
  - app/bin/new_package.py
parent_task_id: TASK-114
priority: medium
ordinal: 496000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second slice of the TASK-114.3 re-plan (approved 2026-11-09). bin/new_package.py stops hard-coding kinds, files and options: it reads app/bin/package_layout.toml (TASK-114.3) for each kind's required entries, its optional entries with their option flags and templates, reserved subdomain names, classifications and roots. Behaviour (approved 2026-11-09, TASK-114.3 OQ1/OQ2 and the original plan): a kind always gets its required entries and each optional entry only on request, never an empty placeholder. Capability core = __init__.py, README.md, api.py; feature/subdomain core adds service.py and entrypoints/; core = __init__.py, README.md, api.py, service.py; options --hookspecs/--service/--entrypoints (capability only), --interfaces/--adapters (feature, subdomain, capability, core), --settings (as today); --interfaces without --service is refused for a capability; an option outside its kind is refused, nothing written; the interactive mode asks the options from the same manifest. decisions/feature-packages.md marks service.py and entrypoints/ optional for a driven-port capability and adapters/ and locales/ optional, states the generator rule, dated Changes line. Tooling only; one revert restores today's generator.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 new_package.py holds no per-kind file list, option list or classification list: kinds, entries, options, templates and reserved names come from the manifest loader (TASK-114.3)
- [ ] #2 A capability generated with no optional flag holds exactly __init__.py, README.md and api.py; each optional flag adds only its entry; every combination passes make check-package-shape with an empty baseline (parametrized generator test)
- [ ] #3 A feature or subdomain gets service.py and entrypoints/ by default and interfaces.py, adapters/ or settings.py only on request; core keeps api.py and service.py and gains interfaces.py or adapters/ only on request; umbrella, common and promote behave as before (their test assertions unchanged; the promote setup passes --interfaces)
- [ ] #4 An option outside its kind, or --interfaces without --service on a capability, is refused naming feature-packages.md with nothing written; the interactive mode asks each option the kind takes from the manifest
- [ ] #5 decisions/feature-packages.md: service.py and entrypoints/ optional for a capability whose api.py Protocol its adapters implement; adapters/ and locales/ optional; the generator emits optional entries only on request; dated Changes line; the manifest drift test (TASK-114.3) passes
- [ ] #6 ruff, targeted generator and shape tests, then mypy and pytest tests --ignore=tests/smoke once each, make check-package-shape and make check-import-contracts pass, with output in notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (human, ruled under TASK-114.3 before the split): OQ1 approved (core takes --interfaces/--adapters; --interfaces needs --service on a capability); OQ2 approved (the table marks adapters/ and locales/ optional); OQ3 approved (the planned-consumer option stays with TASK-83.4). Plan at pickup against main after 114.3 merges; the superseded 114.3 plan (git history of task-114.3) carries the test list for this behaviour.
<!-- SECTION:NOTES:END -->
