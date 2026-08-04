---
id: TASK-43
title: Implement the Teams transport and re-validate the composition pattern at n=2
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:58'
labels:
  - teams
  - phase-6
milestone: m-6
dependencies:
  - TASK-42
references:
  - decisions/platform-transports.md
  - 'https://github.com/cds-snc/sre-bot/issues/1297'
priority: low
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
BLOCKED until task-42 lands.

1. Implement app/infrastructure/teams/ per the decided record: runtime + lifecycle in lifespan phases, inbound JWT verification, TeamsService outbound Protocol, renderer, hookspecs.
2. Web API client + classify_teams_error in app/integrations/teams/.
3. Pick one existing feature and add a Teams handler beside its Slack handler (thin per-platform handlers, shared service layer) as the validation case.
4. Amend decisions/platform-transports.md with what n=2 taught; only then does the pattern graduate from default to validated standard.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A feature responds on both Slack and Teams with one shared service layer
- [ ] #2 Verification lives in the transport; no Teams SDK types in feature service/domain code (import-linter)
- [ ] #3 decisions/platform-transports.md amended with n=2 learnings
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke tests for the Teams surface
- [ ] #2 PR references decisions/platform-transports.md
<!-- DOD:END -->
