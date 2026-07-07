---
id: TASK-3
title: Remove the X-Sentinel-Source rate-limiter bypass
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - security
  - phase-0
milestone: m-0
dependencies: []
references:
  - decisions/security.md
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Rate limiting): "No header-based exemptions - trusted internal sources authenticate like everyone else."

Today _sentinel_key_func at app/infrastructure/security/rate_limiter.py:19-23 returns None (= exempt from all limits) on bare presence of an X-Sentinel-Source header, and get_limiter() (lines 32-35) builds the Limiter with that key_func (SEC-2, OWASP API4:2023). Anyone can set that header.

Steps:
1. Delete the header-presence exemption from _sentinel_key_func in app/infrastructure/security/rate_limiter.py.
2. If the internal source that motivated the exemption still needs elevated limits, it must authenticate (JWT service principal) and receive a per-principal limit - do NOT re-add any header check.
3. Keep scope minimal: shared Redis storage, Retry-After, and route coverage are task-31 (Phase 4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep -rn "X-Sentinel-Source" app/ returns zero hits
- [ ] #2 A request carrying arbitrary X-* headers is rate limited exactly like one without them (test exists)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass
- [ ] #2 PR references SEC-2 and decisions/security.md
<!-- DOD:END -->
