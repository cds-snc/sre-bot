---
id: TASK-12
title: >-
  Record the two open policy deltas: dependency-scanning gate ownership and
  hookspec deprecation lifecycle
status: Done
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 17:48'
labels:
  - governance
  - phase-1
milestone: m-1
dependencies:
  - TASK-10
references:
  - decisions/governance.md
  - decisions/dependency-scanning.md
  - decisions/hookspec-deprecation.md
  - decisions/plugins.md
  - 'https://github.com/cds-snc/sre-bot/issues/1266'
priority: low
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ADR-REVIEW-AND-MIGRATION-PLAN.md (now deleted per TASK-11) originally listed two gaps the decisions/ corpus left open. Both remained genuinely unresolved as of this reassessment (2026-07-29), confirmed directly against current CI workflows and app/infrastructure/plugins/specs.py rather than the now-deleted source document:
1. Dependency scanning: Renovate (renovate.json) opens update PRs, but nothing in CI blocks a merge on a known-vulnerable dependency - .github/workflows/docker_vulnerability_scan.yml is workflow_dispatch-only (schedule disabled pending an upstream Trivy limitation, per its own header comment) and .github/workflows/ossf-scorecard.yml is push-to-main/weekly-schedule observability only (forwards to Sentinel, not a PR gate).
2. Hookspec deprecation lifecycle: app/infrastructure/plugins/specs.py's register_slack_commands hookspec already carries an ad hoc '(DEPRECATED: will be removed in favor of register_slack_listeners...)' docstring today, with zero formal policy - no minimum lifetime, no removal checklist - and four live hookimpl implementers (app/modules/dev, app/modules/sre, app/packages/access/sync, app/packages/geolocate).

Resolution: both decision records have been authored directly (decisions/dependency-scanning.md and decisions/hookspec-deprecation.md, both Accepted/applies: target, both naming a migration ticket) rather than left for a future planning pass, since architecture-mode reassessment is where this kind of decision-authoring belongs. decisions/README.md's index has been updated to list both. The two named migration tickets (TASK-66: wire the blocking CI gate; TASK-67: migrate register_slack_commands's implementers and eventually retire it) carry the remaining implementation work - this task's own scope (write the two decision records + index update) is now content-complete; only the PR/merge step remains, which is a human git operation this session does not perform.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Two new records exist in decisions/ (dependency-scanning.md, hookspec-deprecation.md) with status Accepted and honest applies values
- [x] #2 decisions/README.md index lists both new records
- [x] #3 Each record has Checks that a CI step or five-minute review can verify, and names a migration ticket for its target-state gap
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 PR merged following the cascade rule (grep for references, none dangling)
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Both decision records authored directly during a 2026-07-29 architecture-mode reassessment (grounding doc ADR-REVIEW-AND-MIGRATION-PLAN.md was deleted by TASK-11; gaps re-confirmed against live code/CI instead). decisions/dependency-scanning.md: blocking gate for Critical/High findings on direct Python deps via pip-audit, applies: target, migration ticket TASK-66. decisions/hookspec-deprecation.md: milestone-anchored minimum deprecation window + grep-based removal checklist, applies: target, migration ticket TASK-67. decisions/README.md index updated with both rows. Remaining: PR creation and merge (human git operation, DoD#1) and the cascade-rule grep-for-references check (DoD#1's 'grep for references, none dangling' - both new records are net-new so nothing pre-existing references them yet).
<!-- SECTION:NOTES:END -->
