---
id: TASK-114.4
title: >-
  Package generator reads the layout manifest and emits only the parts a package
  uses
status: In Progress
assignee: []
created_date: '2026-11-09T15:41:00Z'
updated_date: '2026-11-10T17:46:00Z'
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
- [x] #1 new_package.py holds no per-kind file list, option list or classification list: kinds, entries, options, templates and reserved names come from the manifest loader (TASK-114.3); PLUGIN_KINDS, AREA_KINDS and UMBRELLA_MEMBER_KINDS (generator behaviour, not layout) stay in code
- [x] #2 A capability generated with no optional flag holds exactly __init__.py, README.md and api.py; each optional flag adds only its entry; every combination passes make check-package-shape with an empty baseline (parametrized generator test)
- [x] #3 A feature or subdomain gets service.py and entrypoints/ by default and interfaces.py, adapters/ or settings.py only on request; core keeps api.py and service.py and gains interfaces.py or adapters/ only on request; umbrella, common and promote behave as before (their test assertions unchanged; the promote setup passes --interfaces)
- [x] #4 An option outside its kind, or --interfaces without --service on a capability, is refused naming feature-packages.md with nothing written; umbrella and promote take no option and refuse any; the interactive mode asks each option the kind takes from the manifest
- [x] #5 decisions/feature-packages.md: service.py and entrypoints/ optional for a capability; adapters/ and locales/ optional; the generator writes required entries and an optional entry only when its option flag is given, refuses an option the kind does not take or any option on umbrella or promote, and keeps config edits (entry points, contracts, enablement keys) in code as behaviour, not layout; dated Changes line; the manifest drift test (TASK-114.3) passes
- [x] #6 ruff, targeted generator and shape tests, then mypy and pytest tests --ignore=tests/smoke once each, make check-package-shape and make check-import-contracts pass, with output in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
APPROVED 2026-11-09 (human), with the program-scope assessment (notes, same date): step 6 wording revised; ACs #1, #4, #5 reworded.
Planned 2026-11-09 against main 3075170b (TASK-114.3 merged: app/bin/package_layout.toml, app/bin/package_layout.py with layout(), check_package_shape.py reading it). Rulings OQ1/OQ2/OQ3 from the task notes are applied, not re-asked. Domain-model gate: not applicable (tooling data, no domain entity). The superseded 114.3 generator test list did not survive (the 114.3 task file holds only the manifest plan); the matrix below is derived from the ACs and the existing generator tests.

GROUND (call sites found)
- bin/new_package.py hard-codes: KINDS :73, CLASSIFICATIONS :77, RESERVED_SUBDOMAINS :83, FEATURES/CAPABILITIES :71-72, the --settings flag :123 and Request.settings :100, _files kind matrix :282-308 (template per kind and file), the interactive "Settings slice?" question :529, kinds prompt :517, subdomain-name check :169 and promote :437. Behavioural edit logic (PLUGIN_KINDS :74, AREA_KINDS :75, UMBRELLA_MEMBER_KINDS :76, the TOML edits) is not layout and stays.
- app/bin/package_layout.toml today has capability extends feature with service.py and entrypoints/ REQUIRED (comment in the 114.3 plan: "114.4 moves them"); common declares no optional entry; no option or template data. bin/package_layout.py: Kind/Roots/Layout, _kind() applies exclude after adding the kind's own entries (:130-137), top-level keys fixed by TOP_LEVEL_KEYS :24.
- Existing tests touching generated shape: tests/integration/bin/test_bin_package_generator_create.py :113-122 (feature file set includes interfaces.py), :135-150 (capability asserts hookspecs.py), :165-184 (umbrella/core/common), :294-311 (interactive answers), :314-388 (promote). Unit: tests/unit/bin/test_bin_package_layout_load.py (MINIMAL manifest :27-41 has no options/templates, so those keys must be optional in the loader).
- Only other readers: Makefile new-package (passes ARGS), bin/package_templates/README.md ("the kind matrix in new_package.py maps each template"), umbrella_readme.md.tmpl and feature-packages.md mention the generator in prose.

DESIGN (manifest additions, all in app/bin/package_layout.toml)
- [options.<name>]: the optional flags, each naming the entry it adds and what it needs: hookspecs -> hookspecs.py; service -> service.py; entrypoints -> entrypoints/; interfaces -> interfaces.py (needs = ["service.py"]); adapters -> adapters/; settings -> settings.py. An option is available to a kind exactly when its entry is in that kind's OPTIONAL set, so the per-kind option table is derived, not written: capability takes hookspecs, service, entrypoints, interfaces, adapters, settings; feature/subdomain take interfaces, adapters, settings; core takes interfaces, adapters, settings; common takes settings; umbrella none. Optional entries with no option (domain.py, schemas.py, store.py, providers.py, plugin.py, locales/) are written by hand, as today.
- Per-kind [kinds.<k>.templates]: entry -> template file name ("" = empty file), inherited through extends and overridable (capability: README.md, api.py, hookspecs.py; core: __init__.py, README.md, api.py; common; umbrella). Replaces the _files matrix.
- Capability: required __init__.py, README.md, api.py; optional service.py, entrypoints/, hookspecs.py plus the inherited ones. common gains optional settings.py (open kind, union with the ADR table unchanged).
- Loader: exclude now drops INHERITED entries before the kind's own are added, so a capability can exclude service.py and entrypoints/ from feature's required and list them optional. Existing exclude tests unaffected (exclude-of-an-absent-name still refers to inherited names). New fields on Layout: options (frozen dataclass Option: name, entry, needs) and Kind.templates; validation names the key (option entry not declared by any kind, needs not an entry, template for an undeclared entry). options and templates are optional in the file so the 114.3 loader tests stay unchanged.
- The shape check's allowed names are the union of required and optional, which this change does not alter, so check-package-shape output is identical. Template for adapters/: new bin/package_templates/adapters_init.py.tmpl (docstring only; ruff INP001 needs the __init__.py, and it is the "never an empty placeholder" minimum, same as entrypoints/__init__.py).

STEPS (tests first)
1. Red tests (below): tests/unit/bin/test_bin_package_layout_load.py gains manifest cases; tests/integration/bin/test_bin_package_generator_create.py gains the option matrix and refusals and has its four affected assertions updated.
2. app/bin/package_layout.py (~+60 LOC): Option dataclass, options and templates parsing and validation, exclude-before-own-entries, Layout.options, Kind.templates, helper Layout.options_of(kind) returning the options whose entry is in that kind's optional set (manifest order).
3. app/bin/package_layout.toml (~+45 lines): the sections above; header comment updated (generator reads it).
4. app/bin/new_package.py (net ~-20 LOC, ~170 lines touched): delete KINDS, CLASSIFICATIONS, RESERVED_SUBDOMAINS, FEATURES/CAPABILITIES literals and _files; read them from layout(). KINDS for argparse = manifest kinds + "promote". Flags are added from layout().options; Request.settings becomes Request.options: frozenset[str]. New _check_options(request) called first in generate() before any read or write: refuse an option whose entry is not optional for the kind ("--hookspecs is not an option of a feature; it takes --interfaces, --adapters, --settings; see decisions/feature-packages.md"), refuse an option whose needs entry is absent from the package (required or chosen): "--interfaces needs --service on a capability (decisions/feature-packages.md)"; promote takes no layout option (previously ignored silently, now refused; see assumptions). File set = kind.required + chosen options' entries, each rendered from kind.templates; a directory entry writes its __init__.py. The settings option keeps its config/base.toml table edit, keyed by the option name. prompt_arguments asks "Include <entry>? (y/N)" for each option the chosen kind takes, read from the manifest (umbrella: none; promote: none). Docstring usage block updated.
5. app/bin/package_templates/adapters_init.py.tmpl (new, 1 line); package_templates/README.md: the "kind matrix in new_package.py" bullet becomes "the manifest's templates table".
6. decisions/feature-packages.md: layout table comments mark service.py and entrypoints/ "(optional for a capability)", adapters/ and locales/ "(optional)"; the clause "the generator will (TASK-114.4)" becomes: "the shape check and the generator both read it. The generator writes each kind's required entries, and an optional entry only when asked by an option flag named for it (--hookspecs, --service, --entrypoints, --interfaces, --adapters, --settings), never an empty placeholder; --interfaces needs --service on a capability, and an option the kind does not list, or an option given to umbrella or promote, is refused with nothing written. Which config files a kind edits (entry points, contracts, enablement keys) is generator behaviour, not layout, and stays in code." Changes: "- 2026-11-09: the generator reads the manifest and emits optional entries only on request; a capability requires only __init__.py, README.md and api.py; service.py, entrypoints/, adapters/ and locales/ are optional; options outside a kind are refused (TASK-114.4)." The manifest drift test must pass (names unchanged).
7. Gates (see below).

TEST MATRIX
Generator (tests/integration/bin/test_bin_package_generator_create.py; the 'root' fixture is reused, no new file):
- Happy: capability with no flag holds exactly {__init__.py, README.md, api.py}. Parametrized over every valid subset of the capability's six options (hookspecs, service, entrypoints, interfaces, adapters, settings; interfaces only with service; 48 cases): file set equals required plus chosen entries, directories hold their __init__.py, checker.find_violations() == set() with the empty baseline. One case (all flags) also runs the full _assert_consistent (ruff incl. INP001, contracts, enablement).
- Feature default = {__init__.py, README.md, service.py, entrypoints/}; feature/subdomain with --interfaces --adapters --settings add exactly those; core default = {__init__.py, README.md, api.py, service.py}, + interfaces/adapters on request, never entrypoints/; common default two files, --settings adds settings.py; umbrella unchanged (assertions untouched).
- Boundary: --interfaces with --service on a capability accepted; --interfaces on a feature accepted (service.py always there).
- Failure (nothing written, existing parametrized 'writes nothing' test extended, message names feature-packages.md): feature --hookspecs; feature --service; subdomain --entrypoints; core --entrypoints; core --hookspecs; common --interfaces; umbrella --settings; capability --interfaces without --service; promote --settings.
- Interactive: asks exactly the manifest's options for the kind (capability: six; core: three; umbrella: none), in manifest order, and returns the matching flags; existing prompt test updated to the new question list.
- Promote: setup passes --interfaces; every promote assertion unchanged.
- Existing assertions that must change (stated openly): feature file set loses interfaces.py (:116); the capability test passes --hookspecs for its hookspecs.py assertion (:135-150); the interactive test's answers (:294-311). Umbrella, common and promote assertions stay as they are.
Manifest (tests/unit/bin/test_bin_package_layout_load.py): real manifest: capability required exactly three, optional includes service.py/entrypoints/hookspecs.py; core optional includes interfaces.py and adapters/ and not entrypoints/; options_of per kind equals the table above; every template file named exists under bin/package_templates; every required entry of a generator-written kind has a template; malformed: option entry undeclared, needs unknown, template for an undeclared entry, unknown option key, exclude-then-reoptional works.

AC TRACEABILITY
- #1 no per-kind lists in new_package.py -> steps 2-4; manifest tests plus a test that scans new_package.py for the literals is unnecessary: review by diff; grep in notes (rg for "hookspecs.py|CLASSIFICATIONS|RESERVED_SUBDOMAINS" in new_package.py).
- #2 capability exactly three files, each flag adds only its entry, every combination passes shape check -> steps 2-4; the 48-case parametrized test.
- #3 feature/subdomain/core defaults and options, umbrella/common/promote unchanged -> step 4; feature, core, common, promote tests.
- #4 refusals and interactive -> step 4; refusal and interactive tests.
- #5 ADR -> step 6; drift test.
- #6 gates -> step 7.

SIZE: production files 6 (new_package.py, package_layout.py, package_layout.toml, adapters_init.py.tmpl, feature-packages.md, package_templates/README.md) plus 3 test files; about 300 production LOC changed (new_package ~170 touched / net -20, package_layout.py ~+60, manifest ~+45, ADR and README ~15, template 1). One subsystem (bin tooling), behaviour change only (the loader tweak is part of it; no mechanical refactor mixed in). Passes the gate.

ASSUMPTIONS (verify at implementation)
- Shape-check verdicts unchanged because required+optional union is unchanged: run make check-package-shape before and after, same output; the 114.3 shape tests pass untouched.
- A generated capability without service.py/entrypoints/ passes the shape check and plugin enablement: shown by the combination test.
- Refusing options on umbrella and promote (silently ignored today) is the AC #4 rule applied uniformly; no caller passes them (rg of Makefile, docs, skills found only ARGS pass-through).
- tomllib keeps table order, so options and prompts follow manifest order.
- 48 generate calls on the fixture are fast; if the file exceeds ~20 s, keep singles, pairs and all-flags instead and say so in the notes.
- 25.10.2 compatibility: 'capability text_generation --classification generic --consumer features.incident.scribe --consumer features.incident.comms --adapters' gives exactly __init__.py, README.md, api.py and adapters/__init__.py, so its "delete empty hookspecs.py, interfaces.py, service.py and entrypoints/" step disappears and only --adapters is added to its command (it has adapters/openai.py, unconfigured.py, in_memory.py); no --service, --interfaces, --hookspecs, --settings. The capability's enablement key, entry point and contracts are untouched by this task.

BLAST RADIUS AND ROLLBACK
Bin tooling plus one ADR edit; no runtime code, config or terraform. Failure modes: a wrong manifest breaks generation (every command refused) or the shape check; guarded by the loader and combination tests and the before/after check output. No consumer of generated output exists yet beyond the first capability (25.10.2, waiting on this). One git revert restores today's generator (manifest, loader, generator, template, ADR together). Merge before 25.10.2 starts; 114.5 reads the same manifest and is unaffected (additive keys).

VERIFICATION
During implementation: cd app && uv run ruff check . and the targeted tests only (tests/unit/bin/test_bin_package_layout_load.py, tests/unit/bin/test_bin_package_shape_check.py, tests/integration/bin/test_bin_package_generator_create.py). At the end, once each and sequentially: uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)', then uv run pytest tests --ignore=tests/smoke; plus make check-package-shape and make check-import-contracts. Output pasted in notes (pre-existing mypy errors in legacy modules/ called out, not fixed).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (human, ruled under TASK-114.3 before the split): OQ1 approved (core takes --interfaces/--adapters; --interfaces needs --service on a capability); OQ2 approved (the table marks adapters/ and locales/ optional); OQ3 approved (the planned-consumer option stays with TASK-83.4). Plan at pickup against main after 114.3 merges; the superseded 114.3 plan (git history of task-114.3) carries the test list for this behaviour.

2026-11-09: planned, proposed, awaiting approval. Size verdict: passes the single-PR gate (6 production files, about 300 production LOC, one subsystem: bin tooling; behaviour change only; one git revert restores today's generator). No open question for the human: OQ1-OQ3 applied as ruled; umbrella/promote option refusal and the 25.10.2 command (adds --adapters) are stated as assumptions.

2026-11-09 (human): plan approved with the program-scope assessment: no ADR conflict; two gaps closed in feature-packages.md by step 6 (generator rule incl. refusals and the layout/behaviour boundary; 'optional for a capability', the shape check cannot see which Protocol a capability implements). AC #1, #4, #5 reworded as proposed in comment #1 plus the assessment. Prior: TASK-114.2 (--settings refused on umbrella), TASK-114.3 re-plan (manifest is layout only, Q3/Q4). Upcoming generator users: TASK-25.10.2 (command gains --adapters), TASK-83.4 (compatible), TASK-146.1 and TASK-119 pick options at their planning. Sources: clig.dev (check early, bail out, understandable errors); nx.dev/generators/generator-options (declarative option schema, file edits in generator code); copier.readthedocs.io configuring (conditional files); alistair.cockburn.us/hexagonal-architecture (ports required, adapters pluggable).

2026-11-10: implemented on task-114.4-package-generator-manifest (from main 8b8d1aeb). Tests first (86 red), then green.
- Manifest (bin/package_layout.toml): [options.<name>] for hookspecs, service, entrypoints, interfaces (needs service.py), adapters, settings; per-kind templates tables (inherited through extends, filtered to the kind's entries); capability excludes service.py and entrypoints/ from feature's required and lists them optional; common gains optional settings.py. New template bin/package_templates/adapters_init.py.tmpl.
- Loader (bin/package_layout.py): Option dataclass, Kind.templates, Layout.options and options_of(kind) (options whose entry the kind lists optional, manifest order); exclude now applies to inherited entries before the kind's own are added; options and templates optional in the file; validation names the key (option entry or needs undeclared, unknown option key, template for an undeclared entry).
- Generator (bin/new_package.py): KINDS, CLASSIFICATIONS, RESERVED_SUBDOMAINS, FEATURES/CAPABILITIES literals and the _files matrix deleted; read from layout(). Flags built from layout().options; Request.settings -> Request.options. _check_options runs first in generate(), before any read or write: option outside the kind, any option on umbrella or promote, and --interfaces without --service on a capability are refused naming decisions/feature-packages.md. Interactive mode asks 'Include <entry>? (y/N)' for each option the kind takes. PLUGIN_KINDS, AREA_KINDS, UMBRELLA_MEMBER_KINDS stay in code. rg for 'hookspecs.py|CLASSIFICATIONS|RESERVED_SUBDOMAINS' in new_package.py: no match.
- ADR decisions/feature-packages.md: table marks service.py and entrypoints/ optional for a capability, adapters/ and locales/ optional; generator rule incl. refusals and the layout/behaviour boundary; Changes line 2026-11-10. bin/package_templates/README.md points at the manifest's templates tables.
- Tests: tests/unit/bin/test_bin_package_layout_load.py (real-manifest kinds, options_of per kind, templates exist for every written entry, inherited templates, exclude-then-optional, four malformed cases); tests/integration/bin/test_bin_package_generator_create.py (48-case capability combination matrix with checker.find_violations() == set() and full _assert_consistent on all flags; feature/subdomain/core/common defaults and options; refusals write nothing; interactive questions per kind). Changed existing assertions as planned: feature set loses interfaces.py, capability test passes --hookspecs, interactive answers, promote setup passes --interfaces; umbrella/common/promote assertions unchanged. Generator file runs in 8.6 s, so the full matrix stays.
Gates (from app/):
- uv run ruff check . -> All checks passed!
- uv run pytest tests/unit/bin tests/integration/bin -> 473 passed
- make check-package-shape -> OK: no net-new package-shape violations (3 baselined violation(s) remain).
- make check-import-contracts -> Contracts: 13 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 41 errors in 14 files (checked 425 source files); all pre-existing in legacy modules/ (same count as the L3 baseline), none in touched files.
- uv run pytest tests --ignore=tests/smoke -> 6875 passed in 208.33s
TASK-176 asked at start (2026-11-10): nothing changed (#1, #4 open; #2 waits on TASK-182).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-09T20:02:00Z

---

AC proposals (none applied, human decides). #1: clarify that PLUGIN_KINDS, AREA_KINDS and UMBRELLA_MEMBER_KINDS (which TOML edits a kind gets) stay in code; they are behaviour, not layout. #4: add 'promote takes no layout option' (today ignored silently, the plan refuses it). Both are covered by the plan as written; no AC removal proposed.

---
<!-- COMMENTS:END -->
