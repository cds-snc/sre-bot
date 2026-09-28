---
id: TASK-83.6
title: >-
  Import Slack workspace users as accounts and link SSO members through the
  IdP-asserted email
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 17:05'
labels:
  - identity
dependencies:
  - TASK-83.4
  - TASK-25.4
  - TASK-64
references:
  - decisions/people-and-accounts.md
parent_task_id: TASK-83
priority: medium
ordinal: 173000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slack accounts are keyed by (slack, team_id, user_id), with known id aliases, because a Slack user id changes when a workspace joins an Enterprise org.

Slack enforces SSO against the IdP for full members, so their profile email was set by the IdP. decisions/people-and-accounts.md (Accepted 2026-09-25) allows an sso_email link when:
- the account is a full member (not is_restricted or is_ultra_restricted) of a workspace configured as SSO-enforced;
- its email matches exactly one active identity;
- the email is in an allowed domain of a trusted IdP.
Guests and accounts that don't match stay unlinked; per-feature access policies decide what they can use (TASK-129). The link is then keyed by the Slack user id, and the email is only recorded as its evidence.

Slack users are read through an adapter in app/capabilities/people/adapters/ built on the Slack client factory (TASK-25.4), with errors classified by classify_slack_error. The job registers through the register_background_jobs hookspec as a Tier-2 job with a lease from the coordination contract.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each Slack user in the configured workspace becomes one account keyed by team_id and user_id, with email and display name as attributes
- [ ] #2 A full member of an SSO-enforced workspace whose email matches exactly one active identity in an allowed domain gets one sso_email link with an audit event; a guest, no match or several matches stays unlinked
- [ ] #3 On a re-run, an account whose email no longer matches its linked identity is flagged for SRE and never moved to another person
- [ ] #4 Re-running the import creates no duplicate accounts, including for an id recorded as an alias
- [ ] #5 The job runs behind a setting that defaults to off and makes no writes to Slack
- [ ] #6 Slack is read only through app/capabilities/people/adapters/ using the Slack client factory; the job registers through register_background_jobs as a Tier-2 job with a lease
- [ ] #7 Full test suite, ruff and mypy pass
<!-- AC:END -->
