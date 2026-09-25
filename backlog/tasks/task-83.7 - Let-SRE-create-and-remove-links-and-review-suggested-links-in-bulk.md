---
id: TASK-83.7
title: >-
  Let SRE link accounts outside SSO, join people across IdPs and resolve flagged
  links
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 17:06'
labels:
  - identity
dependencies:
  - TASK-83.5
  - TASK-83.6
  - TASK-129
references:
  - decisions/people-and-accounts.md
  - decisions/security.md
parent_task_id: TASK-83
priority: medium
ordinal: 174000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
With the IdP import (TASK-83.5) and sso_email links (TASK-83.6), most accounts link without manual work (decisions/people-and-accounts.md, Accepted 2026-09-25). SRE handles three cases by hand:
- an account outside SSO, such as a Slack guest who should be recognised;
- a flagged sso_email link whose evidence diverged;
- a human with identities in two IdPs, who starts as two people. A shared email may suggest a join, but only an SRE action creates one.

Who counts as SRE is an IdP-group access policy (TASK-129). The interface (a Slack command and modal, or an HTTP admin endpoint) is chosen during planning.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Only callers allowed by the feature's access policy (TASK-129) can create, confirm or remove links or joins
- [ ] #2 Suggested cross-IdP joins come from shared attributes and are listed for review; they never create a join on their own
- [ ] #3 An admin link or join records admin provenance and one audit event naming who made it
- [ ] #4 A link to an identity or account already claimed by another person is rejected and shown to the reviewer
- [ ] #5 Resolving a flagged sso_email link either keeps it (audited) or removes it, leaving the account unlinked
- [ ] #6 Full test suite, ruff and mypy pass
<!-- AC:END -->
