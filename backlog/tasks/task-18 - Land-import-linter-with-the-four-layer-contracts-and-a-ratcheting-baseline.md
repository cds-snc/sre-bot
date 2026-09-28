---
id: TASK-18
title: >-
  Land import-linter with the six-layer plugin-architecture contracts and a
  ratcheting ignore list
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-28 14:55'
labels:
  - toolchain
  - phase-2
  - architecture
  - plugin-architecture
milestone: m-7
dependencies: []
references:
  - decisions/toolchain.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1272'
  - decisions/plugin-architecture.md
  - decisions/migration.md
priority: high
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24 to decisions/plugin-architecture.md, which says: "Enforcement comes before any move." Import-linter contracts for its layer table land first; existing violations become ignore_imports entries that may only be removed (unmatched_ignore_imports_alerting = error); layers that don't exist yet are marked optional. The earlier four-contract scope (packages -> infrastructure -> integrations) followed the deleted decisions/layers.md.

Configure [tool.importlinter] with root_packages set to the flat top-level names (decisions/toolchain.md): the six layers contracts, server, features, capabilities, infrastructure, integrations, plus the transitional top-level packages packages, modules, jobs, api, models and utils (decisions/migration.md table).

Contracts (decisions/plugin-architecture.md Checks, feature-packages.md Checks, migration.md Checks, outbound-clients.md Checks):
a. layers: server > features > capabilities > infrastructure > integrations > contracts. contracts, features and capabilities are optional until created. Place packages beside features for as long as it exists; modules, api and jobs are legacy, sitting above features and below server.
b. forbidden: features, capabilities (and packages) never import infrastructure or server.
c. forbidden: contracts imports nothing else from the app.
d. forbidden: integrations imports nothing from the app except contracts.
e. forbidden: features, capabilities and packages import integrations only from adapters/ modules.
f. independence: the packages in features/ (and in packages/ while it exists).
g. forbidden: nothing in features, capabilities, contracts, infrastructure or packages imports modules.
h. per-umbrella layers contract with containers = the umbrella, subdomains as independent siblings above common, exhaustive = true (access today; incident when its umbrella exists).
The forbidden rule that nothing outside server imports provider modules binds once the service registry exists; it is added by the registry ticket, not here.

Seed each contract's ignore_imports with every current violation so the suite lands green. Add lint-imports to CI as a blocking step.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 lint-imports runs as a blocking CI step with contracts a-h from the description configured over the flat root packages
- [ ] #2 contracts, features and capabilities are declared optional, so each contract binds the moment that directory is created
- [ ] #3 A deliberate new violation (draft commit) fails CI; reverted
- [ ] #4 ignore_imports entries are per-contract, dated/attributed in comments, and unmatched alerting is on
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 CI blocking; baseline snapshot committed
- [ ] #2 PR references decisions/toolchain.md and decisions/plugin-architecture.md (decisions/layers.md was deleted 2026-09-24 and replaced by plugin-architecture.md)
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Ground truth (empirically verified 2026-09-28, see report for full session evidence):
- import-linter 2.15, installed and run via a scratch venv (not committed) against app/ using a [tool.importlinter] TOML config equivalent to the one below, `cd app && lint-imports --config <scratch>.toml --no-cache`.
- root_packages that currently exist as real packages (have __init__.py) and match app/pyproject.toml's [tool.hatch.build.targets.wheel] packages list: server, packages, infrastructure, integrations, modules, api, jobs, models, utils. `contracts`, `features`, `capabilities` do not exist yet; import-linter's `root_packages` validator calls `importlib.util.find_spec` and hard-errors ("Could not find package 'features' in your Python path") if a nonexistent package is listed there, so these three are named ONLY inside layer definitions using optional-layer syntax `(name)`, never in root_packages. `bin/`, `geodb/`, `locales/`, `tests/` are excluded (bin is tooling per decisions/migration.md; geodb/locales have no __init__.py; tests is the app's own test tree).
- Optional-layer syntax is parentheses: `"(modules) | (api) | (jobs)"` — confirmed in importlinter/contracts/layers.py (`ModuleTail.is_optional`, `raw_module_tail.startswith("(")`).
- `unmatched_ignore_imports_alerting` defaults to `error` already (importlinter/contracts/forbidden.py, independence.py) — no need to set it explicitly, but AC #4 asks for it to be visibly "on", so set it explicitly per contract for reviewability.
- Running contracts a, b, d, e, f from the task description against current app/ code gives these REAL violation counts (raw edges, before any wildcard consolidation): (a) layers: 23 (jobs/api -> modules edges, infrastructure -> jobs); (b) packages never import infrastructure/server: 97, all packages->infrastructure, zero packages->server; (c) contracts imports nothing from the app: 0 (contracts/ doesn't exist, contract starts clean); (d) integrations imports nothing but contracts: 19 (all integrations.<vendor> -> infrastructure.*, matches decisions/outbound-clients.md's Migration tolerances); (e) packages import integrations only via adapters/: 49; (f) independence across packages/*: 3, all packages.oncall_sync -> packages.user_rotations (matches decisions/feature-packages.md's known oncall_sync/user_rotations coupling, TASK-123's job to remove); (g) nothing in features/capabilities/contracts/infrastructure/packages imports modules: 0, already clean; (h) packages.access per-umbrella layers (catalog|request|sync over common, exhaustive): 0, already clean, confirms the 2026-09-03 comment's claim still holds.
- Total ~191 raw violation edges need `ignore_imports` entries across contracts a/b/d/e/f. Many share a (source-package, target-module) pattern across sibling submodules (e.g. every packages.aws_platform.adapters.* module importing integrations.aws.client/settings; every packages.access.sync.* module importing a different infrastructure.* service). These may be consolidated with import-linter's `*`/`**` wildcards, but ONLY within one already-identified, already-tolerated pattern (one source package, one target module or its submodule tree) — never a wildcard spanning multiple packages or multiple unrelated target modules, because a broad wildcard's `ignore_imports` entry stays "matched" (and so silent) for ANY future import fitting it, defeating the shrink-only ratchet. Prefer the narrowest wildcard that exactly covers today's edges; when in doubt use the exact `a.b.c -> x.y.z` edge.

Step 1 — `app/pyproject.toml`: add `import-linter` to `[dependency-groups] dev` (line ~178) via `uv add --group dev import-linter` (let uv pin the resolved version; do not hand-pin a version number that will drift). Run `uv lock` so `app/uv.lock` picks it up (uv.lock is a generated file, not hand-edited).

Step 2 — `app/pyproject.toml`: add a new `[tool.importlinter]` section (after `[tool.hatch.build.targets.wheel]`, end of file) with:
- `root_packages = ["server", "packages", "infrastructure", "integrations", "modules", "api", "jobs", "models", "utils"]`.
- Contract (a), `type = "layers"`, name e.g. "Six-layer plugin architecture":
  `layers = ["server", "(modules) | (api) | (jobs)", "(features) | packages", "(capabilities)", "infrastructure", "integrations", "(contracts)"]`, `unmatched_ignore_imports_alerting = "error"`, `ignore_imports` seeded with the 23 edges found in step 0 (jobs.scheduled_tasks -> modules.aws.identity_center / modules.aws.spending / modules.incident.notify_stale_incident_channels; infrastructure.plugins.specs -> jobs; plus the remaining ~19 integrations->infrastructure edges that also surface here because `infrastructure` sits directly above `integrations` in the layers list — verify the exact overlap at implementation time by diffing contract (a)'s and (d)'s violation output, since layers and forbidden contracts both see the same edges from different angles).
- Contract (b), `type = "forbidden"`, name "Packages, features and capabilities never import infrastructure or server": `source_modules = ["packages"]` (add `"features"`/`"capabilities"` only once TASK-106+ create them — they cannot be listed as root-relative source_modules before they exist, same nonexistent-package constraint as root_packages), `forbidden_modules = ["infrastructure", "server"]`, ignore list seeded with the 97 packages->infrastructure edges.
- Contract (c), `type = "forbidden"`, name "contracts imports nothing else from the app": `source_modules = ["contracts"]` is invalid today (contracts/ doesn't exist) — do NOT add this contract yet; add it in TASK-106 when `app/contracts/` is created, per plugin-architecture.md's "layers that don't exist yet are marked optional" (a forbidden contract has no optional-layer syntax, so the only sound way to keep it "green with no codebase change" ahead of contracts/ existing is to omit it, not to fake an ignore list against a package that can't be resolved). Record this as a one-line comment in the config pointing to TASK-106.
- Contract (d), `type = "forbidden"`, name "integrations imports nothing from the app except contracts": `source_modules = ["integrations"]`, `forbidden_modules = ["server", "packages", "infrastructure", "modules", "api", "jobs", "models", "utils"]`, ignore list seeded with the 19 integrations->infrastructure edges (matches decisions/outbound-clients.md Migration's tolerated list; comment references that record).
- Contract (e), `type = "forbidden"`, name "packages import integrations only from adapters/ modules": `source_modules = ["packages"]`, `forbidden_modules = ["integrations"]`, ignore list seeded with the 49 edges. Note some of these are the SAME underlying source lines as contract (b)'s violations when a package imports an `infrastructure` shim that itself imports `integrations` (import-linter reports the full chain as context but the ignore entry only needs the direct edge, e.g. `packages.access.sync.providers -> infrastructure.directory`, not the transitive `infrastructure.directory -> infrastructure.directory.factory -> integrations.google_workspace.client` shown beneath it).
- Contract (f), `type = "independence"`, name "packages/* are independent of each other": `modules` listing every current top-level `packages/*` entry (access, incident, incident_draft, incident_summary, aws_platform, geolocate, oncall_sync, rant, talent, user_rotations — verify the full current list with `ls app/packages`), ignore list seeded with the 3 `packages.oncall_sync -> packages.user_rotations` edges (references TASK-123, which removes this coupling).
- Contract (g), `type = "forbidden"`, name "Nothing outside legacy imports modules": `source_modules = ["packages", "infrastructure"]` (add features/capabilities/contracts once they exist), `forbidden_modules = ["modules"]`, no ignore list (starts clean — verify it is still clean at implementation time; if not, that is a new finding to report, not something to paper over with a new ignore entry).
- Contract (h), `type = "layers"`, name "Access subdomains are independent siblings over a shared kernel": `layers = ["catalog | request | sync", "common"]`, `containers = ["packages.access"]`, `exhaustive = true`, no ignore list (starts clean). Do not add a `packages.incident` container (packages/incident/ does not exist; TASK-38 adds it).
- Every `ignore_imports` list gets one leading TOML comment: `# seeded <today's date>, TASK-18, see decisions/plugin-architecture.md Migration / decisions/outbound-clients.md Migration` so removals are attributable per AC #4.

Step 3 — `app/Makefile`: add `check-import-contracts:` target below `check-aws-platform-seam` (~line 108), body `uv run lint-imports`, matching the existing `check-*` freeze-check targets' style; add `check-import-contracts` to the `.PHONY` line at the top of the file.

Step 4 — `.github/workflows/ci_code.yml`: add a new step "Import contract check" (`working-directory: ./app`, `run: make check-import-contracts`) after the existing "Runtime import check" step and before "Test", matching the existing freeze-check steps' shape.

Step 5 — Verify AC #3 by hand: add one deliberate new violation (e.g. a throwaway `import infrastructure` line in a `packages/` module), run `make check-import-contracts` locally to confirm it fails, then revert the throwaway line before committing. Do not commit the violating state at any point.

Step 6 — Run `cd app && uv run lint-imports` for real (not the scratch venv) to confirm the suite is green with the seeded ignore lists, then `make lint-ci`, `mypy` (scoped: this change touches no `.py` files, so 0 new mypy findings expected), and the existing `make test` / `make check-*` targets to confirm nothing else regressed.

AC traceability:
- AC #1 (lint-imports blocking CI, contracts a-h configured) -> Steps 2, 3, 4. Verified by: CI run showing the new step, and `make check-import-contracts` exiting 0 locally. Note: contract (c) is deliberately NOT added yet (see Step 2); report this as a scope note, not a silent AC failure — the task description's "contracts a-h" presumes `contracts/` may be declared as an optional forbidden-contract source, which import-linter does not support the way it supports optional layers. Flag this to the human reviewer explicitly.
- AC #2 (contracts/features/capabilities declared optional) -> Step 2's layers contract (a) uses `(features)`, `(capabilities)`, `(contracts)` optional syntax. Verified by re-running lint-imports after creating a throwaway `app/contracts/__init__.py` locally (then deleting it) and confirming the layers contract still passes/binds without config changes.
- AC #3 (deliberate new violation fails CI, then reverted) -> Step 5.
- AC #4 (ignore_imports per-contract, dated/attributed, unmatched alerting on) -> Step 2's per-contract comments and explicit `unmatched_ignore_imports_alerting = "error"`.
- DoD #1 (CI blocking, baseline snapshot committed) -> Step 4 (CI step) + Step 2 (the seeded pyproject.toml is the "baseline snapshot", committed with the PR).
- DoD #2 (PR references decisions/toolchain.md and decisions/plugin-architecture.md) -> PR description step, no code change.

Test matrix (this is a config-only change; no new pytest files):
- Happy path: `make check-import-contracts` exits 0 against the current tree with the seeded config (Step 6).
- Failure path: AC #3's deliberate violation makes it exit non-zero (Step 5).
- Ratchet regression: manually confirm `unmatched_ignore_imports_alerting = "error"` fires by temporarily deleting one real violation's source line so its ignore entry goes unmatched, confirming lint-imports fails, then restoring the line (do this only in the scratch/local run, never commit).
- CI wiring: confirm the new "Import contract check" step appears and runs in the PR's Actions run.

Assumptions and doubts:
- Assumes `uv add --group dev import-linter` resolves cleanly against the existing dependency set (pluggy is already a runtime dependency at >=1.6.0; import-linter depends on grimp, click, typing-extensions — verify no version conflicts when running `uv lock`).
- Assumes the current `app/packages/*` top-level list used for contract (f) is exactly what `ls app/packages` shows at implementation time; re-verify immediately before writing the config, since packages move over the following tasks (this list is the one thing most likely to drift between planning and implementation).
- Assumes contract (b)'s 97-edge count and contract (e)'s 49-edge count don't need full manual enumeration in this plan (that duplicates work the tool does); the implementer re-runs `lint-imports` locally to get the authoritative current list rather than trusting this plan's counts verbatim, since a few days may pass between planning and implementation and other in-flight PRs could add or remove edges.
- Assumes wildcard consolidation is a judgment call left to the implementer per the narrow-wildcard rule above; if in doubt, prefer more (exact) ignore lines over fewer (broad) ones — the plan does not mandate a specific consolidated count.

Blast radius and rollback:
- Config-only change (pyproject.toml, Makefile, CI workflow); no app/*.py file changes, no runtime behavior change. A `git revert` of the PR fully restores prior state with no migration concerns.
- Risk if seeded incorrectly: a too-narrow ignore list makes CI red on merge (caught immediately, blocks nothing else since main isn't yet relying on this gate); a too-broad wildcard silently masks future violations (caught later by whoever eventually tightens the ratchet, mitigated by the narrow-wildcard rule above and by TASK-106+ needing every ignore entry to still resolve to real code they can point at when they migrate it).
- No ordering constraint on other in-flight PRs: this task only adds a new CI gate and touches no shared code paths, so it can land independently of everything except needing an accurate `ls app/packages` snapshot at write time.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-03 16:14
---
PROPOSED FIFTH CONTRACT (2026-09-03): umbrella subdomain containers. decisions/feature-packages.md gained an umbrella rule this session (complex features get packages/<feature>/<subdomain>/ + common/; flat <feature>_<subfeature> naming rejected). Its Checks delegate mechanical enforcement to this task. Contract (b) as written ("packages/* subpackages independent of each other") does not cover the INSIDE of an umbrella.

Add contract (e):

[[tool.importlinter.contracts]]
name = "Access subdomains are independent siblings over a shared kernel"
type = "layers"
layers = [
    "catalog | request | sync",
    "common",
]
containers = ["packages.access"]
exhaustive = true

Semantics: pipes make the subdomains mutually non-importable; common sits below so every subdomain may import it and it may import none of them; exhaustive = true fails CI when a directory is added under packages/access/ without being declared as a layer. That last part is what stops the umbrella from becoming a dumping ground, and it is the reason the umbrella won a flat layout on review - a containers contract cannot be written against flat root packages at all.

THIS ONE CAN LAND IN THIS TASK, GREEN, WITH NO CODEBASE CHANGES. Verified 2026-09-03 against packages/access:
- grep for cross-subdomain imports (each of catalog/request/sync importing another) returns zero matches; all sharing already goes through packages.access.common.
- direct children of packages.access are exactly catalog, common, request, sync (plus an empty __init__.py), so exhaustive is satisfied.
No ignore_imports seeding needed for this contract - unlike (a)/(c)/(d) it starts clean.

DO NOT add a packages.incident container yet. packages/incident/ does not exist; incident logic is still split across app/modules/incident/ (4636 LOC) and the flat packages/incident_draft, packages/incident_summary. Adding that container now would fail CI and block every PR. TASK-38 owns creating the umbrella and adding its container line to this contract as its final step; TASK-38 has been updated with an AC for it.

Suggested wording change to step 2(b) so the two contracts do not overlap ambiguously: "(b) Feature independence: top-level packages/* features independent of each other; per-umbrella sibling independence handled by contract (e)."

Reference: import-linter Layers contract docs (containers, multi-item layers via pipes, exhaustive/exhaustive_ignores) - https://import-linter.readthedocs.io/en/stable/contract_types/layers/
---

created: 2026-09-24 19:57
---
2026-09-24 rescope: decisions/layers.md was deleted and replaced by decisions/plugin-architecture.md; contracts follow its six-layer table. The existing plan was written for the four-contract scope and must be re-planned (/plan-task TASK-18) before implementation.
---

created: 2026-09-28 14:55
---
2026-09-28: implementation plan approved by human (Guillaume Charest) for the doc-2 Stack A / Wave 0 realignment.
---
<!-- COMMENTS:END -->
