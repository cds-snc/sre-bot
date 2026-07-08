---
id: TASK-31
title: >-
  Distributed rate limiting: shared storage, Retry-After, per-principal keys,
  default route coverage
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - security
  - phase-4
milestone: m-4
dependencies:
  - TASK-3
  - TASK-28
references:
  - decisions/security.md
priority: medium
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Rate limiting). After task-3 removed the bypass, the limiter is still in-memory per process (meaningless across 2+ ECS tasks) and covers only 3 of 16 routes; 429s lack Retry-After.

Steps:
1. Configure SlowAPI storage_uri from SecuritySettings: redis:// whenever more than one replica can run; memory:// only for local. Terraform: provision ElastiCache (or note the explicit single-replica risk acceptance if the maintainer declines - record it in this task).
2. Key function: per-principal (JWT sub) when authenticated, per-IP otherwise.
3. Default limits applied app-wide; explicit exemptions only for health endpoints; per-route overrides where needed.
4. 429 responses are RFC 9457 problem details with Retry-After (renders via task-28 helper).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Limiter uses the configured shared backend in deployed environments (integration test against Redis in CI or documented risk acceptance)
- [ ] #2 Two processes sharing the backend enforce one combined limit (test)
- [ ] #3 429 body is problem+json and carries Retry-After (test)
- [ ] #4 All routes are covered by a default limit; health endpoints explicitly exempt
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployment config includes the Redis URL per environment
- [ ] #2 PR references decisions/security.md
<!-- DOD:END -->
