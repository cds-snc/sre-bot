---
id: TASK-165.8
title: E10 Provisioned playbooks and incident personalisation
status: To Do
assignee: []
created_date: '2026-11-03T18:59:00Z'
updated_date: '2026-11-04T16:44:00Z'
labels:
  - incident
  - content
milestone: m-7
dependencies:
  - TASK-165.4
  - TASK-178
  - TASK-134
references:
  - .claude/skills/domain-model-evolution/SKILL.md
parent_task_id: TASK-165
type: feature
ordinal: 470000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deliver an organisation/team playbook pilot from provisioned content only, alongside bounded status-update personalisation and incident-type document templates. The playbook ADR decision and incident-type semantics land in A5. Team contacts or notifications must follow D33; if the organization has not established a reliable team/role source, keep the delivered playbook usable with person-level contacts and do not infer members from unstandardized groups.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Status updates retain fixed core fields and support bounded feature-specific fields with a versioned form contract and the agreed drafting guidance.
- [ ] #2 Organisation and team playbooks are provisioned, suggested, previewed, and applied by a person as additive one-shot changes; they are never automatically applied.
- [ ] #3 Incident types and per-type document templates follow the decision recorded in A5, and the configured Google template remains the default.
- [ ] #4 Team contacts follow the D33 decision; if the external source is not ready, the epic closes whole with person-level contacts and no group-expansion fallback.
- [ ] #5 Tests and documentation cover provisioned-content validation, playbook preview/apply, template selection, and status-update compatibility; managed writes are out of scope for this epic.
- [ ] #6 If A5 adopts provisioned incident classifications, adding a classification needs no code change. Older read clients show an unfamiliar classification explicitly without treating it as a known one; unsupported write values are rejected, and classifications never override authorization or lifecycle rules. Tests cover existing content, older clients and template defaults.
<!-- AC:END -->
