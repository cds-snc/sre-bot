---
id: TASK-114.2
title: >-
  Package generator: features, capabilities (the first creates
  app/capabilities/), umbrellas, subdomains, core/ and common/
status: Done
assignee: []
created_date: '2026-11-06T02:56:00Z'
updated_date: '2026-11-09T17:44:00Z'
labels:
  - plugin-architecture
  - tooling
milestone: m-7
dependencies:
  - TASK-114.1
references:
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - decisions/plugins.md
  - decisions/product-scope.md
  - decisions/migration.md
parent_task_id: TASK-114
ordinal: 488000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second slice of TASK-114 (split 2026-11-06, human). One generator for every package kind, sharing one template and TOML-edit engine. It writes the package in the layout-table shape and edits pyproject.toml and app/config/base.toml as tomlkit documents (a dev dependency; comments kept), re-checking the result with tomllib as the old data plus the intended delta before writing. Standard-library string.Template files; no copier (the shape check guards drift, so template updates are not needed). Success criterion (feature-packages.md): a new contributor runs it and is productive in an afternoon.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The generator creates a feature, a capability, an umbrella, an umbrella subdomain, or an umbrella's core/ or common/ in the layout-table shape; the generated package passes check-package-shape with an empty baseline, ruff, and registers on a plugin manager unchanged
- [x] #2 A plugin (feature, capability or subdomain) gets its entry-point line (dotted for a subdomain), its module in the protected-plugins contract, and its enablement key in the [plugins.<area>] table the user picks from product-scope.md's areas; core/, common/ and the umbrella get none
- [x] #3 A new feature is added to the feature-independence contract; a subdomain, core/ or common/ is added to its umbrella's exhaustive layers contract; a new umbrella gets its own layers contract
- [x] #4 The first capability creates app/capabilities/: capabilities joins root_packages, the wheel packages and the six-layer contract; later capabilities change none of those
- [x] #5 A plugin's __init__.py template holds a register_requirements hookimpl returning an empty list; a capability gets api.py, hookspecs.py and a README with the Classification and Feature consumers sections
- [x] #6 Each edit of pyproject.toml and base.toml keeps its comments and is verified with tomllib before it is written; a failed check writes nothing
- [x] #7 The generator prints the product-scope.md table row to add and is run by make new-package
- [x] #8 make new-package promote <feature> --subdomain <name> turns a flat plugin feature into an umbrella in place: its code becomes the subdomain, settings.py moves to common/ keeping its table and environment names, every features.<feature> reference in the app's Python is rewritten, the entry point and the enablement key in every configuration file are renamed <feature>.<subdomain>, and the umbrella gets its layers contract; a refused promotion changes nothing
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-06 (human; OQ5 tomlkit, OQ8 two PRs, OQ9 shared table rule). Re-verify file:line anchors against main when 114.1 has merged.

Size: ~650 production LOC, ~16 production files (new_package.py ~260, package_toml.py ~170, ~11 templates ~200, pyproject dev dependency, uv.lock, Makefile). Over the ~400 LOC guideline, inside the 20-file allowance (human, 2026-11-06: fewer PRs, split only where the concept changes); one concept (the generator), a third of it template text. Recorded as an accepted exception.

Steps
1. Dev dependency tomlkit (latest, 0.15.x) in the dev group; uv lock.
2. app/bin/package_toml.py: pure functions over tomlkit documents, each returning the edited document:
   - add_entry_point(doc, name, module); add_protected_plugin(doc, module); add_independent_feature(doc, "features.<name>"); add_umbrella_layer(doc, umbrella, member, kind) (subdomain joins the pipe-separated top layer in sorted order, core/common their own layers in order subdomains > core > common); add_umbrella_contract(doc, umbrella); bootstrap_capabilities(doc) (root_packages, hatch wheel packages; the "(capabilities)" optional layer stays as is, it already matches once the package exists) - each a no-op when already present (idempotent);
   - add_enablement_key(base_doc, area, name) under [plugins.<area>], value true in base (TASK-112.2 convention; off-everywhere areas are set by the author);
   - verify(old_text, new_doc, expected_delta): tomllib.loads(new) == apply(delta, tomllib.loads(old)); write only when equal, else raise and write nothing.
3. app/bin/new_package.py (argparse; make new-package runs it interactively when no args): kinds feature | capability | umbrella | subdomain | core | common; --area from product-scope.md's four tables (plus shared once [plugins.shared] exists); refuses an existing path or a name that is not lower snake_case; writes templates with string.Template; applies step 2 edits; prints the product-scope.md table row to add and the next steps (README consumers, tests path).
4. Templates app/bin/templates/package/: plugin __init__.py (register_requirements hookimpl returning [] and a docstring naming the package), README.md (feature), README.md (capability: ## Classification, ## Feature consumers), settings.py (a ConfigurationSlice on [<name>] with enabled-free fields), service.py, interfaces.py, entrypoints/__init__.py, api.py, hookspecs.py (capability), core api.py; umbrella __init__.py is written empty (no template).
5. Kind matrix: feature = layout + entry point + protected + independence + key; capability = layout + api.py/hookspecs.py/README + entry point + protected + key (+ bootstrap the first time); umbrella = empty __init__ + independence + umbrella contract (no entry point, no key); subdomain = layout + dotted entry point + protected + umbrella layer + key; core = layout without entrypoints/ and plugin files, api.py + umbrella layer; common = __init__ + umbrella layer.
6. Makefile new-package; docs: feature-packages.md Consequences names make new-package; README in app/bin/templates/package explains editing a template means updating the shape check if a name changes.

Tests
- app/tests/unit/bin/test_bin_package_toml_edit.py: each edit on a copy of the real pyproject.toml and base.toml keeps every comment line, is idempotent, and verify() rejects a stray change (writes nothing).
- app/tests/integration/bin/test_bin_package_generator_create.py: per kind, generate into a tmp tree with copies of pyproject.toml and base.toml; run check_package_shape (monkeypatched roots, empty baseline) -> no violations; tomllib re-parse asserts entry point, protected module equals entry-point module set (logic of test_the_protected_plugins_contract_lists_exactly_the_entry_point_modules in tests/integration/server/test_server_plugins_enablement_boot.py), enablement key and contracts; check_plugin_enablement over the tmp base.toml; import the generated package from the tmp root, register on a pluggy PluginManager with the contracts hookspecs, call register_requirements -> []; ruff over the generated files. Failure cases: existing path, bad name, unknown area, capability bootstrap only once.
- mypy is not run per generated package: one scratch package is generated during the PR and mypy's output recorded in the notes; the full mypy gate covers the templates' Python.
AC traceability: #1 integration per kind; #2 entry point/protected/key assertions; #3 independence and umbrella contract assertions; #4 bootstrap test; #5 template assertions; #6 toml edit tests; #7 make target and printed row (review + test of the printed text).
Blast radius: tooling only; it changes pyproject.toml and base.toml only when run. No runtime change; one git revert.
Domain-model evolution: N/A.
Gates: ruff and targeted tests during TDD; at the end make check-import-contracts, check-settings-key-ownership, check-package-shape, full mypy then full pytest, once each.

2026-11-06 (human, during implementation): add a promote kind to this PR (dev tooling only, no production risk): a flat plugin feature becomes an umbrella in place, keeping its name (feature-packages.md: a feature too large for one service becomes an umbrella). Code moves into <feature>/<subdomain>/, settings.py to common/ (table and env names kept, so no SSM rename), Python references rewritten across the app, entry point and enablement keys (base.toml, ci.toml, any config file) renamed <feature>.<subdomain>, umbrella layers contract added; computed and verified before anything moves. Tests: promote cases in tests/integration/bin/test_bin_package_generator_create.py; rename edits in tests/unit/bin/test_bin_package_toml_edit.py. Also: audit the generated shapes against the current ADRs, doc-11 and doc-15.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06: implemented on task-114.2-package-generator (from main d9574645, #1830 merged); In Progress for review.

Anchors re-verified against main: [project.entry-points.sre_bot], contracts (a) layers with "(capabilities)", (b) no-host-imports, (e) integrations-via-adapters, (f) feature-independence, (h)/(i) umbrella layers, (m) protected-plugins, root_packages, hatch wheel packages, base.toml [plugins.<area>] tables: all as planned.

Changes: bin/new_package.py (make new-package; argparse, interactive when run with no args on a terminal), bin/package_toml.py (edits as data: SetKey/Append/Insert/Replace applied to the tomlkit document and to the tomllib data; verify compares the two, a mismatch writes nothing), bin/package_templates/ (13 string.Template files + README), tomlkit 0.15.2 dev dependency, Makefile new-package.

Decisions taken during implementation (recorded in the ADRs' change lines):
- Templates live in bin/package_templates/, not bin/templates/package/: the repo .gitignore rule "package" ignores any path named package.
- The capabilities bootstrap also adds capabilities to the source_modules of contracts (b) and (e) (plugin-architecture.md Checks: capabilities never import infrastructure or server; integrations only from adapters/). Without it the first capability (TASK-25.10) ships unguarded. plugin-architecture.md change line.
- Capability inputs: --classification (generic|supporting) and at least one --consumer features.<x>[.<sub>] that exists, so the README passes the shape check's readme rules with an empty baseline. A capability ahead of its consumer (TASK-83.4) is still the baseline-entry route (plugin-architecture.md 2026-11-06).
- Areas are read from base.toml's [plugins.*] tables, so [plugins.shared] is offered once it exists.
- An umbrella takes --area (for the printed product-scope row only; no key) and gets an exhaustive layers contract with layers = [] (import-linter accepts it); subdomain, core and common join it in subdomains > core > common order.
- --settings (any kind but umbrella) writes settings.py on [<module path joined by _>] and adds the empty table to base.toml; refused when the table exists.
- Subdomain names core, common and the layout-table directory names are refused; an entry-point name bound to another module is refused (e.g. rant).
- tests/integration/server/test_server_plugins_ci_requirements_guard.py now flags a plugin only when its register_requirements returns a requirement: the generated template returns [] and would otherwise fail CI for every new plugin. plugins.md change line.

Scratch run on the real tree (pyproject.toml and base.toml backed up and restored, packages deleted, uv sync): feature+settings, capability (first: bootstrap)+settings, umbrella, subdomain+settings, core, common. lint-imports 14 kept 0 broken (new umbrella contract kept); check-package-shape OK (10 baselined); check-settings-key-ownership OK; ruff clean; mypy on the 25 generated files: Success, no issues; installed entry points match the enablement keys (check_plugin_enablement); plugin enablement boot, CI requirements guard and lifespan configuration-phase tests pass with the scratch plugins installed.

Tests: tests/unit/bin/test_bin_package_toml_edit.py (19), tests/integration/bin/test_bin_package_generator_create.py (17).
Gates (from app/): ruff check . -> All checks passed; make check-import-contracts -> 13 kept, 0 broken; make check-settings-key-ownership -> OK; make check-package-shape -> OK, 10 baselined; mypy . -> 41 errors in 14 files, pre-existing (same as TASK-114.1), none in touched files (run a second time only to group errors by file, a slip against run-once); pytest tests --ignore=tests/smoke -> 6426 passed.

2026-11-06 (second commit on PR #1832, human request): promote kind and an alignment audit.
- promote <feature> --subdomain <name> (AC #8): flat plugin feature -> umbrella in place; code into the subdomain, settings.py to common/ keeping its table and env names (no SSM rename), features.<feature> references rewritten in the app's Python and the moved package's Markdown, entry point and enablement keys renamed <feature>.<subdomain> in base.toml and every config/*.toml (ci.toml included), umbrella layers contract added; all TOML rendered and verified before anything moves. New edits: DeleteKey, rename_entry_point, rename_in_contracts (independence contract kept), rename_enablement_key.
- Audit against the ADRs, doc-11 and doc-15 (read-only subagent, verified against ADR text), applied: capability bootstrap now also covers contracts (g) and (k) and allows capabilities.**.entrypoints.slack in (j); pyproject (j) gains features.**.entrypoints.slack (platform-entrypoints.md Checks already require it); a capability's area comes from its consumers' keys, a mismatch is refused and consumers spanning areas are refused until [plugins.shared] exists (plugins.md); core/ and common/ get a README; common/'s slice reads [<umbrella>] (matches promote; configuration.md line); next steps name ci.toml switch-off and building the slice in host_configuration.py; hookspecs template names the marker. Kept: enablement true in base (TASK-112.2 convention, pinned by test_base_keeps_the_access_plugins_off_and_every_other_plugin_on; approved plan). Not emitted: the capabilities' declared order (no file records it yet).
- ADR change lines: plugin-architecture.md and plugins.md amended; feature-packages.md, configuration.md, platform-entrypoints.md added.
- Scratch run on the real tree (restored): every kind plus promote; lint-imports 15 kept 0 broken, shape and ownership OK, ruff clean, mypy no issues in 33 generated files, boot tests pass.
- Gates (from app/): ruff clean; check-import-contracts 13 kept 0 broken; check-settings-key-ownership OK; check-package-shape OK (10 baselined); mypy 41 errors in 14 files, pre-existing, none in bin/ (run once); pytest tests --ignore=tests/smoke 6437 passed.
<!-- SECTION:NOTES:END -->
