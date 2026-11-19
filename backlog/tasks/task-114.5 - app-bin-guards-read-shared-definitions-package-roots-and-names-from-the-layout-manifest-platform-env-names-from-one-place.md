---
id: TASK-114.5
title: >-
  app/bin guards read shared definitions: package roots and names from the
  layout manifest, platform env names from one place
status: In Progress
assignee: []
created_date: '2026-11-09T15:41:00Z'
updated_date: '2026-11-19T13:37:00Z'
labels:
  - tooling
milestone: m-3
dependencies:
  - TASK-114.3
references:
  - decisions/feature-packages.md
  - decisions/testing.md
  - decisions/configuration.md
parent_task_id: TASK-114
priority: low
ordinal: 497000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of the TASK-114.3 re-plan (approved 2026-11-09). Remove the remaining duplicated rule data in app/bin (survey 2026-11-09). From the layout manifest (TASK-114.3): package_toml.py's CAPABILITIES/CORE/COMMON names (:30-32), check_test_seams.py's features/capabilities roots (STRICT_ZONES :63, GUARDED_ROOTS :68), check_fake_coverage.py's api.py and adapters names (:47-48). Env names (human, 2026-11-09: dedup kept in current tasks): audit_env_names.py RUNTIME (:47-60) repeats check_settings_key_ownership.py PLATFORM_NAMES (:80); RUNTIME derives from it; whether RUNTIME_PREFIXES and SDK_NAMESPACE (:83) can share one definition is settled at plan with a classification test (merging must not widen what the audit treats as runtime). Off the incident critical path; side row. Tooling only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 package_toml.py, check_test_seams.py and check_fake_coverage.py take their package roots and layout names from the manifest loader; their existing tests pass unchanged in assertions
- [x] #2 audit_env_names.py's runtime names derive from check_settings_key_ownership.PLATFORM_NAMES (no repeated literal); audit classification tests pass unchanged; the prefix question is decided in the plan
- [x] #3 rg finds no second literal definition of the features/capabilities roots, the layout file names or the core/common kind names under app/bin outside the manifest and its loader
- [x] #4 ruff, targeted bin tests, then mypy and pytest tests --ignore=tests/smoke once each, make check-test-seams, check-fake-coverage, check-settings-key-ownership and check-package-shape pass, with output in notes
- [x] #5 RUNTIME_PREFIXES stays separate from SDK_NAMESPACE (merging would widen the audit: AWS_BUCKET, UVICORN__X); a classification test pins both predicates so a merge is a deliberate change
- [x] #6 check_package_shape.py and new_package.py take the core/common names from the loader constants, not their own literals
- [x] #7 the manifest declares public_api = "api.py" as a top-level role; the loader refuses a manifest whose capability or core kind does not require it; check_fake_coverage reads it
- [x] #8 feature-packages.md has a Changes line for the manifest's entry roles; migration.md's Done line drops LEGACY_ROOT from the test-seam guard; configuration.md Checks states the env audit's runtime set is narrower than the SDK and runtime namespace
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Scope and verdict
Tooling only (app/bin + app/tests/unit/bin) plus three ADR lines that ride in the same PR. Size gate passes: ~55 net production LOC (about 30 removed literals/constants, about 30 added: loader accessors, the public_api key and its check, LEGACY_ROOT), 8 production files (package_layout.toml, package_layout.py, package_toml.py, check_package_shape.py, new_package.py, check_test_seams.py, check_fake_coverage.py, audit_env_names.py), 1 subsystem (bin tooling), no behavior change to any guard's verdicts. ADR edits: feature-packages.md, migration.md, configuration.md (one line each). Tests: 3 existing files extended. No decomposition.
Branch at implementation: task-114.5-bin-guards-shared-definitions from main.

## Re-verified call sites (line numbers from main 6f9b7645; the 2026-11-09 numbers had drifted)
Layout names (manifest app/bin/package_layout.toml; loader app/bin/package_layout.py, layout() is @cache, no import side effects; Roots has features/capabilities only):
- bin/package_toml.py:30-32 CAPABILITIES/CORE/COMMON; uses :220 (core/common skip in sibling_lines), :234-236, :249-257 (capabilities root edits). package_toml imports nothing from bin yet.
- bin/check_test_seams.py:63 STRICT_ZONES (features/capabilities literals), :68 GUARDED_ROOTS (features, capabilities, modules); uses :155, :274, :280, :315. "unit"/"integration" are test-tree names, not layout: stay.
- bin/check_fake_coverage.py:47-48 CAPABILITY_API_MODULE_NAME / CAPABILITY_ADAPTERS_DIR (uses :101-102); :101 and :115 repeat the "capabilities" root literal.
- Found beyond the task text, same defect: bin/check_package_shape.py:68-69 CORE/COMMON (uses :152,:167,:181,:183); bin/new_package.py:87 COMMON (use :248). check_package_shape.py:63-64 already reads roots from layout() (the pattern to follow).
Env names:
- bin/audit_env_names.py:47-60 RUNTIME (3 platform names + 8 AWS_* credential/config names), :62 RUNTIME_PREFIXES, used only by _is_runtime :132-133 (callers :144, :153).
- bin/check_settings_key_ownership.py:80 PLATFORM_NAMES (ENVIRONMENT, GIT_SHA, FORWARDED_ALLOW_IPS; the closed list of configuration.md:43), :83 SDK_NAMESPACE regex, used :653 (sdk-namespace rule) and :656 (PLATFORM_NAMES, env-naming rule).
- Import mechanics: bin is a package (bin/__init__.py); scripts import each other as "from bin.x import y" and run as "python -m bin.x"; pyproject pythonpath = ["."]; no sys.path edits, INP001 not an issue. audit_env_names already does "from bin import check_settings_key_ownership as checker"; that module has only constants, re.compile and defs at import, main guarded at :702. Importing PLATFORM_NAMES from it is safe. bin/package_layout.py imports nothing from bin, so package_toml importing it makes no cycle.

## Decisions (assessed at program scope 2026-11-19; approved by the human the same day)
OQ1 - entry roles are declared in the manifest, not derived. feature-packages.md names api.py the public surface of a capability (:32) and of an umbrella's core/ (:56, :84, :99); the manifest is the layout table's machine copy (:142) but had no way to mark an entry's role. Precedent: TASK-114.3 declared grows_into_package as a top-level role list rather than deriving it. Practice: Tach declares a module's public surface in tach.toml ([[interfaces]] expose), Nx makes each project's index.ts its declared public API; neither infers it. Deriving api.py as "the entry capability requires beyond feature" would break the day a feature needs api.py or a capability gains a second required entry, and misses core/. So: a top-level manifest key public_api = "api.py"; the loader refuses the manifest unless kinds capability and core both require that entry. adapters/ is already declared (options.adapters.entry). feature-packages.md gets a Changes line.
OQ2 - core/common names are loader constants. They are fixed directory names in the ADR's umbrella layout (feature-packages.md:56) and change only with that record (the "constant only if it must never change" rule, 2026-11-18). CORE_KIND = "core" and COMMON_KIND = "common" live in package_layout.py only; the loader refuses a manifest missing either kind; every tool imports them. AC #3 allows literals in the loader, so no exception.
OQ3 - the legacy root is a named constant tied to the migration's end. "modules" is not a layout entry (AC #3 does not cover it) and appears as a root only at check_test_seams.py:68; testing.md:28/:44 guard it until migration.md:63 "Done means". It becomes LEGACY_ROOT = "modules" in check_test_seams.py with a comment citing migration.md; migration.md's Done line gains "and LEGACY_ROOT is dropped from the test-seam guard" so the task deleting app/modules/ deletes it too.
Prefix - RUNTIME_PREFIXES and SDK_NAMESPACE stay separate (evidence below). configuration.md:97/:138 define the broad SDK and runtime namespace a slice may never declare; no record said the env audit's runtime set is deliberately narrower. configuration.md Checks gains one sentence: the env audit treats as runtime only names an SDK or the runtime reads itself (AWS_ENDPOINT_URL*, UVICORN_*, OTEL_*, the platform names and the AWS credential-chain names), narrower than the namespace the ownership check forbids; a classification test keeps the two apart.
Scope check across doc-11, doc-15, doc-16: no other task changes. 15a (TASK-25.10.2) creates the first capability, the first package the fake-coverage api.py scan reads; TASK-164 (To Do) moves env-checks into CI and lists audit_env_names.py but does not change classification; TASK-111.15.2 is Done; TASK-83.4's generator option does not touch roles.

## Loader additions (bin/package_layout.py + package_layout.toml)
- Manifest: top-level public_api = "api.py", with a comment (the public surface of a capability and of an umbrella's core/, feature-packages.md).
- Loader: public_api joins REQUIRED_TOP_LEVEL_KEYS; Layout.public_api (str); LayoutError naming the key if it is not a string or not required by both the capability and core kinds.
- Layout.adapters_dir: options["adapters"].entry without the trailing "/"; LayoutError if the option is absent.
- CORE_KIND = "core", COMMON_KIND = "common": the loader requires both kinds (LayoutError naming the key); the directory name equals the kind name.
Manifest is the declarative source for bin tooling: layout names, roles and roots are manifest data, not constants and not settings. A plain constant stays only for a name that is not layout (LEGACY_ROOT, unit, integration, in_memory.py, infrastructure). Nothing here is policy/tuning, so no typed setting.

## Prefix decision (evidence)
Do not merge RUNTIME_PREFIXES with SDK_NAMESPACE. They answer different questions and are not subset-related:
- SDK_NAMESPACE r"(AWS|UVICORN|OTEL)_[^_]" matches every AWS_x. Audit RUNTIME_PREFIXES allows only AWS_ENDPOINT_URL*, UVICORN_*, OTEL_* plus the 8 listed AWS names. AWS_BUCKET matches SDK_NAMESPACE but is today a "check" in the audit; merging would turn it into "none (read by the platform)": widens runtime. This is the widening the task forbids.
- Opposite direction: UVICORN__X / OTEL__X start with the audit prefix but not the regex (double underscore), so the audit treats them as runtime and the ownership check does not. A shared regex would change that too.
Decision: RUNTIME_PREFIXES stays in audit_env_names.py, with a comment citing the configuration.md Checks sentence. RUNTIME = PLATFORM_NAMES | the AWS names (the AWS literals stay: they are the SDK credential-chain names the audit exempts, a different set from the platform names). Classification test pins both predicates side by side, so a future merge is a visible, deliberate test change.

## Ordered steps (TDD: failing test first, each step keeps main green)
1. package_layout.toml + package_layout.py: add public_api and its check, Layout.public_api, Layout.adapters_dir, CORE_KIND/COMMON_KIND + required-kind validation. Tests first in tests/unit/bin/test_bin_package_layout_load.py. The drift test against the feature-packages.md table stays unchanged (public_api is a role, not a new entry). [AC1, AC3, AC7]
2. package_toml.py: drop CAPABILITIES/CORE/COMMON literals; CAPABILITIES = layout().roots.capabilities, CORE/COMMON from the loader constants. check_package_shape.py:68-69 and new_package.py:87 likewise. Existing test_bin_package_toml_edit.py / test_bin_package_shape_check.py / generator tests pass unchanged. [AC1, AC3, AC6]
3. check_test_seams.py: STRICT_ZONES and GUARDED_ROOTS take features/capabilities from layout().roots; GUARDED_ROOTS adds LEGACY_ROOT = "modules" (comment: dropped when migration.md Done is reached). Existing test_bin_test_seams_check.py unchanged. [AC1, AC3]
4. check_fake_coverage.py: api.py from layout().public_api, adapters from layout().adapters_dir; the two "capabilities" literals (:101, :115) from layout().roots.capabilities; delete CAPABILITY_API_MODULE_NAME and CAPABILITY_ADAPTERS_DIR (replaced; rg-verified across app/ that no other reader exists before deleting). test_bin_fake_coverage_check.py unchanged. [AC1, AC3]
5. audit_env_names.py: RUNTIME = checker.PLATFORM_NAMES | frozenset of the 8 AWS names; RUNTIME_PREFIXES stays with the why-comment. Tests first in test_bin_audit_env_names_classify.py. [AC2, AC5]
6. ADR lines (same PR): feature-packages.md Changes "2026-11-19: the manifest names entry roles: public_api (api.py, the public surface of a capability and of core/), read by the fake-coverage check; core and common kind names are loader constants (TASK-114.5)"; migration.md "Done means" gains "and LEGACY_ROOT is dropped from the test-seam guard"; configuration.md Checks gains the env-audit runtime sentence, with a Changes line. [AC8]
7. Delete-dead-code sweep on the touched files (ruff F401/F841 plus rg of each removed constant); delete only on evidence of no reader. bin/env-checks RETIRED map and RETIRED semantics untouched; MAXMIND_KEY not touched. Docstring touch-ups only where they quote a removed constant.

## Test matrix (names per testing-standards; docstrings state behavior only)
- test_bin_package_layout_load.py (extend): happy: public_api == "api.py", adapters_dir == "adapters", CORE_KIND/COMMON_KIND kinds exist in the real manifest; failure: tmp manifests refused naming the key: public_api missing, public_api not required by capability, public_api not required by core, missing core or common kind, missing adapters option.
- test_bin_audit_env_names_classify.py (extend): (a) RUNTIME == PLATFORM_NAMES | the AWS set (derivation, no literal repeat); (b) parametrized classification, name -> audit action: ENVIRONMENT/GIT_SHA/FORWARDED_ALLOW_IPS none; AWS_REGION, AWS_ENDPOINT_URL_S3, UVICORN_PORT, OTEL_SERVICE_NAME none; AWS_BUCKET check even though SDK_NAMESPACE matches it (boundary); UVICORN__X pinned as today's behavior (none), with a case showing SDK_NAMESPACE does not match it. Existing classify tests unchanged.
- Unchanged-assertion regression: test_bin_package_toml_edit, test_bin_package_shape_check, test_bin_test_seams_check, test_bin_fake_coverage_check, test_bin_settings_key_ownership_check, test_bin_audit_env_names_*.
- AC3 evidence: rg -n '"features"|"capabilities"|"api.py"|"adapters"|"core"|"common"' app/bin/*.py lists only package_layout.py (non-layout literals such as LEGACY_ROOT, unit, integration, infrastructure are outside AC3's scope).

## Assumptions and doubts (verify)
- check_test_seams STRICT_ZONES evaluated at import calls layout(): same pattern as check_package_shape; verify importing both modules in one process in the bin tests.
- "api.py" and "adapters" are used by no other bin script: rg across app/bin and app/tests before step 4.
- package_toml's first import from bin: verify python -m bin.new_package and the tests still import cleanly (no cycle).
- layout() is @cache: tests that build a Layout from tmp manifests do not affect the module constants (they never did).
- The drift test compares kinds' entries with the ADR table only: verify it ignores top-level role keys like grows_into_package before step 1; if it does not, extend it the same way grows_into_package is handled.

## Blast radius and rollback
Dev/CI tooling and three ADR lines; no runtime import of bin, merge deploys nothing. A wrong accessor would change a guard's verdict (a missed or false violation) or make the loader refuse at import; the unchanged-assertion tests and the five make checks catch both. One git revert restores everything; no ordering constraints, no config or terraform.

## Domain-model evolution
Not applicable: no domain entity; the loader gains read accessors and one validated key on an existing frozen dataclass.

## Gates
During TDD: cd app && uv run ruff check . and the targeted tests: uv run pytest tests/unit/bin -q. At the end, once each and sequential: uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)', then uv run pytest tests --ignore=tests/smoke. Plus make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams, check-fake-coverage (from app/); output into notes. Smoke tests not run.

## AC traceability
AC1: steps 1-4, layout_load tests + the unchanged guard tests. AC2: step 5, classify tests. AC3: steps 1-4 plus the rg check. AC4: Gates. AC5: step 5 tests. AC6: step 2. AC7: step 1, layout_load tests. AC8: step 6.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-11-19 on task-114.5-bin-guards-shared-definitions from main 6f9b7645. In Progress; Done is the human's.

What changed
- package_layout.toml: top-level public_api = "api.py". package_layout.py: Layout.public_api (refused unless every capability/core kind present requires it), Layout.adapters_dir (from options.adapters.entry), CORE_KIND/COMMON_KIND/CAPABILITY_KIND (Final), and check_tool_needs(): layout() refuses the repository manifest without the capability, core and common kinds or the adapters option. load_layout stays generic so tmp fixture manifests need only public_api.
- package_toml.py: FEATURES/CAPABILITIES from layout().roots (also the features.<umbrella> container and the capabilities slack-entrypoint glob); CORE/COMMON from the loader constants.
- check_package_shape.py: CORE/COMMON from the loader; the capability-consumer prefix from roots.features.
- new_package.py: COMMON constant deleted; UMBRELLA_MEMBER_KINDS, the CONSUMER regex, the promote moves and the interactive hints read the loader names.
- check_test_seams.py: PACKAGE_ROOTS from layout().roots; LEGACY_ROOT = "modules" named, comment ties it to migration.md Done.
- check_fake_coverage.py: CAPABILITY_API_MODULE_NAME and CAPABILITY_ADAPTERS_DIR deleted (rg: no other reader); public_api, adapters_dir and roots.capabilities from the loader.
- check_settings_key_ownership.py (beyond the plan's file list, same defect): RUN_SWITCH_ROOTS' features/ from roots.features. 9 production files.
- audit_env_names.py: RUNTIME = checker.PLATFORM_NAMES | the 8 AWS credential-chain names; RUNTIME_PREFIXES kept separate with the why-comment.
- ADRs: feature-packages.md Changes (entry roles, guards read the loader); migration.md Done drops LEGACY_ROOT; configuration.md Checks (env audit's runtime set narrower than the SDK namespace) and Changes.
- Tests: test_bin_package_layout_load.py (real-manifest names; public_api missing / a directory / not required by capability / by core refused; check_tool_needs passes a full manifest and refuses one missing the adapters option or the capability, core or common kind); test_bin_audit_env_names_classify.py (PLATFORM_NAMES subset of RUNTIME with only AWS_ names beside it; nine names pinned for audit action and SDK_NAMESPACE match side by side, incl. AWS_BUCKET check/match and UVICORN__X none/no-match). Existing assertions unchanged; MINIMAL fixture gains public_api.

AC #3 evidence: rg -n '"(features|capabilities|core|common|api\.py|adapters/?)"|["/.]features[./]|["]capabilities\.' bin/*.py lists only package_layout.py (definitions), docstrings/help text, and package_toml.py:38 type UmbrellaMember = Literal["subdomain", "core", "common"] (a type needs literals; mypy checks the loader's Final constants against it). Generic Python names inside check logic (__init__.py, README.md, entrypoints in the shape check) are rules of those checks, not duplicated layout definitions; left as is. The drift test ignores top-level role keys (verified: unchanged and green).

Gates (from app/)
- uv run ruff check . -> All checks passed!; ruff format --check bin -> 18 files already formatted
- uv run pytest tests/unit/bin tests/integration/bin -q -> 493 passed
- make check-import-contracts -> Contracts: 14 kept, 0 broken.
- make check-settings-key-ownership -> OK: every settings key and configuration table has one owner, ...
- make check-package-shape -> OK: no net-new package-shape violations (3 baselined violation(s) remain).
- make check-test-seams -> OK: no net-new strict-zone patches (47 baselined); OK: no net-new legacy pin seams (12 baselined)
- make check-fake-coverage -> OK: every covered Protocol has an in-memory fake (4 baselined gap(s) remain).
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 40 errors in 13 files (checked 452 source files): pre-existing legacy baseline (modules/incident/...), none in bin/. Run twice by mistake (second run only to filter bin/ lines).
- uv run pytest tests --ignore=tests/smoke -> 7814 passed, 231 warnings in 230.11s

Blast radius: dev/CI tooling and ADR text only; merge deploys nothing. One git revert restores everything.
<!-- SECTION:NOTES:END -->
