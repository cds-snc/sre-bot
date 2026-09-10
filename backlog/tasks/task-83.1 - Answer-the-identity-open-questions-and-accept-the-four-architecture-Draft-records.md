---
id: TASK-83.1
title: >-
  Answer the identity open questions and accept the four architecture Draft
  records
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
  - architecture
dependencies: []
references:
  - decisions/governance.md
parent_task_id: TASK-83
priority: high
ordinal: 168000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Four Draft records dated 2026-09-10 set the direction for identity, shared capabilities and platform entry points:
- decisions/workplace-systems.md
- decisions/capability-packages.md
- decisions/people-and-accounts.md
- decisions/platform-entrypoints.md

Implementation under the people-and-accounts coordinator must not start until they are accepted. decisions/governance.md makes Accepted the binding rule for new code, and requires reversals to cascade.

Open questions to settle first:
- Which verified-link mechanisms come first: SRE admin links only; self-service linking by signing in to both accounts; or an HR employee number, if populated in both directories (Microsoft Graph employeeId, Google Directory externalIds of type organization).
- The authoritative source of contractors, and the attribute that records a person's kind.
- How SRE reviews suggested links at employee scale (bulk confirmation) without auto-linking.

Cascade on acceptance (governance.md cascade rule):
- layers.md: Path A scope, promotion, platform transports.
- cloud-portability.md: contracts scoped to hosting services; directory removed from the backing-service list.
- feature-packages.md: capability packages, api.py, dependency rules.
- platform-transports.md and transport-slack.md: the entry point split.
- configuration.md: where transport settings live.
- README index.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The open questions in decisions/people-and-accounts.md are answered and recorded in the record
- [ ] #2 Each of the four Draft records is Accepted, or Rejected with its reason
- [ ] #3 Every accepted record's cascade is applied in the same PR, so layers.md, cloud-portability.md, feature-packages.md, platform-transports.md, transport-slack.md, configuration.md and README.md no longer contradict it
- [ ] #4 TASK-18's scope includes a packages layer contract that places features above capability packages, with exhaustive = true
- [ ] #5 TASK-26, TASK-33, TASK-42 and TASK-43 are re-scoped to the entry point split
<!-- AC:END -->
