---
id: TASK-146.1.2
title: >-
  Move the rotation commands and oncall_sync onto the on-call capability; delete
  user_rotations
status: To Do
assignee: []
created_date: '2026-11-16T17:07:00Z'
updated_date: '2026-11-16T17:08:00Z'
labels:
  - oncall
  - capabilities
dependencies:
  - TASK-146.1.1
parent_task_id: TASK-146.1
priority: medium
type: feature
ordinal: 524000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice C of TASK-146.1 (human, 2026-11-16): the only slice that changes what production runs (the 5-minute oncall_sync job and /sre rotations). Side PR from an up-to-date main after TASK-146.1.1 merges; it does not gate TASK-145.7.9. One git revert restores user_rotations (its files move, not rewritten).

The rotation files move byte-identical into the capability; user_rotations' Slack commands become capabilities/oncall/entrypoints/slack.py; oncall_sync reads self-managed rotations through capabilities.oncall.api; packages/user_rotations, its enablement key and its contract entries are deleted. oncall_sync's own Opsgenie adapter stays until TASK-146.2.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The rotation files move byte-identical to capabilities/oncall/rotations/ and the packaged default directory loads them (test over the installed package path)
- [ ] #2 The /sre rotations commands are served by capabilities/oncall/entrypoints/slack.py, one service call per handler; the legacy surface pins pass with assertions unchanged
- [ ] #3 oncall_sync reads self-managed rotations only through capabilities.oncall.api; a failed lookup skips that usergroup and never shrinks it; the oncall_sync job pins pass with assertions unchanged
- [ ] #4 packages/user_rotations no longer exists, with its [plugins.incident_response] key, its protected-plugins module, its feature-independence entries and the oncall_sync -> user_rotations ignore entries removed
- [ ] #5 decisions/organisation-content.md tolerated path, oncall.md Migration, product-scope.md, feature-packages.md, dependency-injection.md and configuration.md name the capability instead of user_rotations
- [ ] #6 ruff, mypy, lint-imports, check-package-shape, check-settings-key-ownership, check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN v1 (2026-11-16; approved split, human). Side PR on its own branch from an up-to-date main after TASK-146.1.1 merges (doc-11 row 18d.c). Does not gate TASK-145.7.9. Re-ground every path:line at pickup against main.

SIZE: ~160 production LOC added or changed (mostly moved), ~290 deleted, ~11 production files plus doc lines; the deletion and the move are mechanical, the oncall_sync port change is the one behaviour edit. Passes the gate (rule 3 not tripped: the move carries no new behaviour; oncall_sync's port keeps its contract).

STEPS
1. git mv app/packages/user_rotations/rotations/*.json app/capabilities/oncall/rotations/ (byte-identical; one file today, canadalogin-website-atc.json).
2. capabilities/oncall/entrypoints/slack.py: register_commands and the handlers from packages/user_rotations/platforms/slack.py, each handler one service call; the view handler bridges once with asyncio.run at the sync Bolt edge (features/incident/response/entrypoints/slack.py:140); README_URL repointed; register_slack_commands hookimpl in plugin.py. The slack_bolt contract (j) already allows capabilities.**.entrypoints.slack (generator bootstrap).
3. oncall_sync: ports.py defines its own CurrentUserRotation and an async UserRotationsProvider; new packages/oncall_sync/adapters/rotations.py implements it over capabilities.oncall.api (list rotations, on_call_now per rotation; an error result -> that usergroup skipped and logged, never written empty); providers.py, __init__.py (job gate and warmup use api.configured_rotations(), sync), service.py awaits the port. Nothing else in oncall_sync changes; its Opsgenie adapter stays (TASK-146.2).
4. Delete app/packages/user_rotations/ and tests/unit/packages/user_rotations/ (behaviour already covered by TASK-146.1.1 tests and step 2's ported tests).
5. Configuration and contracts: pyproject entry point user_rotations, the pytest env pin key, feature-independence module and its ignores, protected-plugins module and the three oncall_sync -> user_rotations ignores removed; base.toml and ci.toml user_rotations keys removed.
6. Tests rewired with assertions unchanged: legacy surface (conftest, slash-command registration, oncall_sync job run, INVENTORY.md), oncall_sync unit tests, server plugin requirement/enablement/boot/ci-guard lists.
7. Docs: organisation-content.md:15,77 (tolerated path now capabilities/oncall/rotations/), oncall.md Migration and Changes, product-scope.md:22,47, feature-packages.md:13, dependency-injection.md:16, configuration.md:16.

AC TRACEABILITY
#1 step 1 -> test_oncall_rotations_adapter_load.py (packaged default directory case) + wheel listing. #2 step 2 -> test_oncall_entrypoint_slack_rotations_view.py (ported from test_user_rotations_slack.py) + legacy surface pins. #3 step 3 -> tests/unit/packages/oncall_sync/test_oncall_sync_rotations_adapter.py (success, error result -> skipped, no write) + test_oncall_sync_job_run.py unchanged. #4 steps 4-5 -> lint-imports (unmatched ignores error) + enablement boot test. #5 step 7. #6 gates.

BLAST RADIUS AND ROLLBACK
Merging deploys a change to the 5-minute oncall_sync job (writes Slack usergroups) and /sre rotations. Failure mode: a wrong path or a file missing from the wheel yields no rotations, so the self-managed usergroup silently stops updating; guarded by the packaged-directory test and a post-deploy log check (human step: oncall_sync_user_rotation_synced for canadalogin-website-atc within 10 minutes of the deploy). No terraform, env var or secret change. One git revert restores user_rotations.
<!-- SECTION:PLAN:END -->
