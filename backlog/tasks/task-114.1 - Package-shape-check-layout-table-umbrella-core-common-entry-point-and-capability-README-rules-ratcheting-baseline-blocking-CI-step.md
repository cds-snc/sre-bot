---
id: TASK-114.1
title: >-
  Package-shape check: layout table, umbrella, core/common, entry-point and
  capability README rules, ratcheting baseline, blocking CI step
status: In Progress
assignee: []
created_date: '2026-11-06T02:56:00Z'
updated_date: '2026-11-06T03:13:00Z'
labels:
  - plugin-architecture
  - tooling
milestone: m-7
dependencies:
  - TASK-112.2
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - decisions/plugins.md
  - decisions/product-scope.md
parent_task_id: TASK-114
ordinal: 487000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
First slice of TASK-114 (split 2026-11-06, human: two PRs, a read-only guard and the generator). A script under app/bin/ checks every package under app/features/ and app/capabilities/ against the decisions/feature-packages.md layout table, as amended in this PR (interfaces.py; service and domain may grow into packages; plugin.py when an entry point names it). It also implements two checks the ADRs promise and nothing runs: every package shipping hookimpls has an entry-point line (plugins.md) and subdomain entry-point names are dotted (feature-packages.md rule 6). Known violations sit in a ratcheting baseline, each entry naming the task that removes it. The ADR amendments ruled on 2026-11-06 ride with this PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The check fails on a top-level name outside the amended feature-packages.md table in any package under app/features/ or app/capabilities/, on a non-empty umbrella __init__.py, on a .py module at an umbrella root, on an umbrella core/ with entrypoints/, hookimpls or an entry point, and on an umbrella common/ holding adapters/, a store or a provider module
- [x] #2 interfaces.py is allowed; service and domain may each be a module or a package of that name; plugin.py is allowed only where an entry point names it; api.py and hookspecs.py only in capabilities, and api.py in an umbrella core/
- [x] #3 The check fails when a package under features/ or capabilities/ defines hookimpls and no entry point names it or its plugin module, and when a subdomain entry point is not named <feature>.<subdomain>
- [x] #4 A capability fails without a README holding a Classification section (generic or supporting) and a Feature consumers section naming at least one package under app/features/; a capability whose first consumer is a queued task is a baseline entry naming that task
- [x] #5 Known violations live in app/bin/baselines/package_shape.txt, each group naming its owning task; a new violation fails, a fixed one is reported stale; the real tree passes
- [x] #6 The check is app/bin/check_package_shape.py with make check-package-shape and a blocking step in .github/workflows/ci_code.yml
- [x] #7 decisions/feature-packages.md, plugin-architecture.md, plugins.md and product-scope.md carry the 2026-11-06 amendments and their Checks lines name the script
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-06 (human; OQ1-OQ9 rulings in TASK-114's plan). Planning edits ride with this slice's code PR.

Size: ~320 production LOC, 5 production files (check ~260, baseline ~25, Makefile +4, CI +4, cloud_operations/__init__.py docstring removed) plus 4 ADRs. One concept: a read-only guard. Gate passes.

Steps
1. ADR amendments (dated Changes line each):
   - feature-packages.md Layout: add `interfaces.py  # the Protocols service.py depends on, implemented in adapters/ (optional)` and `plugin.py  # the hookimpls, when the host reads the package's settings before plugins load; the entry point names it (plugins.md)`; a note that service.py and domain.py may each grow into a package of the same name. Checks: the shape check (app/bin/check_package_shape.py, baseline app/bin/baselines/package_shape.txt) covers the table, umbrella init, core/ and common/, dotted entry-point names (moved from grep and review) and the capability README.
   - plugin-architecture.md capability test 1: "at least one feature needs it now, or its first consumer is a queued task; until that consumer merges the capability is a baseline entry of the shape check naming it". Checks line 119 names the script and the README format.
   - plugins.md Checks line 79 ("every package that ships hookimpls has a matching entry-point line") names the script. Rule: a capability consumed by one product area takes its enablement key in that area's table; one consumed by two or more areas goes in a [plugins.shared] table no area switch turns off, built by the first cross-area capability task (TASK-83.4 or TASK-122, whichever first).
   - product-scope.md: the same placement rule next to the table.
2. app/bin/check_package_shape.py (shape of check_aws_platform_seam.py; module globals FEATURES_ROOT, CAPABILITIES_ROOT, BASELINE_PATH, PYPROJECT_PATH monkeypatchable; report() from freeze_guard):
   - ALLOWED_FILES = __init__.py, README.md, settings.py, service.py, domain.py, interfaces.py, schemas.py, store.py, providers.py, plugin.py; capability-only api.py, hookspecs.py (api.py also in an umbrella core/). ALLOWED_DIRS = adapters, entrypoints, locales, service, domain. __pycache__ ignored; contents of allowed dirs not name-checked.
   - Classification (D1): a directory is an umbrella iff it has a child package outside ALLOWED_DIRS and no entry point targets it or its plugin module; otherwise flat. Umbrella children: subdomains (table), core/ (table without entrypoints/, plugin.py; no hookimpl; no entry point), common/ (no adapters/, store.py, providers.py).
   - Entry points read from [project.entry-points.sre_bot] with tomllib; only targets under features./capabilities. are checked.
   - Rules and keys: unknown name "<path>"; "<path>:umbrella-init" (any bytes); umbrella root .py "<path>"; "<path>:core-entrypoints|core-hookimpl|core-entry-point"; common "<path>"; plugin.py with no entry point "<path>:plugin-unnamed"; hookimpls (ast: decorator named hookimpl) in __init__.py or plugin.py with no entry point "<pkg>:no-entry-point"; entry-point name not "<feature>" for a flat feature/capability or "<feature>.<subdomain>" for a subdomain "<name>:entry-point-name"; capability README "<path>:readme-missing|readme-classification|readme-consumers".
   - README format (case-sensitive): "## Classification" then a line "generic" or "supporting"; "## Feature consumers" then bullets "- features.<feature>[.<subdomain>]" resolving to a directory under app/features/.
3. Baseline seed (run with an empty baseline; the output must equal this list): incident/comms approval.py, comms_profile.py, form.py, history.py, ports.py, prompt.py, publisher.py (TASK-186); incident/core/legacy_upgrade.py and incident/response/legacy_upgrade_job.py (TASK-145.13); incident/scheduling/availability.py (TASK-138). Header comments per group name the owner, as aws_platform_seam_consumers.txt does. response/plugin.py is allowed by the amended table; cloud_operations/__init__.py is fixed, not baselined.
4. app/Makefile check-package-shape (+ .PHONY); ci_code.yml blocking step after "Settings key ownership check".

Tests: app/tests/unit/bin/test_bin_package_shape_check.py (tmp tree + monkeypatch, as test_bin_aws_platform_seam_check.py), one test per rule:
- AC #1: unknown file; unknown dir; platforms/ dir; non-empty umbrella init (code, docstring); .py at umbrella root; core/ with entrypoints/, with a hookimpl, targeted by an entry point; common/ with adapters/, store.py, providers.py; the full allowed table passes; __pycache__ ignored; umbrella vs flat classification (entry-point tie-break; settings-only subdomain).
- AC #2: interfaces.py passes; service/ and domain/ packages pass; plugin.py with an entry point passes, without one fails; api.py in a feature fails, in core/ passes, in a capability passes.
- AC #3: hookimpl with no entry point fails; subdomain entry point "sync" fails, "access.sync" passes; flat feature named otherwise fails.
- AC #4: missing README, missing/invalid classification, no consumers, unresolvable consumer fail; valid passes; features are not subject.
- AC #5: baselined violation passes; new one fails; fixed one reported stale; the real repo tree exits 0.
- AC #6/#7: make target and CI step present (review); ADR lines (review).
Assumptions (verify): app/capabilities/ absent; no Stack K PR adds a top-level name (gh pr list before merge; re-seed after rebase); the violation list is complete (step 3 diff).
Blast radius: a blocking CI step; a branch adding an off-table name fails until it follows the table or a reviewed ADR amendment. No runtime change; one git revert removes it.
Domain-model evolution: N/A (directory names, no entity or stored record).
Gates: ruff and the targeted test during TDD; at the end make check-import-contracts, make check-settings-key-ownership, make check-package-shape, full mypy then full pytest, once each.

Step 1 status: the ADR amendments were written during planning on 2026-11-06 (same branch); implementation re-reads them against the code it ships and fixes any wording drift.

Correction 2026-11-06: TASK-138 is superseded (TASK-169 D5, calendar stays incident-owned); the scheduling/availability.py baseline entry is owned by TASK-145.10 (AC added there), not 138.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06: implemented with TDD on task-114-package-generator (same session as planning, human).
- app/bin/check_package_shape.py: umbrella detection per D1 (no entry point names it or its plugin module, and it holds a directory outside adapters/entrypoints/locales/service/domain); rules and keys as in its docstring. An umbrella __init__.py may hold whitespace only.
- Baseline seeded from main (#1827 adds no top-level name): 10 entries, comms x7 -> TASK-186, core/legacy_upgrade.py and response/legacy_upgrade_job.py -> TASK-145.13, scheduling/availability.py -> TASK-145.10.
- features/cloud_operations/__init__.py emptied; its sentence moved to a new features/cloud_operations/README.md (umbrella roots allow README.md).
- freeze_guard.py docstring names the new consumer; plugin-architecture.md Checks wording tightened to what the check enforces (each consumer bullet must resolve).
- Tests: tests/unit/bin/test_bin_package_shape_check.py, 41 passed (one per rule, the ratchet, and the real tree).
Gates: ruff check . clean; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK; make check-package-shape OK (10 baselined); mypy 41 errors in 14 files, pre-existing, none in touched files (run twice: the second only to filter, a slip against run-once); pytest tests --ignore=tests/smoke 6390 passed.
Follow-up proposed, not done (outside this task's files): add make check-package-shape to the delivery-session skill's gate list.
<!-- SECTION:NOTES:END -->
