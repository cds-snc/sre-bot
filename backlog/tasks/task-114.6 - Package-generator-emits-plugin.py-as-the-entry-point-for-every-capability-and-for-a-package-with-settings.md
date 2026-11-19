---
id: TASK-114.6
title: >-
  Package generator emits plugin.py as the entry point for every capability and
  for a package with settings
status: In Progress
assignee: []
created_date: '2026-11-19T14:27:00Z'
updated_date: '2026-11-19T15:11:00Z'
labels:
  - tooling
milestone: m-3
dependencies:
  - TASK-114.4
  - TASK-114.5
references:
  - decisions/plugins.md
  - decisions/feature-packages.md
  - decisions/plugin-architecture.md
  - app/bin/new_package.py
  - app/bin/package_layout.toml
parent_task_id: TASK-114
priority: medium
ordinal: 530000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-11-19 from TASK-25.10.2 planning (Q1, approved by the human with the platform/extension framing).

WHY: contract (m) protects each entry point's module and every submodule under it. When a package's entry point is the package itself, nothing outside the package may import it. A capability's api.py is always imported by features (plugin-architecture.md:38; capability test 1 requires a feature consumer), and a package with settings.py is imported by the host's configuration phase (plugins.md 2026-11-05; server/configuration/host_configuration.py). Both cases therefore need the entry point to be the package's plugin module. Today the generator always names the package as the entry point, so TASK-146.1.1 (D4) moved oncall's hookimpls into capabilities/oncall/plugin.py by hand. TASK-25.10.2 (text_generation), TASK-25.10.3 (its settings.py) and TASK-83.4 (the people capability, doc-15 E4) hit the same gap.

FRAMING (human, 2026-11-19): capabilities and contracts/ are the platform this project maintains; features are the extension surface, written in-tree or in an adopter's own distribution. A capability is its api.py (the platform API) plus an optional plugin module for its own surfaces; the plugin module is what is registered and switched by the enablement key. Backstage keeps a plugin's extension points and service refs in a separate -node library, so consumers never depend on the plugin package itself.

SCOPE: make new-package writes plugin.py from the plugin_init template, names it as the entry point and as contract (m)'s protected module, and leaves __init__.py as a docstring only:
- for every capability;
- for any package given --settings.
A feature without --settings is unchanged (the package stays the entry point). plugins.md:39 is reworded to match: the entry point names the package's plugin module whenever code outside the plugin imports the package (a capability's api.py, or settings.py read by the configuration phase). The manifest's plugin.py entry is extended to the capability kind if it is not already listed there. Tooling and ADR text only; deploys nothing; single PR from main. Plan at pickup.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 make new-package for a capability writes plugin.py holding the register_requirements hookimpl, a docstring-only __init__.py, and names <package>.plugin as both the entry point and the contract (m) protected module; the generator tests assert both values, and one scratch-copy lint-imports run with a feature importing the capability's api.py is recorded in notes
- [x] #2 A feature or subdomain, with or without --settings, still names the package as its entry point; plugin.py stays an optional entry placed by hand when the host reads the package's settings before plugin loading (plugins.md:39)
- [x] #3 bin/package_layout.toml declares plugin_module = "plugin.py" and the capability kind requires it (the loader refuses otherwise, and refuses it in core); the drift test against feature-packages.md passes, and make check-package-shape passes on the generated output with no new baseline entry
- [x] #4 The shape check reads plugin_module from the layout and reports <path>:capability-entry-point for a capability whose entry point names the package, and <path>:hookimpl-outside-plugin when a package with plugin.py defines a hookimpl in __init__.py; no baseline entry
- [x] #5 decisions/plugins.md:39 and decisions/feature-packages.md (the plugin.py row, the generator sentence and the Checks line) state the rule, with dated Changes lines
- [x] #6 Generator, layout and shape-check tests cover the capability case and the unchanged feature cases; ruff, the bin tests, make check-import-contracts and check-package-shape pass, then full mypy and pytest, with output in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
BASE: main 6f9b7645 plus d2e81c54 (TASK-114.5, in review). 114.5 edits the same files (bin/package_layout.py, package_layout.toml, new_package.py, check_package_shape.py, test_bin_package_layout_load.py), so this task is implemented on main after 114.5 merges (OQ1: dependency TASK-114.5 added on approval). Branch at implementation: task-114.6-capability-plugin-module from main.

FINDINGS (2026-11-19)
- The generator names the package as the entry point and protected module for every plugin kind (bin/new_package.py _pyproject_edits: entry_point(..., package.module), protected_plugin(pyproject, package.module); _report prints the same target). plugin.py is a feature-kind optional entry inherited by capability (package_layout.toml [kinds.feature] optional), with no template and no option flag, so it is never generated.
- The shape check already holds plugin.py to an entry point naming it (check_package_shape.py _check_plugin_package: <path>:plugin-unnamed) and strips a trailing plugin module from targets (_package_module, PLUGIN_MODULE = "plugin" constant at :70). It does not hold a capability to a plugin-module entry point, and does not flag hookimpls left in __init__.py when plugin.py exists (those hooks are never registered: the entry point names plugin.py).
- The --settings half of this task's description does not hold (OQ2). comms and scribe both have settings.py with package entry points (features.incident.comms, features.incident.scribe), because a plugin's slice validates in plugin boot when the plugin is enabled (configuration.md:69, lifecycle.md phase 3); only a slice read in the configuration phase (host_configuration.py: incident.common, postmortem, response) needs the plugin module, which plugins.md:39 already says. So the generator cannot tell from --settings alone; the feature case stays as today.

DECISIONS PROPOSED
 D1 The role is declared in the manifest, not derived (carry rule; precedent public_api, TASK-114.5): top-level plugin_module = "plugin.py"; the loader refuses it unless the capability kind requires it and core excludes it. [kinds.capability] required gains "plugin.py"; templates "plugin.py" = "plugin_init.py.tmpl" (existing hookimpl template) and "__init__.py" = "capability_init.py.tmpl" (new: docstring only, 'import api.py only; the hookimpls live in plugin.py', as capabilities/oncall/__init__.py).
 D2 Generator: when the package's entries hold plugin_module, the entry-point target and the contract (m) protected module are '<module>.plugin'; _report prints that target. Nothing else in the TOML edits changes (entry-point name, enablement key and area rules unchanged).
 D3 Shape check reads plugin_module from the layout instead of its PLUGIN_MODULE constant and gains two violations (OQ3): '<path>:capability-entry-point' when a capability's entry point names the package rather than its plugin module, and '<path>:hookimpl-outside-plugin' when a package has plugin.py and its __init__.py defines a hookimpl. oncall passes both; no baseline entry.

ORDERED STEPS (TDD: failing tests first)
 1. tests/unit/bin/test_bin_package_layout_load.py: test_a_capability_requires_only_its_init_readme_and_api becomes ...requires_its_init_readme_api_and_plugin_module ({__init__.py, README.md, api.py, plugin.py}); plugin_module loads as 'plugin.py'; refusals: missing, not required by capability, allowed in core. Drift test unchanged in mechanism (names already include plugin.py).
 2. tests/integration/bin/test_bin_package_generator_create.py: a capability writes plugin.py with the register_requirements hookimpl and a docstring-only __init__.py (no hookimpl), entry point text_generation-style '<module>.plugin' and the same value in contract (m) protected_modules; test_a_capability_holds_its_required_entries_plus_exactly_the_options_given gains plugin.py; a feature, subdomain and a feature with --settings still name the package (unchanged case); the generated output passes check_package_shape; printed next steps name '<module>.plugin'.
 3. tests/unit/bin/test_bin_package_shape_check.py: capability entry point naming the package -> capability-entry-point; naming .plugin passes; plugin.py plus a hookimpl in __init__.py -> hookimpl-outside-plugin; a feature with a package entry point and no plugin.py is unaffected.
 4. bin/package_layout.toml (plugin_module key, capability required and templates, comment); bin/package_layout.py (field, loader check, top-level key set); bin/package_templates/capability_init.py.tmpl (new); bin/new_package.py (_plugin_target helper used by _pyproject_edits and _report; module docstring line); bin/check_package_shape.py (D3; docstring rule list).
 5. ADRs, dated 2026-11-19 Changes lines (TASK-114.6, human): plugins.md:39 'An entry point targets its package's plugin submodule when code outside the plugin imports the package: always for a capability, whose api.py features import, and for a package whose settings the host reads before plugin loading; the hookimpls then live only in that module, and import-linter contract (m) protects it.' feature-packages.md:40 plugin.py row 'the hookimpls; required in a capability, optional elsewhere (when the host reads the package's settings before plugins load); the entry point names it'; the generator sentence (:46) and the Checks line (:103) name the two new shape violations.
 6. Gates at the end, once each in sequence from app/: ruff check; make check-import-contracts check-package-shape; uv run pytest tests/unit/bin tests/integration/bin; then full mypy, then full pytest tests --ignore=tests/smoke. One scratch-copy run (outside /workspace) of make new-package capability ... plus a feature importing its api.py, then lint-imports, recorded in notes as the end-to-end check of AC #1.

AC TRACEABILITY
 #1 steps 2, 4 (generator test; scratch lint-imports run in notes). #2 (reworded per OQ2) step 2 unchanged-case tests. #3 steps 1, 3, 4. #4 step 5. #5 step 6.

TEST MATRIX: happy (capability gets plugin.py, .plugin target in both TOML places, shape passes); boundary (capability with --hookspecs/--service/--entrypoints/--adapters still gets plugin.py once; promote of a feature unchanged); failure (manifest without plugin_module, capability not requiring it, core allowing it: LayoutError; shape violations above); unchanged (feature, subdomain, feature with --settings: package target).

DOMAIN-MODEL EVOLUTION: not applicable (tooling; no entity or persisted shape).

SIZE: ~50 production LOC over 6 files (manifest, loader, template, generator, shape check, plus ADR lines in 2 records); one subsystem (app/bin); passes the gate.

ASSUMPTIONS AND HOW TO VERIFY
 - Making plugin.py required in the capability kind breaks no existing package: only capabilities/oncall exists and has plugin.py (verified); the shape check allows required and optional alike and does not test presence, so the change reaches the generator and the drift test only.
 - Shape rule capability-entry-point is satisfied by oncall (target capabilities.oncall.plugin, verified in pyproject.toml:49).
 - TASK-25.10.2's planned command needs no change; its D1 hand edits are already dropped (plan REVISIONS 2026-11-19).

BLAST RADIUS AND ROLLBACK: tooling and ADR text only; deploys nothing; one git revert restores the old generator. No consumer until 25.10.2, which depends on this.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-19 implemented on task-114.6-capability-plugin-module from main 53fa634c (TASK-114.5 #1874 merged), ACs #1-#6 checked, In Progress.

Changes (6 production files plus 2 ADRs):
- bin/package_layout.toml: top-level plugin_module = "plugin.py"; [kinds.capability] excludes the inherited optional plugin.py and requires it; templates __init__.py = capability_init.py.tmpl, plugin.py = plugin_init.py.tmpl.
- bin/package_layout.py: Layout.plugin_module; required top-level key; _plugin_module refuses a non-module value, a capability kind that does not require it, and a core kind that declares it.
- bin/package_templates/capability_init.py.tmpl (new): docstring only, points at $module.api and plugin.py.
- bin/new_package.py: _plugin_target() returns <module>.plugin when the package's entries hold plugin_module; used for the entry point, contract (m) and the printed Entry point line. Features and subdomains, with or without --settings, keep the package target.
- bin/check_package_shape.py: PLUGIN_MODULE read from the layout; new <path>:capability-entry-point (a capability-kind package named by its own module) and <__init__.py>:hookimpl-outside-plugin (plugin.py named by an entry point and __init__.py defines a hookimpl; an unnamed plugin.py keeps reporting plugin-unnamed only). oncall passes; no baseline entry.
- decisions/plugins.md (Decision :39, Checks, Changes 2026-11-19) and decisions/feature-packages.md (plugin.py row, generator paragraph, Checks line, Changes 2026-11-19). The enablement-key rule for capabilities is not written here: it rides with TASK-25.10.2 AC #9.

Tests: test_bin_package_layout_load.py (capability requires plugin.py and its templates; four new refusals), test_bin_package_shape_check.py (capability fixtures use .plugin; capability-entry-point; hookimpl-outside-plugin; feature with hookimpls in __init__ and no plugin.py unaffected), test_bin_package_generator_create.py (capability: plugin.py, docstring-only __init__.py, .plugin in the entry point and protected_modules, registers from plugin.py; every option combination holds plugin.py; feature with --settings keeps features.shop; printed Entry point line names the target written).

Scratch-copy end-to-end (AC #1), outside /workspace (rsync of app/ to the session scratchpad, .venv excluded, PYTHONPATH at the copy): python -m bin.new_package capability demo_cap --classification generic --consumer features.incident.comms wrote __init__.py (docstring only), README.md, api.py, plugin.py; pyproject entry point demo_cap = "capabilities.demo_cap.plugin" and the same in contract (m); [plugins.incident_response] demo_cap = true. Added 'from capabilities.demo_cap import api' to features/incident/comms/service/__init__.py. lint-imports: Contracts: 14 kept, 0 broken; check_package_shape OK (3 baselined). Negative control: entry point and protected module set back to capabilities.demo_cap -> (m) BROKEN, 'features.incident.comms.service -> capabilities.demo_cap.api'; shape check FAIL capabilities/demo_cap/plugin.py:plugin-unnamed and capabilities/demo_cap:capability-entry-point.

Gates (from app/): uv run ruff check . -> All checks passed!; uv run pytest tests/unit/bin tests/integration/bin -> 502 passed; make check-import-contracts -> Contracts: 14 kept, 0 broken; make check-settings-key-ownership -> OK; make check-package-shape -> OK (3 baselined); make check-test-seams -> OK (47 strict-zone, 12 legacy pin baselined); uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 40 errors in 13 files (pre-existing: modules 21, infrastructure 15, features 2, integrations 2; none in changed files; same count as after TASK-114.5); uv run pytest tests --ignore=tests/smoke -> 7882 passed.

Merge deploys nothing (tooling and ADR text). Next: PR (base main); Done is the human's. Unblocks 15a TASK-25.10.2.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-19T14:40:00Z

---

2026-11-19 planning: proposed AC changes (awaiting approval). AC #1: replace 'lint-imports passes when a feature imports the new capability's api.py' with 'the generator tests assert both values; one scratch-copy lint-imports run with a feature importing the capability's api.py is recorded in notes'. AC #2: replace with 'a feature or subdomain, with or without --settings, still names the package as its entry point; plugin.py stays an optional entry placed by hand when the host reads the package's settings before plugin loading (plugins.md:39)'. Reason: comms and scribe have settings.py with package entry points; a plugin's slice validates in plugin boot (configuration.md:69). New AC (D3): 'the shape check reports <path>:capability-entry-point for a capability whose entry point names the package, and <path>:hookimpl-outside-plugin when a package with plugin.py defines a hookimpl in __init__.py; no baseline entry'. Description: the --settings half is withdrawn. Dependency TASK-114.5 to add (same files).

---

created: 2026-11-19T14:43:00Z

---

2026-11-19 (human): plan approved; OQ1 (depends on TASK-114.5, implement on main after it merges), OQ2 (the --settings half is withdrawn; features and subdomains unchanged) and OQ3 (capability-entry-point and hookimpl-outside-plugin shape rules) approved as recommended; AC changes applied (#1 reworded, #2 replaced, #3 declares plugin_module, #4 new shape rules, #5 #6 as before). The description's --settings scope is superseded by AC #2.

---
<!-- COMMENTS:END -->
