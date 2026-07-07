---
id: TASK-42
title: Write the transport-teams decision record (M365 Agents SDK evaluation)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - teams
  - phase-6
milestone: m-6
dependencies: []
references:
  - decisions/platform-transports.md
priority: low
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
BLOCKED until Teams is funded - do not start speculatively (decisions/platform-transports.md honesty note: the pattern is a default extracted from n=1).

When funded:
1. Evaluate the M365 Agents SDK (successor to Bot Framework) against the platform-transport slots: runtime/lifecycle, inbound verification (JWT), outbound Protocol (TeamsService), helpers, registration hookspecs.
2. Write decisions/transport-teams.md per decisions/governance.md format with real Considered Options and honest Checks.
3. Record where the Slack-derived composition pattern does NOT fit Teams - divergence is information, not violation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/transport-teams.md exists, Accepted, with real options considered and executable Checks
- [ ] #2 decisions/README.md index updated
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Reviewed against decisions/platform-transports.md slot model
<!-- DOD:END -->
