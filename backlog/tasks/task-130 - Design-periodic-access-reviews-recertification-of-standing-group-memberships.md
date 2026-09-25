---
id: TASK-130
title: Design periodic access reviews (recertification) of standing group memberships
status: To Do
assignee: []
created_date: '2026-09-25 18:06'
labels:
  - architecture
  - identity
  - access
  - security
milestone: m-4
dependencies:
  - TASK-129
references:
  - decisions/people-and-accounts.md
  - 'https://csf.tools/reference/nist-sp-800-53/r5/ac/ac-2/'
priority: low
ordinal: 278000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DESIGN SESSION, no production code yet. Split out of TASK-129 on 2026-09-25. Human direction: bot-driven attestation is the intended direction, but its implementation exceeds the scope of the authorization decision, and the organization isn't mature enough for it yet. TASK-129 only records that periodic reviews are required (NIST SP 800-53 r5 AC-2 and AC-6(7); the TBS Directive on Security Management calls for periodic review). Google Workspace has no native review campaign.

Questions for the design session, centred on the people who manage groups:
- What form a review request takes: a Slack or Teams notification, an email, a Backstage page.
- Whether that form changes with the size of the group's membership, for example one prompt per member for small groups and a bulk list for large ones.
- Who reviews each group: its owners, or its approver group in the requestable-groups catalogue.
- How often reviews run, per group or per sensitivity tier.
- What happens to an unanswered review.
- How a removal decided in a review is written to the IdP and audited.

Output: a UX and flow proposal validated with group managers, then an amendment to the authorization record and right-sized follow-up tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A design proposal describes the reviewer experience (channel, format, and how it scales with group size), validated with at least one group-managing team
- [ ] #2 The authorization decision record is amended with the chosen review model: reviewers, cadence, the unanswered-review outcome, and how removals reach the IdP with an audit record
- [ ] #3 Follow-up implementation tasks are created under the single-PR size gate; no production code changes
<!-- AC:END -->
