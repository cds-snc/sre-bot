---
id: TASK-114.3
title: >-
  Package generator emits only the parts a package uses: optional layout entries
  by explicit option, required core always
status: To Do
assignee: []
created_date: '2026-11-09T14:04:00Z'
labels:
  - tooling
milestone: m-3
dependencies:
  - TASK-114.2
references:
  - decisions/feature-packages.md
  - decisions/plugins.md
  - app/bin/new_package.py
  - app/bin/package_templates
  - app/tests/integration/bin/test_bin_package_generator_create.py
parent_task_id: TASK-114
priority: medium
ordinal: 495000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found at the TASK-25.10 plan (2026-11-09). A scratch-copy dry run of make new-package for the first capability (text_generation) emitted empty hookspecs.py, interfaces.py, service.py and entrypoints/. That capability has no extension point, no orchestration and no inbound handler, so all four would be deleted by hand as dead code.

CAUSE: TASK-114's description said the generator emits 'the layout', and TASK-114.2 AC #5 gave every capability api.py and hookspecs.py. But decisions/feature-packages.md's layout table marks hookspecs.py and interfaces.py as optional. The shape check passes empty files either way, so nothing caught the divergence. The table is also silent on service.py and entrypoints/ for a capability whose api.py Protocol is implemented directly by its adapters (a driven port: text generation, and the workplace systems and people capabilities to come). That capability has no service and no handler: an ADR gap.

PRACTICE: generators emit a required core and add optional parts only on an explicit option. NestJS's resource generator asks for the transport layer and whether to generate CRUD entry points, and --no-spec skips tests (docs.nestjs.com/recipes/crud-generator). Rails skips components with --skip-* (guides.rubyonrails.org/command_line.html). Backstage scaffolder steps run conditionally on template parameters (backstage.io/docs/features/software-templates/writing-templates). Nx generators gate optional template folders on schema options. An empty placeholder module is dead code (memory rule: delete dead code), and it suggests a contract the package does not have: an empty hookspecs.py points at a capability order that nothing declares yet (plugins.md).

TARGET: the generator always emits the core for each kind and adds each optional entry only when asked. Feature or subdomain core: __init__.py (register_requirements), README.md, service.py and entrypoints/. Capability core: __init__.py, README.md and api.py. Options: --settings (exists), --hookspecs (capability only), --interfaces, --service and --entrypoints (capability only; a feature always has both), --adapters (an adapters/__init__.py). The interactive make new-package asks the same yes/no questions. feature-packages.md marks service.py and entrypoints/ optional for a capability, with the driven-port case named. Its Changes line rides with this PR.

Production: tooling only. Nothing under app/features, app/capabilities or config changes; one revert undoes it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A capability generated with no optional flag holds exactly __init__.py, README.md and api.py; each of --hookspecs, --interfaces, --service, --entrypoints, --adapters and --settings adds only its entry, and the result passes make check-package-shape with an empty baseline (per-combination generator test)
- [ ] #2 A feature or subdomain still gets service.py and entrypoints/ by default; --interfaces, --adapters and --settings add theirs; existing kinds (umbrella, core, common, promote) behave as before (their generator tests unchanged)
- [ ] #3 --hookspecs is refused for any kind but a capability, and --service/--entrypoints opt-outs are not offered for a feature, each with a message naming feature-packages.md; the interactive mode asks the same questions
- [ ] #4 decisions/feature-packages.md's layout table marks service.py and entrypoints/ optional for a capability whose api.py Protocol is implemented by its adapters, and states that the generator emits optional entries only on request; dated Changes line
- [ ] #5 ruff, the targeted generator tests, mypy, pytest tests --ignore=tests/smoke, make check-package-shape and make check-import-contracts pass, with output in notes
<!-- AC:END -->
