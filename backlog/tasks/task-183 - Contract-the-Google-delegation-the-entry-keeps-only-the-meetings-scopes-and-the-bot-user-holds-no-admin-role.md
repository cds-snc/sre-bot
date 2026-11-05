---
id: TASK-183
title: >-
  Contract the Google delegation: the entry keeps only the meetings scopes and
  the bot user holds no admin role
status: To Do
assignee: []
created_date: '2026-11-05T00:09:00Z'
updated_date: '2026-11-05T00:13:00Z'
labels:
  - security
milestone: m-7
dependencies:
  - TASK-180
  - TASK-181
references:
  - decisions/service-accounts.md
  - app/integrations/google_workspace/README.md
priority: high
type: chore
ordinal: 480000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Contract step of the TASK-169 ruling (2026-11-05, human), human-led in the Google Admin console. After TASK-181 only Calendar and Meet delegate, so the domain-wide delegation entry needs only calendar.events, calendar.freebusy and meetings.space.created. Delegation cannot be limited to particular users and can reach super admins (https://knowledge.workspace.google.com/admin/apps/control-api-access-with-domain-wide-delegation), so every other scope on the entry is a standing power over every account in the domain. The entry today holds scopes no bot code requests (reviewed with the human on 2026-11-05; the list is deliberately not recorded in the repository).

The bot's Workspace user stays: it is the organiser of meetings and invitations. Its admin role moved to the service account in TASK-181, so the user keeps none.

Precondition: the entry's client id ("CDS-SNC Apps") may be shared by other applications. Before any scope is removed, confirm the service account serves only the bot; otherwise the bot first moves to its own service account in cdssnc (same steps as TASK-180, new delegation entry) and this task is re-planned.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Precondition checked: the service account and its client id serve only the bot (GCP activity for the account, and the owners of anything else found); otherwise the move to a dedicated account is planned first
- [ ] #2 The delegation entry lists exactly calendar.events, calendar.freebusy and meetings.space.created (Admin console > Security > Access and data control > API controls > Manage domain wide delegation)
- [ ] #3 The bot's Workspace user holds no admin role and stays licensed as the meeting organiser
- [ ] #4 decisions/service-accounts.md Migration closes the delegation divergences and the README service identity section states the final entry
- [ ] #5 After the change: deploy-checks post google passes and TASK-181's manual checks pass again; rollback is re-adding the removed scopes from the human's own record, kept outside the repository
- [ ] #6 The google task check is deleted from bin/deploy-checks.zsh once this task is Done (checks belong to their task)
- [ ] #7 The runbook's transition section is deleted and its steps match the final delegation entry
<!-- AC:END -->
