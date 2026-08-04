---
id: TASK-18
title: Land import-linter with the four layer contracts and a ratcheting baseline
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
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
