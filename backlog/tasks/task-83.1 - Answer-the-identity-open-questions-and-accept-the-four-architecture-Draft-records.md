---
id: TASK-83.1
title: >-
  Answer the identity open questions and accept the three remaining identity and
  entry-point Draft records
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-24 20:08'
labels:
  - identity
  - architecture
dependencies: []
references:
  - decisions/governance.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-83
priority: high
ordinal: 168000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Updated 2026-09-24. Three Draft records dated 2026-09-10 still set the direction for identity and platform entry points:
- decisions/workplace-systems.md
- decisions/people-and-accounts.md
- decisions/platform-entrypoints.md
The fourth, decisions/capability-packages.md, was deleted. decisions/plugin-architecture.md (Accepted 2026-09-24) replaced it and the deleted layers.md, and commit 3407cd5c already rewrote cloud-portability.md, feature-packages.md, platform-transports.md, transport-slack.md, configuration.md and README.md to match the six layers. The cascade this ticket used to own is done. Re-scoping TASK-18, TASK-26, TASK-33, TASK-42 and TASK-43 to the entry-point split was also done on 2026-09-24.

Implementation under the people-and-accounts coordinator must not start until these records are accepted: decisions/governance.md makes Accepted the binding rule for new code.

Open questions to settle first:
- Which verified-link mechanisms come first: SRE admin links only; self-service linking by signing in to both accounts; or an HR employee number, if populated in both directories (Microsoft Graph employeeId, Google Directory externalIds of type organization).
- The authoritative source of contractors, and the attribute that records a person's kind.
- How SRE reviews suggested links at employee scale (bulk confirmation) without auto-linking.

decisions/interaction-toolkits.md is also Draft but is not part of this ticket; its tickets are created on acceptance.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The open questions in decisions/people-and-accounts.md are answered and recorded in the record
- [ ] #2 Each of workplace-systems.md, people-and-accounts.md and platform-entrypoints.md is Accepted, or Rejected with its reason
- [ ] #3 Any cascade an acceptance still requires is applied in the same PR, so no Accepted record contradicts another
<!-- AC:END -->
