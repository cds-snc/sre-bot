---
id: TASK-42
title: Write the transport-teams decision record (M365 Agents SDK evaluation)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-09-10 16:18'
labels:
  - teams
  - phase-6
milestone: m-6
dependencies: []
references:
  - decisions/platform-transports.md
  - 'https://github.com/cds-snc/sre-bot/issues/1296'
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-10 16:18
---
ARCHITECTURE CONSTRAINT ADDED 2026-09-10 (human-directed). Chat platforms are split by direction (decisions/platform-entrypoints.md, Draft):
- Entry point: SDK runtime and connection lifecycle, verification, dispatch and in-request replies. Goes to app/server/<platform>/, beside HTTP.
- Handler contract: typed request/response models, argument parser, OperationResult renderer, in-request reply Protocol and registrar Protocol. Goes to app/infrastructure/<platform>/, with no runtime and no I/O.
- Messaging people or channels outside a request: goes to a capability package (decisions/capability-packages.md, Draft) or a Path B adapter.
- Web API client and classify_<platform>_error: app/integrations/<platform>/ (unchanged).

Features never receive SDK runtime objects such as the Bolt App. Do not move a runtime into app/infrastructure/<platform>/ in the meantime, so it moves only once.

The Teams decision record should adopt this split from the start: Bot Framework runtime in app/server/teams/, Teams handler contract in app/infrastructure/teams/. Acceptance of the Drafts is tracked in TASK-83.1.
---
<!-- COMMENTS:END -->
