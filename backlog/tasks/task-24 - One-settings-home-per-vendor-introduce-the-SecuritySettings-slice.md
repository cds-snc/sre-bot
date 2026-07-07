---
id: TASK-24
title: One settings home per vendor; introduce the SecuritySettings slice
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
priority: medium
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/configuration.md (Ownership). Today each vendor has two settings homes - integrations/<vendor>/settings.py (new) and infrastructure/configuration/integrations/<vendor>.py (old) - and app/infrastructure/security/settings.py exists but is wired to nothing; security config is borrowed from ServerSettings.

Steps:
1. Per vendor: keep app/integrations/<vendor>/settings.py as the single home (credentials live with the client); migrate any fields only present in the old file; delete infrastructure/configuration/integrations/<vendor>.py; update consumers.
2. Wire app/infrastructure/security/settings.py as the real SecuritySettings slice (allowed issuers/JWKS, CORS allow-list, rate-limit storage backend, dev-bypass flag) and move those fields off ServerSettings - or delete the file if tasks 2/4 already created the slice elsewhere; one home either way.
3. Namespaced env names (SLACK__..., AWS__...) via env_nested_delimiter; one env var has exactly one owning class.
4. Fail fast: settings validate at provider import during lifespan phase 2; missing credential fails boot naming the variable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/configuration/integrations/ no longer exists; each vendor has exactly one settings class
- [ ] #2 SecuritySettings owns issuers/JWKS, CORS, rate-limit, dev-bypass config and is consumed by the security stack
- [ ] #3 A boot test shows a missing required credential fails with a message naming the env var
- [ ] #4 CI/grep check: no env var read by two BaseSettings classes
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Deployment env files updated for renamed variables (renames listed in PR description)
- [ ] #2 PR references decisions/configuration.md
<!-- DOD:END -->
