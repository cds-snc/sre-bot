---
id: TASK-187
title: >-
  Test-seam guard: tests of features and capabilities fake at Protocol seams;
  legacy pin seams on a shrinking baseline
status: To Do
assignee: []
created_date: '2026-11-06T19:11:00Z'
updated_date: '2026-11-06T19:11:00Z'
labels:
  - testing
  - migration
  - tooling
dependencies: []
priority: high
ordinal: 491000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-11-06 (TASK-36.1.2 OQ6, human-approved). decisions/testing.md requires Protocol fakes at the seam, but every freeze guard reads only the package tree, never app/tests/, so rebuilt code can pick up the legacy habit of patching module internals. Two zones on the freeze-baseline ratchet (decisions/migration.md rule 3, app/bin/freeze_guard.py):
- Strict zone: tests whose subject is under features/ or capabilities/ never patch (monkeypatch.setattr, mock.patch, patch.object) a target inside features/, capabilities/ or modules/; they register a Protocol fake (service registry, dependency_overrides, provider clearing per testing.md). Baseline seeded once from main, ratchets down.
- Legacy pin zone (tests/integration/legacy_surface/): an internal legacy seam is allowed only inside a named fixture in legacy_surface/conftest.py whose docstring names its owning rebuild task; the guard lists those patch targets in a seam baseline that only shrinks, and flags any patch of a modules/ target written inline in a pin test.
Must land before the first legacy surface rebuild (TASK-145.7).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The legacy pin zone allows modules/ patches only inside named legacy_surface/conftest.py fixtures that name their owning task; inline patches in pin tests fail; the seam baseline is seeded once and only shrinks
- [ ] #2 make check-test-seams and a blocking CI step run the guard; baselines are seeded from main at implementation
- [ ] #3 decisions/testing.md Checks lists the guard; the delivery-session skill's gate list and the implementation-planning skill's legacy cutover checklist name it
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass; the guard has unit tests over fixture trees
- [ ] #5 app/bin/check_test_seams.py on freeze_guard.py reports net-new strict-zone patches of features/, capabilities/ or modules/ targets and fails on them, except the provider seams decisions/testing.md sanctions (a provider function replaced for its direct-call consumers); stale baseline entries are reported as safe to remove
<!-- AC:END -->
