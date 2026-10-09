---
id: TASK-145.1
title: >-
  Move packages/incident to features/incident as it stands, with the first-mover
  wiring, before any rebuild slice
status: Done
assignee:
  - '@me'
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:43'
labels:
  - incident
  - features
  - chore
dependencies:
  - TASK-144
parent_task_id: TASK-145
priority: high
type: chore
ordinal: 351000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer A1 of TASK-145, the first slice: the incident umbrella moves from app/packages/incident/ to app/features/incident/ as it stands (core/, scribe/, documents/, drive/, meet/, scheduling/), so every later slice builds in the final home and nothing is renamed at the end. Pure move, no runtime change. Starts once the TASK-144 stack is merged, because those PRs edit scribe files.

THIS SLICE
- app/features/__init__.py (empty namespace) and the umbrella under it; the old path is deleted.
- First-mover wiring: "features" joins the hatch wheel packages, the import-linter root_packages, the ruff known-first-party list, and every contract that names "packages" as a source or forbidden module (no-host-imports, integrations-via-adapters, no-legacy-imports, contracts-leaf, integrations-leaf); the layers contract already lists (features) as an optional layer. feature-independence gains features.incident; the incident-umbrella contract's container becomes features.incident.
- Entry point "incident.scribe" = "features.incident.scribe"; the ignore entries for scribe's Google Docs adapter, the views module's infrastructure.i18n import and the service's integrations.openai import are renamed, never added.
- Every importer and mock patch string rewritten: tests (about 70 files), modules/incident (migration.md rule 5: an import-path change in a frozen module), jobs/scheduled_tasks.py, the legacy_surface registration test. Tests move to tests/unit/features/incident/ and tests/integration/features/incident/ with their names unchanged.
- The umbrella and scribe READMEs, the legacy_surface inventory and decisions/incident-management.md's tolerated list name the new path.
- Not in this slice: the package-shape check (TASK-114), per-environment enablement (TASK-112) and TOML settings (TASK-111) arrive on their own; settings slices and environment variable names are unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/features/incident/ holds core, scribe, documents, drive, meet and scheduling unchanged; app/packages/incident/ does not exist; every importer and patch string is rewritten
- [x] #2 features is a hatch wheel package, an import-linter root package and a ruff first-party package; every contract naming packages also names features; the umbrella and independence contracts name features.incident
- [x] #3 The entry point incident.scribe targets features.incident.scribe; the import-linter ignore list only renamed entries and did not grow
- [x] #4 Tests live under tests/unit/features/incident/ and tests/integration/features/incident/ and pass unchanged apart from paths; the legacy_surface suite passes
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Grounded at main d2d973ae (2026-10-09), TASK-144 fully merged. Pure move; no behaviour change.

## Discovered state
- The umbrella: app/packages/incident/{__init__.py (empty), README.md, core/, scribe/, documents/, drive/, meet/, scheduling/}, 50 files. app/packages/__init__.py is an empty marker; app/features/ does not exist.
- Importers outside the umbrella (rg 'packages\.incident', 83 files, 356 occurrences): app/jobs/scheduled_tasks.py; nine frozen legacy files app/modules/incident/{core,incident_conversation,incident_document,incident_folder,incident_helper,incident_roles,incident_status,information_update,schedule_retro}.py (an import-path change in a frozen module is allowed by migration.md rule 5); pyproject.toml; 73 test files under tests/unit/packages/incident/ and tests/integration/packages/incident/ plus tests/integration/legacy_surface/{conftest.py:27-38, test_slack_command_registration_surface.py:22-24 and the comment at :376}, tests/modules/incident/test_incident_conversation.py, tests/unit/modules/incident/test_incident_timeline_update.py. 26 of the 328 test occurrences are patch("packages.incident...") strings, which fail at patch time, not import time.
- pyproject.toml: entry point "incident.scribe" = "packages.incident.scribe" (45); hatch wheel packages list (212) and import-linter root_packages (219) name "packages" and the comment at 216-218 says to add features in the PR that creates it; the layers contract already lists "(features) | packages" (231); contracts naming "packages": no-host-imports source (257), contracts-leaf forbidden (315), integrations-leaf forbidden (322), integrations-via-adapters source (344), feature-independence modules (365), no-legacy-imports source (384), incident-umbrella containers (402); ignore entries 299-305 and 354 name packages.incident.*. ruff known-first-party already lists capabilities and features (70-84). mypy uses explicit_package_bases and excludes tests: nothing to change.
- Test package markers: tests/unit/packages/__init__.py, tests/unit/packages/incident/__init__.py and the same two under tests/integration/; tests/unit/features/ does not exist.
- Docs naming the path: app/packages/incident/README.md, app/packages/incident/scribe/README.md, tests/integration/legacy_surface/INVENTORY.md handler column rows 118-121, decisions/incident-management.md Migration ("the umbrella in packages/incident/ until the first TASK-145 slice moves it"). Dockerfile, app/bin and .github name no incident path.

## Steps
1. `git mv app/packages/incident app/features/incident`; add app/features/__init__.py (empty, like app/packages/__init__.py).
2. Rewrite every dotted reference: sed `packages\.incident` -> `features.incident` over app/ (imports, patch strings, pyproject entry point and ignore entries, the legacy_surface comment). Verify `rg 'packages\.incident' app` returns nothing.
3. pyproject.toml: add "features" to hatch packages (212), root_packages (219), and to the five contracts that list "packages" as source or forbidden (257, 315, 322, 344, 384); replace "packages.incident" with "features.incident" in feature-independence (365) and the incident-umbrella container (402). The layers contract needs no edit. Ignore entries were renamed by step 2: the list has the same length.
4. Tests: `git mv tests/unit/packages/incident tests/unit/features/incident` and the same under tests/integration/; add tests/unit/features/__init__.py and tests/integration/features/__init__.py; the incident __init__.py files move with their directories. File names unchanged.
5. Docs: path lines in the two READMEs; INVENTORY.md rows 118-121 handler column; incident-management.md Migration drops the "until the first TASK-145 slice moves it" clause and adds a dated Changes line; backlog doc-9 target-shape comment already says features.
6. Gates from app/: ruff, mypy, `uv run lint-imports`, pytest tests --ignore=tests/smoke; `uv build` to prove the wheel includes features; `uv sync` locally because the entry-point target changed.

## AC traceability
| AC | Steps | Evidence |
| --- | --- | --- |
| 1 | 1, 2, 4 | `rg 'packages\.incident' app` empty; `git diff -M --stat` shows renames only plus the import hunks |
| 2 | 3 | pyproject diff; `lint-imports` passes with features as a root |
| 3 | 2, 3 | entry-point line; ignore list same length (count the lines before and after) |
| 4 | 4 | full pytest run; legacy_surface suite green |
| 5 | 6 | gate output in the task notes |

## Test matrix
No new tests: the moved suite is the proof. One assertion is added to tests/unit/features/incident/scribe/test_incident_scribe_plugin_registration.py: the entry point group maps incident.scribe to features.incident.scribe (boot wiring).

## Assumptions and doubts
- import-linter accepts "features" as a root package only once app/features/__init__.py exists (its own comment says so): create the marker in the same commit.
- hatch includes a package by top-level name; verify with `uv build` and `unzip -l` on the wheel.
- tests/factories/slack_bolt.py and the server plugin tests name the plugin "incident.scribe" by entry-point name, not by module path: unaffected (verify with rg after step 2).
- The deploy picks up the new entry-point target through the image build; no runtime configuration names the module path (rg over terraform/ and .github/ for "packages.incident").

## Size
About 130 files, nearly all renames; roughly 60 import lines and 10 pyproject lines change. Mechanical, reviewed by `git diff -M --stat` plus the pyproject hunk. Same precedent as the TASK-124.x package moves.

## Blast radius and rollback
A missed path fails at import or boot, caught by lint-imports and the plugin-loading tests. Single `git revert`. No data, config or Terraform change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## What changed
- `git mv app/packages/incident app/features/incident` (50 files, all R100) and `app/features/__init__.py` added as the namespace marker. Tests moved with `git mv` to `tests/unit/features/incident/` and `tests/integration/features/incident/` (names unchanged); `tests/unit/features/__init__.py` and `tests/integration/features/__init__.py` added.
- `packages.incident` -> `features.incident` rewritten in 107 files: imports and patch strings in tests, the nine frozen `modules/incident` files (import line only, migration.md rule 5), `jobs/scheduled_tasks.py`, the legacy_surface conftest and registration test, the scribe i18n owner id, pyproject. Slash paths rewritten in the two READMEs, the documents Google Docs adapter docstring, INVENTORY.md rows 118-121, the legacy_surface comment and `decisions/incident-management.md` (tolerated list no longer names the move; dated Changes line added). `decisions/feature-packages.md` context line names `features/incident/`; its dated history line keeps the old path.
- pyproject: `features` added to hatch wheel packages, import-linter `root_packages`, and contracts (b), (c), (d), (e), (g); feature-independence lists `features.incident`; the incident-umbrella container is `features.incident`; entry point `incident.scribe = features.incident.scribe`. The permanent adapters allowance in (e) became `**.adapters.** -> integrations.**` so one entry covers both roots: the ignore list has 70 entries before and after, every `packages.incident` entry renamed, none added.
- Tests that encode the path: three boundary tests (drive, scheduling, documents) build the path from `features`; `test_server_plugins_entrypoint_declaration.py` scans both `packages/` and `features/` and accepts `<root>.<name>` targets. One assertion added to the scribe plugin registration test: the installed `incident.scribe` entry point resolves to `features.incident.scribe`.
- `uv sync` re-installed the project so the entry-point metadata matches; other checkouts need the same after pulling.

## Evidence (from app/)
- `uv run ruff check .`: All checks passed!
- `uv run lint-imports`: Contracts: 10 kept, 0 broken (features is a root package; (i) incident-umbrella kept over `features.incident`).
- `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`: Found 48 errors in 19 files, repo-wide and pre-existing. In touched files: `features/incident/scheduling/adapters/google_calendar.py` (2), `features/incident/meet/adapters/google_meet.py` (1), both R100 renames with no content change; `modules/incident/information_update.py` (6) on lines the import rename did not touch. 0 new errors.
- `uv run pytest tests --ignore=tests/smoke`: 4546 passed, 2357 warnings in 50.76s (includes legacy_surface and the moved suites).
- `uv build --wheel`: wheel lists 51 `features/incident/` files and 0 `packages/incident/` files; `entry_points.txt` has `incident.scribe = features.incident.scribe`.
- `rg 'packages[./]incident' app decisions Makefile Dockerfile .github terraform` returns nothing. `git diff HEAD -M --name-status`: 130 renames, 18 modified, 3 added.

## For the human
- Review the PR by `git diff -M --stat` plus the pyproject hunk; the production diff is import lines only.
- The deploy image rebuild picks up the new entry-point target; no config or Terraform change.
<!-- SECTION:NOTES:END -->
