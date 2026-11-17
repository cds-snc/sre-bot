---
id: TASK-146.1.2
title: >-
  Move the rotation commands and oncall_sync onto the on-call capability; delete
  user_rotations
status: Done
assignee: []
created_date: '2026-11-16T17:07:00Z'
updated_date: '2026-11-17T20:20:00Z'
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
- [x] #1 The rotation files move byte-identical to capabilities/oncall/adapters/rotation_files/ and the packaged default directory loads them (test over the installed package path)
- [x] #2 The /sre rotations commands are served by capabilities/oncall/entrypoints/slack.py, one service call per handler; the legacy surface pins pass with assertions unchanged
- [x] #3 oncall_sync reads self-managed rotations only through capabilities.oncall.api; a failed lookup skips that usergroup and never shrinks it; the oncall_sync job pins pass with assertions unchanged
- [x] #4 packages/user_rotations no longer exists, with its [plugins.incident_response] key, its protected-plugins module, its feature-independence entries and the oncall_sync -> user_rotations ignore entries removed
- [x] #5 decisions/organisation-content.md tolerated path, oncall.md Migration, product-scope.md, feature-packages.md, dependency-injection.md and configuration.md name the capability instead of user_rotations
- [x] #6 ruff, mypy, lint-imports, check-package-shape, check-settings-key-ownership, check-test-seams and pytest tests --ignore=tests/smoke pass
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-17 (row 18d.c): picked up on task-146.1.2-oncall-consumers from main 3ad7b2b2; TASK-176 asked, unchanged. Plan v1 approved under the TASK-146.1 ruling (2026-11-16); every path re-grounded against main.

Ruling during implementation (human, after a program-scope assessment): make check-package-shape rejects capabilities/oncall/rotations/ (the layout table is closed; locales/ is its only data slot). No ADR names a home for in-code rosters: organisation-content.md makes rosters managed content (TASK-146 re-cut, doc-15 E2) and tolerates in-code files until then; provisioned-content.md's app/content/ is for provisioned kinds and does not exist yet (TASK-168). Chosen: capabilities/oncall/adapters/rotation_files/, beside its only reader (importlib.resources anchors data at the reading module). The loader default and its error-message directory changed, AC #1's path was reworded, and the organisation-content.md tolerated path plus a Changes line were updated. No layout-table or baseline change.

Implemented: the rotation file moved byte-identical (sha256 194c6d0d...); capabilities/oncall/entrypoints/slack.py serves /sre rotations, one get_schedule per view handler, bridged with asyncio.run at the sync Bolt edge; plugin.py has register_slack_commands and still declares no requirement (the host calls register_slack_commands only when the Slack transport runs, which requires [slack.tenant]). In oncall_sync, ports.py owns CurrentUserRotation and an async UserRotationsProvider; adapters/rotations.py (CapabilityUserRotations) uses list_schedules, get_schedule (name) and on_call_now. A failed lookup, nobody on call, or no Slack account leaves that rotation out (oncall_sync_user_rotation_lookup_failed / _skipped), and a failed listing leaves all of them out, so no usergroup is ever emptied. The job gate and warmup use api.configured_rotations(). packages/user_rotations and its tests were deleted; the entry point, base/ci keys, pytest env pin, contract (f) module and ignores, and contract (m) module and ignores were removed. The legacy pins were rewired at the provider seam capabilities.oncall.providers.get_oncall_service (an in-memory OnCallLookup recording handles), assertions unchanged. The 146.1.1 boot test that assumed no packaged rotation files now asserts the provider and the accessor agree on them.

Named changes (migration.md step 4): the /sre rotations help link now points at app/capabilities/oncall/README.md (kind b: oncall.md deletes user_rotations, and the old link would 404); the commands are switched by the oncall key instead of user_rotations (configuration, not user-facing).

Evidence: ruff check . All checks passed; lint-imports Contracts: 14 kept, 0 broken; check-package-shape OK (3 baselined); check-settings-key-ownership OK; check-test-seams OK (47 strict, 12 legacy baselined); mypy Found 40 errors in 13 files = baseline, none in changed code; the full pytest first ran 1 failed / 7463 passed (the 146.1.1 boot test above, fixed); the rerun gave 7464 passed. The wheel lists capabilities/oncall/adapters/rotation_files/canadalogin-website-atc.json.

Human post-deploy: within 10 minutes of the deploy, the oncall_sync_user_rotation_synced log for slack_handle canadalogin-website-atc.
<!-- SECTION:NOTES:END -->
