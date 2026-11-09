---
id: TASK-114.3
title: >-
  Package layout manifest: one declarative source for the layout table, read by
  the package-shape check
status: In Progress
assignee: []
created_date: '2026-11-09T14:04:00Z'
updated_date: '2026-11-09T15:53:00Z'
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
First slice of the package-layout source of truth (re-planned 2026-11-09, human-approved split: 114.3 manifest and shape check, 114.4 generator, 114.5 remaining bin guards).

WHY: the layout table of decisions/feature-packages.md is hand-copied into bin/check_package_shape.py (PACKAGE_FILES :63-76, CAPABILITY_FILES :77, PACKAGE_DIRS :78, UMBRELLA_ROOT_FILES :79, COMMON_IO_NAMES :82, CLASSIFICATIONS :84, README headings :85-86), bin/new_package.py (:71-83, _files :282-308) and bin/package_toml.py (:30-33). Found at the TASK-25.10 plan: the generator emitted empty hookspecs.py, interfaces.py, service.py and entrypoints/ for a driven-port capability because nothing ties it to the table (TASK-114.4 fixes the behaviour).

RESEARCH (2026-11-09): no tool both scaffolds and enforces a per-kind layout. uv init has no templates; ruff has no custom rules (astral-sh/ruff#283); ty checks types only. Copier renders conditional files but cannot edit root pyproject/base.toml or lint; Tach duplicates import-linter and checks no file layout; ls-lint would be a second source of truth. Nx's pattern fits: one declarative per-kind record read by generators and linters (nx.dev enforce-module-boundaries). Human rulings: manifest at app/bin/package_layout.toml; loaded with tomllib into frozen dataclasses (trusted repo input, type-model-boundaries); no JSON Schema for now; import-linter contracts stay generator-written (no contract generation). Ruff INP001 rides here (human: add to current tasks): every package needs __init__.py, the manifest's one universal required entry; tests/** is exempt (tests/ has no __init__.py by design, pytest pythonpath ["."], 112 hits all under tests).

TARGET: app/bin/package_layout.toml is the machine copy of the layout table: kinds (feature, subdomain, capability, core, common, umbrella), each with required, optional and forbidden entries (a trailing / marks a directory), the README rules for a capability, classifications and reserved subdomain names. bin/package_layout.py loads and validates it. check_package_shape.py reads it, with the same rules and violation keys as today. A drift test keeps the names in feature-packages.md's table equal to the manifest's. Tooling only; one revert restores it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/bin/package_layout.toml declares every kind (feature, subdomain, capability, core, common, umbrella) with its required, optional and forbidden entries, the capability README rules, classifications and reserved subdomain names; bin/package_layout.py loads it with tomllib into frozen dataclasses and refuses a malformed manifest naming the offending key
- [x] #2 check_package_shape.py holds no layout name constants and reads the manifest; its tests pass unchanged and make check-package-shape on main reports the same result before and after
- [x] #3 A drift test fails when decisions/feature-packages.md's layout table and the manifest name different entries; feature-packages.md names the manifest as the table's machine copy, with a dated Changes line; bin/package_templates/README.md says the same
- [x] #4 Ruff INP001 is enabled for app code (tests/** exempt) and reports nothing
- [x] #5 ruff, the targeted bin tests, then mypy and pytest tests --ignore=tests/smoke once each, make check-package-shape, check-import-contracts, check-settings-key-ownership and check-test-seams pass, with output in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Re-planned 2026-11-09 against main d3778e0a (supersedes the earlier plan in this field; split approved by the human). Domain-model gate: not applicable (tooling data, no domain entity).

STEPS
1. Tests first (red):
   a. app/tests/unit/bin/test_bin_package_layout_load.py (new):
      - the real manifest loads; every kind has __init__.py required; required, optional and forbidden are disjoint per kind; capability allows api.py and hookspecs.py, core allows api.py and not plugin.py or entrypoints/, umbrella allows only __init__.py and README.md; common forbids adapters/, store.py, providers.py.
      - malformed manifests (written to tmp_path) are refused with a message naming the key: unknown top-level or kind key, an entry both required and optional, a name with a path separator other than one trailing /, an unknown kind referenced, an empty classification list.
      - drift: the names in decisions/feature-packages.md's layout code block (the lines after "app/features/<feature>/" up to the closing fence, names before the comment, "/" kept) equal the union of the flat-package kinds' names in the manifest. The test failure message says to amend the ADR and the manifest together.
   b. app/tests/unit/bin/test_bin_package_shape_check.py: unchanged (it patches only the path constants, :48-52); it is the refactor's safety net.
2. app/bin/package_layout.toml (new, ~70 lines, comments name feature-packages.md as the authority):
   [roots] features, capabilities. [kinds.feature] required ["__init__.py", "README.md", "service.py", "entrypoints/"], optional [settings.py, domain.py, interfaces.py, schemas.py, store.py, providers.py, plugin.py, service/, domain/, adapters/, locales/]. [kinds.subdomain] same as feature. [kinds.capability] feature's plus api.py required and hookspecs.py optional (service.py, entrypoints/ stay required here, as the table reads today; 114.4 moves them). [kinds.core] required [__init__.py, README.md, api.py, service.py], optional as feature minus plugin.py, entrypoints/. [kinds.common] required [__init__.py, README.md], forbidden [adapters/, store.py, providers.py] and open otherwise (today's rule). [kinds.umbrella] required [__init__.py, README.md], no optional. [capability_readme] classification_heading, consumers_heading, classifications ["generic", "supporting"]. reserved_subdomains [core, common, adapters, entrypoints, locales, service, domain].
3. app/bin/package_layout.py (new, ~110 LOC): frozen dataclasses Kind (name, required, optional, forbidden, open: bool) with allowed_files / allowed_dirs properties; Layout (roots, kinds, capability README rules, reserved_subdomains); load_layout(path=LAYOUT_PATH) -> Layout with tomllib and explicit validation raising LayoutError; functools.cache on the default path. Public names typed; no Pydantic (trusted repo input).
4. app/bin/check_package_shape.py: delete PACKAGE_FILES, CAPABILITY_FILES, PACKAGE_DIRS, UMBRELLA_ROOT_FILES, COMMON_IO_NAMES, CLASSIFICATIONS and the README heading constants (:63-86); each function takes the allowed names from load_layout() kinds (flat package = feature, capability, subdomain inside an umbrella, core, common, umbrella root). The umbrella detection keeps its rule (a child directory outside the allowed directories of a flat package). Violation keys, the core-entrypoints special key, the baseline and the module's path constants are unchanged. Docstring points at the manifest.
5. app/pyproject.toml: ruff select gains "INP"; per-file-ignores "tests/**" gains "INP001". Check: uv run ruff check . finds no INP001 outside tests.
6. decisions/feature-packages.md: one sentence under the table: app/bin/package_layout.toml is the table's machine copy, read by the shape check and (TASK-114.4) the generator; amend both together, a drift test fails otherwise. Checks list: the shape check reads the manifest. Dated Changes line. bin/package_templates/README.md: the 'update the table and check_package_shape.py' bullet becomes 'the table and the manifest'.
7. Gates: ruff; targeted tests (layout load, shape check, generator create); then once, sequentially, full mypy and full pytest; make check-package-shape, check-import-contracts, check-settings-key-ownership, check-test-seams.

AC TRACEABILITY
- AC #1 manifest and loader -> steps 2, 3; tests 1a (load, validation).
- AC #2 shape check reads it, unchanged behaviour -> step 4; tests 1b unchanged plus make check-package-shape on main (same 10 baselined entries, no new violation).
- AC #3 drift test and ADR sentence -> steps 1a (drift), 6.
- AC #4 INP001 -> step 5; ruff output in notes.
- AC #5 gates -> step 7.

TEST MATRIX
- Happy: real manifest loads; shape check verdicts unchanged across its 347-line suite; generator tests still pass (the generator is untouched here).
- Boundary: common's open allow-list; core's entrypoints/ reported as core-entrypoints, not as a stray name; service/domain as module or package.
- Failure: each malformed-manifest case refused with the offending key; drift test fails when a name is added to only one side (checked by a mutation during implementation).

SIZE: production 3 new or changed bin files (~110 + ~70 + about -40/+25 LOC), pyproject 2 lines, 1 ADR, 1 template README: about 230 LOC, 6 files, one subsystem (bin tooling). Passes the gate. Pure refactor plus a lint rule; behaviour change is 114.4.

ASSUMPTIONS (verify at implementation)
- The shape check's verdicts depend only on the name sets, not their order: confirmed by reading :143-199; re-check after the edit by running make check-package-shape on main before and after (same output).
- INP001 has no hit outside tests/: measured 2026-11-09 (112 hits, all tests/**); re-run.
- The ADR code block is parseable as one name per line before '#': true for :28-44 today; the drift test pins it.

BLAST RADIUS AND ROLLBACK
Tooling and CI only; nothing under app/features, app/capabilities, config or terraform; nothing deploys at runtime. Failure mode: a wrong manifest makes CI's shape step fail or pass wrongly; the unchanged shape tests and the before/after check output guard that. One git revert restores it. 114.4 and 114.5 build on it, so they wait for its merge.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (TASK-25.10 review, human): OQ4 ruled, TASK-114.3 as proposed. Planned the same day against main d3778e0a; ACs #2 and #3 tightened (core takes --interfaces/--adapters; the per-kind option table and the --interfaces-needs---service rule); proposed, awaiting approval.

2026-11-09 (human): OQ1 approved (core takes --interfaces/--adapters; --interfaces needs --service on a capability), OQ2 approved (layout table marks adapters/ and locales/ optional), OQ3 approved (planned-consumer option stays with TASK-83.4). Scope widened before approval of the plan: the generator's final shape must be tidy, deduplicated and flexible, and the package shape (and if possible the contract checks) must come from one declarative source of truth that new_package.py, check_package_shape.py and possibly other app/bin scripts read; evaluate modern libraries and dev tools (Astral ecosystem first) to reduce maintenance. Re-plan in progress; the 2026-11-09 plan above is superseded once the re-plan is written.

2026-11-09 (human): the widened scope is dev tooling only (no production code) and is wanted now as a repo cleanup. The single-PR size gate still applies: if the re-plan exceeds it, it splits into sequential tooling-only subtasks, each revertible on its own.

2026-11-09 (human): re-plan approved: Q1 split into 114.3 (manifest + shape check), 114.4 (generator) and 114.5 (other bin guards); Q2 manifest at app/bin/package_layout.toml; Q3 no import-linter contract generation now; Q4 no JSON Schema now; Q5a ruff INP001 rides here; Q5b env-name dedup rides with 114.5. The original behaviour change and OQ1/OQ2 moved to TASK-114.4. Plan rewritten; awaiting approval.

2026-11-09 implemented on task-114.3-package-layout-manifest from main d3778e0a (re-plan approved by the human with the queue prompt). app/bin/package_layout.toml (kinds feature, subdomain, capability, core, common, umbrella; extends/exclude between kinds; grows_into_package declares service.py/domain.py may become packages, so the manifest's names equal the ADR table's exactly) and bin/package_layout.py (tomllib into frozen dataclasses Kind/Roots/Layout; LayoutError naming the key: unknown keys, missing keys, required-and-optional, nested paths, unknown base kind, extends cycles, exclude of an absent name, empty classifications, bad headings; layout() cached). check_package_shape.py: layout constants deleted (PACKAGE_FILES, CAPABILITY_FILES, PACKAGE_DIRS, UMBRELLA_ROOT_FILES, COMMON_IO_NAMES, CLASSIFICATIONS, headings); roots, names and README rules from the manifest; path constants kept (tests patch them). Behaviour unchanged: shape tests untouched and passing; find_violations() on the repo identical before and after (3 entries); make check-package-shape output identical. Mutations: a manifest-only name fails the drift test (and 2 shape tests); dropping core's api.py fails 15 tests. Ruff INP enabled, tests/** exempt (INP001): 0 hits in app code. ADR: feature-packages.md (manifest sentence, Checks: manifest and INP001, Changes line); bin/package_templates/README.md. Gates: ruff check . all passed; ruff format clean; targeted bin tests 83 passed; check-package-shape OK (3 baselined); check-import-contracts 13 kept, 0 broken; check-settings-key-ownership OK; check-test-seams OK (47 + 12); mypy 41 errors in 14 files, all pre-existing legacy modules/ (none in bin/ or tests/unit/bin; run twice by mistake, the second only to filter); pytest tests --ignore=tests/smoke 6586 passed. Merge deploys nothing (bin tooling, ruff config, ADR). Done is the human's.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-09T15:24:00Z

---

Re-plan proposal (2026-11-09), awaiting the human's approval: the widened scope trips the size gate (~580 LOC, refactor mixed with behaviour change). Research: no Astral tool scaffolds or lints layout (uv init has no templates; ruff has no custom rules, #283; ty is types only); Copier renders conditional files but cannot edit root pyproject/base.toml or lint; Tach duplicates import-linter and checks no layout; ls-lint would be a second source of truth. Nx's pattern (one declarative per-kind record read by generators and linters) fits. Proposed: 114.3 narrowed = app/bin/package_layout.toml manifest + frozen-dataclass loader + check_package_shape.py reads it (refactor, tests unchanged) + drift test ADR table == manifest; 114.4 = generator reads the manifest, optional entries by option (the approved behaviour, OQ1/OQ2), feature-packages.md edits; 114.5 = package_toml.py, check_test_seams.py, check_fake_coverage.py read roots and names from it. Not adopted: Tach, ls-lint, Copier (for now), JSON Schema (for now), contract generation. Follow-ups proposed as separate tasks: ruff INP001; audit_env_names/check_settings_key_ownership platform-name overlap.

---
<!-- COMMENTS:END -->
