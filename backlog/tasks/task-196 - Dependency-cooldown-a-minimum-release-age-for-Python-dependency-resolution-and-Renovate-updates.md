---
id: TASK-196
title: >-
  Dependency cooldown: a minimum release age for Python dependency resolution
  and Renovate updates
status: To Do
assignee: []
created_date: '2026-11-26T13:18:00Z'
labels:
  - toolchain
  - security
dependencies: []
references:
  - decisions/toolchain.md
  - decisions/dependency-scanning.md
priority: medium
ordinal: 553000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Proposed at TASK-37.2.1 planning (P4, human-approved 2026-11-26). No ADR or repo rule sets a minimum release age today: toolchain.md keeps loose constraints in pyproject.toml and exactness in uv.lock, renovate.json has no minimumReleaseAge, and there is no Dependabot config. Practice: a 7-day cooldown would have blocked 8 of 10 recent supply-chain attacks (https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns); uv supports exclude-newer as a relative duration from 0.9.17, with per-package exemptions through exclude-newer-package (https://docs.astral.sh/uv/reference/settings/); Renovate minimumReleaseAge (https://docs.renovatebot.com/key-concepts/minimum-release-age/).

Scope: [tool.uv] exclude-newer = "7 days" in app/pyproject.toml, with the uv version floor it needs; Renovate minimumReleaseAge for pip and uv managers; the escape hatch for a security fix (a per-package exemption, recorded with its reason); a decisions/toolchain.md amendment with the rule and its sources.

Single PR from origin/main, any lane. app/pyproject.toml is shared with Lane A, so whichever PR merges second rebases and keeps both sides. Interim rule until it lands: a new dependency locks the newest release at least 7 days old (TASK-37.2.1).
Production: none (resolution policy). One git revert.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/pyproject.toml sets a 7-day exclude-newer and uv lock --check passes in CI (check)
- [ ] #2 Renovate holds Python updates for the same minimum release age (review)
- [ ] #3 decisions/toolchain.md records the cooldown, its exemption rule for security fixes and its sources (review)
<!-- AC:END -->
