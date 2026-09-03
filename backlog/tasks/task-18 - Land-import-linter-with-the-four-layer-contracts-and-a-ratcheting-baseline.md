---
id: TASK-18
title: Land import-linter with the four layer contracts and a ratcheting baseline
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-03 16:14'
labels:
  - toolchain
  - phase-2
  - architecture
milestone: m-2
dependencies: []
references:
  - decisions/toolchain.md
  - decisions/layers.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1272'
priority: high
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Import contracts) and decisions/layers.md (Checks). Nothing enforces layering today; five old ADRs relied on an import-linter that was never installed.

Steps:
1. Add import-linter to [dependency-groups]; configure [tool.importlinter] with root_packages set to the flat top-level names (packages, infrastructure, integrations, server, api, modules) per the deliberate flat-layout decision in decisions/toolchain.md.
2. Four contracts:
   a. Layers: packages -> infrastructure -> integrations (dependencies point downward only).
   b. Feature independence: packages/* subpackages independent of each other.
   c. integrations imports nothing from upper tiers except infrastructure.operations (the declared shared kernel).
   d. packages/** may import integrations only inside adapters/ modules.
3. Seed per-contract ignore_imports with every current violation (the ~38 upward imports and the deprecated-client consumers) so the suite lands green; enable unmatched_ignore_imports_alerting so stale entries are flagged and the list only shrinks.
4. Add lint-imports to CI as a blocking step.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 lint-imports passes in CI with the four contracts configured
- [ ] #2 A deliberate new violation (draft commit) fails CI; reverted
- [ ] #3 ignore_imports entries are per-contract, dated/attributed in comments, and unmatched alerting is on
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 CI blocking; baseline snapshot committed
- [ ] #2 PR references decisions/toolchain.md and decisions/layers.md
<!-- DOD:END -->

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
<!-- COMMENTS:END -->
