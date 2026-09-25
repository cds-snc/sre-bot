---
id: TASK-18
title: >-
  Land import-linter with the six-layer plugin-architecture contracts and a
  ratcheting ignore list
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-24 19:57'
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

created: 2026-09-24 19:57
---
2026-09-24 rescope: decisions/layers.md was deleted and replaced by decisions/plugin-architecture.md; contracts follow its six-layer table. The existing plan was written for the four-contract scope and must be re-planned (/plan-task TASK-18) before implementation.
---
<!-- COMMENTS:END -->
