---
id: TASK-181
title: >-
  Google gateway delegates only for Calendar and Meet; every other call runs as
  the service account itself
status: To Do
assignee: []
created_date: '2026-11-05T00:09:00Z'
updated_date: '2026-11-05T00:13:00Z'
labels:
  - security
milestone: m-7
dependencies:
  - TASK-145.6
references:
  - decisions/service-accounts.md
  - app/integrations/google_workspace/README.md
priority: high
type: feature
ordinal: 478000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the TASK-169 ruling (2026-11-05, human; decisions/service-accounts.md rule 5). Every Google call today delegates to the bot's Workspace user (client.py applies tenant.delegated_user_email to every service), which is why the delegation entry must hold every scope the bot uses. Only two operations need a user identity: Calendar events with attendees ("Service accounts need to use domain-wide delegation of authority to populate the attendee list", https://developers.google.com/workspace/calendar/api/v3/reference/events) and Meet spaces (user authentication only, https://developers.google.com/workspace/meet/api/guides/authenticate-authorize). Directory reads and group writes run as the service account with the bot user's admin role assigned to it (https://developers.google.com/workspace/guides/create-credentials); Drive, Docs and Sheets run as the service account through its Content manager membership on the SRE shared drive (it is already a member).

The bot always acts as itself (rule 5): no call delegates to the requesting person; who asked is named in the content and recorded in the app.

Scope:
- client.py: only the Calendar and Meet factories apply the delegation subject; Directory, Drive, Docs and Sheets build for the service account itself (behaviour change).
- The delegated_user_email parameter is deleted from the drive, directory and spreadsheet providers, the talent adapter and the incident adapters (dead once the gateway decides).
- Calendar scopes narrowed from calendar to calendar.events (events.insert) and calendar.freebusy (freebusy.query).
- Same service account, so the Drive appProperties the bot wrote stay readable (private properties belong to the OAuth client id: https://developers.google.com/workspace/drive/api/guides/properties); the pre-merge check confirms it.

Planning: apply the size gate; the gateway behaviour and the parameter deletion may be two PRs (behaviour first, deletion second). Placed after TASK-145.6 so fewer incident adapters are touched.

Human before merge (additive, nothing removed): assign the bot user's admin role (Groups read and update, Users read) to the service account (Admin console > Account > Admin roles > the role > Assign service accounts); confirm the account is Content manager on the SRE shared drive; add calendar.freebusy to the delegation entry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Only the Calendar and Meet factories apply the delegation subject; Directory, Drive, Docs and Sheets services are built for the service account itself; a test pins which factories delegate
- [ ] #2 No delegated_user_email parameter remains on the drive, directory and spreadsheet providers, the talent adapter or the incident adapters; grep finds it only on the gateway's meetings path and the tenant entry
- [ ] #3 Calendar calls request calendar.events (events.insert) and calendar.freebusy (freebusy.query), not calendar
- [ ] #4 Before merge (human, additive): the bot user's admin role is assigned to the service account, its Content manager membership on the SRE shared drive is confirmed, calendar.freebusy is on the delegation entry, and a Codespace run as the service account without a subject reads an existing incident document's appProperties and lists the incident folder
- [ ] #5 ruff, mypy, lint-imports, make check-import-contracts, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [ ] #6 After deploy: deploy-checks post google passes (the check TASK-180 adds) and the manual checks pass: /incident declare (folder, document, Meet link), a floppy_disk timeline entry, an access request adding and removing a group member, a talent role folder, retro scheduling with invitations
- [ ] #7 The runbook and the README service identity section match the new delegation split (cascade rule, governance.md)
<!-- AC:END -->
