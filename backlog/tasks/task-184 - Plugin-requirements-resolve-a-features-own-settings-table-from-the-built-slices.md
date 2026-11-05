---
id: TASK-184
title: >-
  Plugin requirements resolve a feature's own settings table from the built
  slices
status: In Progress
assignee: []
created_date: '2026-11-05T01:15:00Z'
updated_date: '2026-11-05T15:05:00Z'
labels:
  - plugins
  - configuration
dependencies: []
references:
  - decisions/plugins.md
  - decisions/configuration.md
  - app/server/plugins/requirements.py
priority: medium
ordinal: 484000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A plugin's register_requirements can name only workplace tenants and the openai, opsgenie and slack tables today: server/plugins/requirements.py resolves a setting through a host-held map of vendor slices (SETTINGS_SLICES), so Requirement("incident_core.folder_id") is always unmet, and adding a feature's table to that map would make the host import feature code. A requirement on a table no vendor slice owns resolves instead against the built configuration slice that reads that table (contracts/configuration.built_slices(), slice_table), so a feature requires its own keys without the host knowing the feature. Prerequisite of TASK-145.6.2 AC #5 (scribe requires [incident_core] folder_id and report_template_id) and of TASK-145.7 (response). Single PR from main; no settings, terraform or environment change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A requirement on a table read by a built configuration slice is met when the named attribute is set and unmet when it is empty, None or an empty secret, with no feature module imported by server/plugins
- [x] #2 A requirement on a table no slice reads, or naming a missing attribute, stays unmet and is reported as plugin_boot_failed naming the plugin and the setting, never a value
- [x] #3 Workplace tenant requirements and the openai, opsgenie and slack tables resolve exactly as before
- [x] #4 decisions/plugins.md states how a requirement on a feature's own table resolves
- [x] #5 A feature table whose slice is not built when requirements resolve is unmet (never built on demand), and a slice built before plugin boot resolves for any plugin, whichever built it
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (TASK-184) - single PR from main, ~15 production LOC in 1 file + 2 doc lines + tests. No settings, terraform or env change. APPROVED 2026-11-05 (human), OQ1-OQ3 as recommended (see Open questions). Re-grounded at main f45d4ec1 (#1823 merged): host_configuration.py:243-247 and lifespan.py:248-252 unchanged; Requirement( declared only by oncall_sync, rant, user_rotations and scribe.

## Grounding (path:line, read 2026-11-05)
- app/server/plugins/requirements.py:31-41 WORKPLACE_SETTINGS / SETTINGS_SLICES (openai, opsgenie, slack getters); :60-71 is_requirement_met returns False when SETTINGS_SLICES has no entry for the table (:67-68).
- app/server/plugins/requirements.py:84-99 unmet_requirements wraps each plugin's resolution in attribute_built_slices(plugin); resolve_requirements :102-120 logs one CRITICAL plugin_boot_failed per failure (plugin, phase, error_type, setting; never a value) then raises PluginRequirementsUnmetError.
- app/contracts/configuration.py:73-84 ConfigurationSlice._table is set from the single toml_table_header; :83 slice_table(built); :88-90 built_slices() = every slice built since the files were installed (_built is keyed by class, so one instance per class), sorted by (table, class name).
- app/server/configuration/host_configuration.py:206-247 the app factory configuration phase builds, eagerly and before the lifespan: slack, openai, opsgenie, google_workspace AND get_incident_core_settings / response / postmortem / cloud_operations_spending / talent (:243-247).
- app/server/lifespan.py:248-252 order: reset_plugin_built_slices, load_plugins (imports entry points, builds nothing), resolve_plugin_requirements(pm, ..., read_configured_systems()) (before every registration hook and before translation/command registration).
- Plugins declaring requirements today (only these 4): packages/oncall_sync/__init__.py:36 (slack.tenant, slack.user_token, opsgenie.tenant); packages/rant/__init__.py:13 and packages/user_rotations/__init__.py:12 (slack.tenant); features/incident/scribe/__init__.py:22 (openai.tenant, slack.tenant, google_workspace.tenant). features/incident/common/settings.py:30,49-50 shows incident_core.folder_id / report_template_id are env_only str default "" (unset = empty string = unmet).
- Existing tests: app/tests/unit/server/plugins/test_server_plugins_requirements_resolve.py (193 lines; `slices` fixture monkeypatches host.SETTINGS_SLICES) and app/tests/integration/server/test_server_plugins_configuration_requirements.py (CI configuration check; builds only vendor getters).

## Decisions (with justification)
(a) Keep SETTINGS_SLICES for the vendor tables; do NOT route them through built_slices. Reasons: (1) AC #3 and the 4 declaring plugins above resolve exactly as before, with precedence unchanged (workplace map, then vendor map, then built slices); (2) a vendor getter builds lazily, so a vendor requirement resolves even when nothing built that slice yet (the integration check at test_server_plugins_configuration_requirements.py:40-46 calls the vendor getters itself; built_slices would be empty there); (3) the vendor map imports integrations/, which is the host's own layer (server -> integrations is allowed), whereas features are not. Moving vendors to built_slices would make vendor resolution depend on build order for no gain. The map stays the "host may build this on demand" list; built_slices is the "feature already built it" fallback.
(b) Fallback is read-only: find the first built slice whose slice_table == table; no match, no path, or a missing attribute = unmet. Never build on demand (that needs a feature import, the inversion this task removes). Not-built-at-resolution is fail-closed: the requirement is unmet and reported as the normal plugin_boot_failed (plugin + setting). Ordering check: the feature slices a legacy/rebuilt subdomain needs are built in host_configuration.py:243-247 during the configuration phase, which runs in the app factory before the lifespan (lifespan.py:248-252 resolves after), so incident_core exists before plugin boot. Consequence for later tasks: a feature slice that is NOT in that eager list (and is built only by its own registration hook, which runs after requirements) would be unmet; such a feature must be added to the eager list or declare no requirement on its table. Documented in plugins.md (AC #4). This is deliberately independent of attribute_built_slices: that helper only attributes slices FIRST built inside a plugin's hook, so incident_core (already built) would be invisible to it; the lookup reads built_slices() directly, and attribution is untouched.
(c) Two slices on one table cannot exist in production: bin/check_settings_key_ownership.py (make check-settings-key-ownership) fails when a configuration-file table is named by two slices. Residual: tests may define throwaway slices; built_slices() is sorted by (table, class name) so the first match is deterministic. No extra code for it; one test pins the determinism-free case (single match) and the plan notes the check as the guarantee.

## Steps (ordered; TDD: tests first)
1. Tests first (red): extend app/tests/unit/server/plugins/test_server_plugins_requirements_resolve.py (it already owns is_requirement_met / unmet_requirements / resolve_requirements; a sibling file is not needed). Add a `built` fixture that monkeypatches host.built_slices to return stub instances of classes carrying a `_table` ClassVar (slice_table reads type(x)._table), plus one test with a REAL ConfigurationSlice subclass (toml_table_header=("feature_x",)) built after install_configuration_files(stub files, paths=()) and torn down with uninstall_configuration_files so _built is cleared.
2. app/server/plugins/requirements.py: import built_slices, slice_table from contracts.configuration (contracts is already imported by this module; no feature import). Add private `_built_slice(table) -> object | None` (next(...) over built_slices()). In is_requirement_met: `read = SETTINGS_SLICES.get(table)`; `value = read() if read is not None else _built_slice(table)`; return False if value is None or no path; rest unchanged. Update the module docstring (a table no vendor slice owns resolves against the already-built slice that reads it) and the SETTINGS_SLICES comment. ~15 LOC.
3. decisions/plugins.md: extend the register_requirements paragraph (line 57) with one sentence: a requirement on a table no vendor slice owns resolves against the built configuration slice that reads that table, found by its toml_table_header, so a feature requires its own keys and the host imports no feature; the slice must be built before plugin boot (feature slices are built in the configuration phase, host_configuration.py), a table no slice reads or an unbuilt slice is unmet; table ownership is unique by make check-settings-key-ownership. Add a dated decision-log line (2026-11-05, TASK-184).
4. Green the targeted tests; then ruff; then the repo checks and full gates (see implementer brief).

## AC -> step -> test traceability
- AC1 (built slice met / unmet on empty, None, empty secret; no feature import) -> steps 1,2 -> test_a_built_feature_slice_requirement_is_met_when_set; ..._unmet_when_empty_none_or_empty_secret (parametrized "", None, SecretStr("")); test_a_real_configuration_slice_resolves_by_its_table; no-feature-import is shown by the import-linter contract run (make check-import-contracts) and the test using only a throwaway slice class.
- AC2 (no slice reads the table / missing attribute / bare table = unmet, reported as plugin_boot_failed with plugin+setting, no value) -> steps 1,2 -> test_a_table_no_slice_reads_is_unmet; test_a_missing_attribute_on_a_built_slice_is_unmet; test_a_bare_table_is_unmet; test_an_unmet_feature_requirement_is_logged_once_without_its_value (resolve_requirements + capture_logs, asserts plugin, setting, phase, error_type, and that the configured value text appears nowhere in the event).
- AC3 (workplace + openai/opsgenie/slack unchanged) -> step 2 -> the existing tests (test_workplace_tenants_resolve_through_the_configured_systems_read, test_other_settings_resolve_through_their_slice, test_an_empty_secret_counts_as_unset, test_plugin_requirements_* on the 4 real plugin modules) must pass unmodified, plus test_a_vendor_table_resolves_through_its_getter_even_when_a_built_slice_has_the_same_table (precedence: the vendor map wins).
- AC4 (plugins.md states it) -> step 3 -> reviewed in the PR diff (no test; docs).
- AC5 (approved as OQ3: unbuilt feature slice is unmet, not built on demand, independent of which plugin built it) -> steps 1,2 -> test_a_feature_slice_not_built_at_resolution_is_unmet (built_slices stub empty); test_a_slice_built_before_the_plugin_boot_is_found_for_any_plugin (slice present in built_slices but attributed to no plugin; two plugins both resolve it).
- Every step maps to an AC (step 4 is verification).

## Test matrix (file: app/tests/unit/server/plugins/test_server_plugins_requirements_resolve.py)
Happy: built slice attr set -> met; nested path (a.b) -> met; real ConfigurationSlice subclass -> met.
Boundary: "", None, SecretStr("") -> unmet; SecretStr("x") -> met; bare "table" without path -> unmet; vendor-map precedence over a same-table built slice; two plugins sharing one built slice both met.
Failure: no slice reads table -> unmet; missing attribute -> unmet; slice not built (empty built_slices) -> unmet; resolve_requirements on a mixed set logs one CRITICAL plugin_boot_failed per unmet feature setting, names plugin+setting, no value, then raises one aggregate error.
Authorization/idempotency: n/a (read-only, no state; repeated calls return the same result).
Integration: no change to test_server_plugins_configuration_requirements.py in this PR (no plugin declares a feature table yet). HANDOFF NOTE for TASK-145.6.2: that CI check builds only vendor getters (:40-46), so once scribe declares incident_core.folder_id it must also build the feature slice (call get_incident_core_settings, or run the configuration phase) and supply placeholders for the env_only codespaces names; otherwise the check reports it unmet.

## Assumptions and doubts (verify)
1. All feature slices a requirement may target are built in the configuration phase before plugin boot - verify by reading host_configuration.py:243-247 vs lifespan.py:248-252 (done) and, at implementation, a test or rg showing resolve runs after build_host_configuration in create_app.
2. _built holds one instance per slice class and slice_table is unique per table in production - verify: make check-settings-key-ownership.
3. server/ may import contracts.configuration - it already does (boot.py:16); verify with make check-import-contracts.
4. google_workspace.* non-tenant settings (e.g. google_workspace.x) previously unmet will now resolve via the built slice; no plugin declares one (only the 4 declarations above) - verify with rg "Requirement(" before merge.
5. Attribute path is walked with getattr like today; a requirement can name any public attribute of a built slice, including non-secret ones - acceptable, unchanged semantic.

## Blast radius and rollback
- Only is_requirement_met's fallback branch changes: it is reached only for a table that is neither in WORKPLACE_SETTINGS nor SETTINGS_SLICES. Today's declared requirements (oncall_sync, rant, user_rotations, scribe: slack.tenant, google_workspace.tenant, slack.user_token, opsgenie.tenant, openai.tenant) all take the unchanged paths, so merging cannot change boot for any enabled plugin. Merging to main deploys; nothing declares a feature table until TASK-145.6.2, so the failure mode "boot fails closed if resolution is wrong" cannot trigger from this PR alone; it becomes live when 145.6.2 merges (an unset INCIDENT_CORE__FOLDER_ID / REPORT_TEMPLATE_ID in production SSM would then abort boot for scribe by design - 145.6.2 owns checking terraform/ssm.tf and the deploy-checks pre step).
- Rollback: one git revert restores the previous behavior (pure additive branch, no data, config, terraform or env change). No ordering constraint for this PR; 145.6.2 must merge after it.

## Domain-model gate
Not applicable: no entity, record, schema, persisted shape or cardinality changes; this is a resolution rule in host code over existing settings slices (domain-model-evolution applies to entity changes only).

## Size gate
~15 production LOC in 1 file (requirements.py) + 2 doc lines in decisions/plugins.md + ~110 test LOC in 1 existing test file; 1 subsystem (server/plugins). Under every threshold; no decomposition, mechanical/behavior mix none.

## Implementer brief
- Read this plan, decisions/plugins.md (register_requirements paragraph + Decision log), app/server/plugins/requirements.py, app/contracts/configuration.py:59-90.
- TDD: write the failing tests first in the named file; follow testing-standards (docstrings describe behavior, stub strategy, assertion rationale only; no task ids or step numbers).
- During TDD run ruff and the targeted test file ONLY: cd app && uv run ruff check . ; cd app && uv run pytest tests/unit/server/plugins/test_server_plugins_requirements_resolve.py
- At the end, after all edits: make check-import-contracts and make check-settings-key-ownership (from app/ context as the Makefile defines), then full mypy (cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)') and, after it finishes, full pytest (cd app && uv run pytest tests --ignore=tests/smoke), once each, sequentially, never in parallel; rerun one only on a real error. Report commands and actual output. Do not run smoke tests. No git commands. Check each AC (backlog task edit 184 --check-ac N) only as its test passes; stop at In Progress.

## Open questions (decided 2026-11-05, human: approved as recommended)
- OQ1 The CI configuration check (tests/integration/server/test_server_plugins_configuration_requirements.py) is not changed here: no plugin declares a feature table in this PR. TASK-145.6.2 step 7 extends it when scribe declares incident_core.folder_id and report_template_id (build the incident_core slice, placeholders for env_only names).
- OQ2 Accepted: a non-tenant google_workspace.* requirement now resolves through the built google_workspace slice (built in the configuration phase). None is declared today; google_workspace.tenant still resolves through WORKPLACE_SETTINGS first. Same rule as any table: the slice that reads it answers.
- OQ3 Accepted (AC #5): a feature slice not built in the configuration phase stays unmet, fail closed (TASK-172 boot rule); never built on demand, which would need the host to import the feature.

## Delivery
Implemented as its own single PR from an up-to-date main (#1823 merged 2026-11-05). This approval rides in the next implementation PR in the queue (TASK-145.6.1, Stack K layer 12a); TASK-184 must merge before TASK-145.6.2 (layer 12b) is implemented, since 12b step 7 declares the incident_core requirements.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-05 (human): plan approved, OQ1-OQ3 as recommended. OQ1: the CI configuration check changes in TASK-145.6.2 step 7, not here. OQ2: a non-tenant google_workspace.* requirement resolves through the built slice (none declared today). OQ3: a feature slice not built in the configuration phase stays unmet (fail closed). Single PR from an up-to-date main (#1823 merged); merges before TASK-145.6.2 is implemented. The approval edits ride in the TASK-145.6.1 (layer 12a) PR.

2026-11-05 implemented (TDD) on task-184-feature-table-requirements above the approval commit. server/plugins/requirements.py: after the workplace map and the vendor map (unchanged precedence; a bare table still returns before any slice is read), a table resolves through contracts.configuration.built_slices() by slice_table; never built on demand. Tests: 12 new cases in tests/unit/server/plugins/test_server_plugins_requirements_resolve.py (stand-in built slices; one real throwaway ConfigurationSlice over its own installed base file, unmet before it is built and met after; vendor precedence; two plugins share one built slice; plugin_boot_failed names plugin and setting, no value in the events or the error). decisions/plugins.md requirements paragraph states the rule (AC #4). tests/integration/server/test_server_plugins_configuration_requirements.py untouched (OQ1: TASK-145.6.2 step 7). Gates: ruff clean; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK; mypy 41 errors in 14 files, all pre-existing and none in touched files; pytest tests --ignore=tests/smoke 6162 passed. Done is the human's.
<!-- SECTION:NOTES:END -->
