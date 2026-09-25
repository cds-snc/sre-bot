---
id: TASK-117
title: >-
  Choose the maintained i18n library behind the translator contract and record
  the decision
status: To Do
assignee: []
created_date: '2026-09-24 20:00'
labels:
  - plugin-architecture
  - i18n
  - architecture
milestone: m-7
dependencies: []
references:
  - decisions/i18n.md
  - decisions/governance.md
priority: medium
type: spike
ordinal: 259000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ARCHITECTURE DECISION, no implementation. decisions/i18n.md: "The implementation uses a maintained library, chosen in a separate decision." The in-house stack (app/infrastructure/i18n/) is tolerated until then, and TASK-72 shows its cost (unbounded t() memoization growing ECS memory).

Evaluate current maintained options with sourced evidence from current documentation, not recall: for example Babel/gettext, fluent.runtime, and python-i18n's successor status. Criteria:
- EN/FR plural and number formatting;
- YAML or PO catalogues kept per feature under locales/;
- runtime loading of catalogues registered at startup;
- per-request locale from contextvars;
- licence and maintenance activity;
- a parity check that can run in CI (TASK-21).
Record the choice as an amendment to decisions/i18n.md, or as a new record, per decisions/governance.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decisions/ record states the chosen library, the alternatives considered, and sourced evidence for each criterion in the description
- [ ] #2 The record states how per-feature catalogues are registered at startup and how the TASK-21 parity check reads them
- [ ] #3 decisions/i18n.md Migration names the implementation ticket
<!-- AC:END -->
