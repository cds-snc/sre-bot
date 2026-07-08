---
id: TASK-14
title: Make the Dockerfile and manifest honor the uv lockfile
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - toolchain
  - phase-2
milestone: m-2
dependencies:
  - TASK-13
references:
  - decisions/toolchain.md
  - 'https://github.com/cds-snc/sre-bot/issues/1268'
priority: high
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/toolchain.md (Packaging). Today the Dockerfile copies uv.lock optionally (glob uv.lock*) then runs uv pip install --system -e . - discarding every property the lockfile buys. Runtime deps are ==-pinned in [project] (exactness belongs in uv.lock), awscli ships as a runtime dep, dev deps sit in [project.optional-dependencies], and stale hatch/Makefile references to the deleted core package linger.

Steps:
1. Rewrite the Dockerfile multi-stage: builder stage runs uv sync --locked --no-dev (non-editable); runtime stage copies the venv/site-packages. COPY uv.lock without a glob so a missing lock fails the build.
2. In app/pyproject.toml: loosen [project] dependencies to ranges (exactness lives in uv.lock); move dev tools to PEP 735 [dependency-groups]; remove awscli from runtime deps; delete stale core references in [tool.hatch.build.targets.wheel] and the Makefile coverage targets.
3. Add uv lock --check and uv sync --locked steps to CI.
4. [project] carries name, static version, description, readme, license (SPDX), requires-python, dependencies, [project.urls]; runtime revision identity is GIT_SHA env.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dockerfile is multi-stage, installs with uv sync --locked --no-dev, and fails to build without uv.lock
- [ ] #2 No == pins remain in [project] dependencies; dev deps live in [dependency-groups]; awscli is gone from runtime deps
- [ ] #3 CI fails when uv.lock is out of date (uv lock --check step)
- [ ] #4 grep -rn "core" app/pyproject.toml app/Makefile shows no references to the deleted package
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Image builds and the container boots (smoke: readiness endpoint responds)
- [ ] #2 PR references decisions/toolchain.md
<!-- DOD:END -->
