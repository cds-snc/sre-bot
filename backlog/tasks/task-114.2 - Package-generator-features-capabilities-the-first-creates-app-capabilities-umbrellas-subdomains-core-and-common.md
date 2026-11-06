---
id: TASK-114.2
title: >-
  Package generator: features, capabilities (the first creates
  app/capabilities/), umbrellas, subdomains, core/ and common/
status: To Do
assignee: []
created_date: '2026-11-06T02:56:00Z'
updated_date: '2026-11-06T02:57:00Z'
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
- [ ] #1 The generator creates a feature, a capability, an umbrella, an umbrella subdomain, or an umbrella's core/ or common/ in the layout-table shape; the generated package passes check-package-shape with an empty baseline, ruff, and registers on a plugin manager unchanged
- [ ] #2 A plugin (feature, capability or subdomain) gets its entry-point line (dotted for a subdomain), its module in the protected-plugins contract, and its enablement key in the [plugins.<area>] table the user picks from product-scope.md's areas; core/, common/ and the umbrella get none
- [ ] #3 A new feature is added to the feature-independence contract; a subdomain, core/ or common/ is added to its umbrella's exhaustive layers contract; a new umbrella gets its own layers contract
- [ ] #4 The first capability creates app/capabilities/: capabilities joins root_packages, the wheel packages and the six-layer contract; later capabilities change none of those
- [ ] #5 A plugin's __init__.py template holds a register_requirements hookimpl returning an empty list; a capability gets api.py, hookspecs.py and a README with the Classification and Feature consumers sections
- [ ] #6 Each edit of pyproject.toml and base.toml keeps its comments and is verified with tomllib before it is written; a failed check writes nothing
- [ ] #7 The generator prints the product-scope.md table row to add and is run by make new-package
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
<!-- SECTION:PLAN:END -->
