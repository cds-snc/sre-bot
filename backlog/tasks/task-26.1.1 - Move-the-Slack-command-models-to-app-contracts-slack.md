---
id: TASK-26.1.1
title: Move the Slack command models to app/contracts/slack/
status: In Progress
assignee: []
created_date: '2026-09-29 20:19'
updated_date: '2026-09-29 20:43'
labels:
  - plugin-architecture
  - slack
milestone: m-7
dependencies:
  - TASK-25.4
  - TASK-36
references:
  - decisions/platform-entrypoints.md
  - decisions/transport-slack.md
  - decisions/feature-packages.md
parent_task_id: TASK-26.1
priority: high
type: task
ordinal: 290000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack A layer 7a (slice 1 of TASK-26.1). Mechanical move with no behaviour change: ArgumentType, Argument, ArgumentParsingError, CommandPayload and CommandResponse move verbatim from app/integrations/slack/models.py to app/contracts/slack/models.py, and every importer is rewritten in the same PR with no shim. The contract (e) ignore entries this makes unmatched are deleted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/contracts/slack/models.py defines the five types as before; app/integrations/slack/models.py no longer defines them (CommandDefinition and the View/Card/Http families stay)
- [x] #2 Every production and test importer imports the five types from contracts.slack.models; grep finds none importing them from integrations.slack.models or integrations.slack.parser, and no re-export shim exists
- [x] #3 The 6 '-> integrations.slack.models' and 2 '-> integrations.slack.parser' contract (e) ignore entries are deleted and no ignore entry is added
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; the TASK-36 legacy_surface suite is green before and after
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Stack A layer 7a. Mechanical move, no behaviour change, no shim.

Steps:
1. Test first: app/tests/unit/contracts/slack/test_slack_contracts_models_shape.py. The five types import from contracts.slack.models; CommandPayload, CommandResponse and Argument are frozen dataclasses where they are today (keep each type's current mutability exactly as it is: a mechanical move changes no behaviour); an AST scan finds no slack_bolt or slack_sdk runtime import in app/contracts/slack/. Fails before the move.
2. New app/contracts/slack/__init__.py (empty) and app/contracts/slack/models.py holding ArgumentType, Argument, ArgumentParsingError, CommandPayload and CommandResponse verbatim, with their docstrings. Remove `from __future__ import annotations` if it comes along.
3. app/integrations/slack/models.py: delete the five types; CommandDefinition and the View/Card/Http families import what they need from contracts.slack.models.
4. Rewrite importers (production): integrations/slack/parser.py, help.py, provider.py; modules/dev/google.py, modules/dev/platforms/slack.py, modules/sre/platforms/slack.py; packages/access/sync/interactions/slack.py, geolocate/platforms/slack.py, incident_draft/platforms/slack.py, incident_summary/platforms/slack.py, rant/platforms/slack.py, user_rotations/platforms/slack.py. Imports of CommandArgumentParser and the tokenizer stay on integrations.slack.parser.
5. Rewrite importers (tests): tests/integration/modules/sre/test_sre_providers.py; tests/unit/integrations/slack/test_slack_provider.py, test_slack_auto_registration.py, test_slack_help.py, test_slack_parser.py, test_slack_tokenizer.py; tests/unit/packages/{rant/test_rant_slack.py, user_rotations/test_user_rotations_slack.py, access/sync/test_access_sync_slack_status.py, incident_draft/test_incident_draft_slack.py, incident_summary/test_incident_summary_slack.py, geolocate/test_slack.py, geolocate/platforms/test_slack.py}.
6. app/pyproject.toml contract (e): delete the 6 "-> integrations.slack.models" entries (access.sync.interactions.slack, geolocate, incident_draft, incident_summary, rant, user_rotations platforms) and the 2 "-> integrations.slack.parser" entries (access.sync.interactions.slack, geolocate). unmatched_ignore_imports_alerting = "error" makes the deletions mandatory.
7. Verify: rg finds no import of the five names from integrations.slack.models or integrations.slack.parser; lint-imports 8 kept with no new entry; gates; legacy_surface suite green unchanged.

AC map: #1 steps 2-3; #2 steps 4-5 and 7; #3 step 6; #4 step 7.
Size: 14 production files (2 new), about 190 LOC, almost all moved verbatim; every other file is a 1-3 line import change.
Rollback: git revert; no runtime change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented as planned. The five types (ArgumentType, Argument, ArgumentParsingError, CommandPayload, CommandResponse) moved to app/contracts/slack/models.py with their docstrings; app/integrations/slack/models.py keeps CommandDefinition and the View/Card/Http families and imports CommandPayload/CommandResponse from contracts. No shim. None of the five was frozen before; all stay mutable (the shape test pins this).

Importers rewritten: 12 production, 13 test files. CommandArgumentParser imports stay on integrations.slack.parser. Contract (e): 6 '-> integrations.slack.models' and 2 '-> integrations.slack.parser' entries deleted, none added.

Fixes in touched files (fix-bugs-in-touched-files rule):
- CommandPayload.__post_init__: deprecated datetime.utcnow() replaced by datetime.now(UTC). The correlation id is opaque; the epoch value is only correct now (utcnow().timestamp() read naive UTC as local time).
- integrations/slack/help.py _generate_slack_help_text: the translator was called without the locale it receives, so argument descriptions always rendered in en-US. It now forwards the locale; regression test test_generate_help_text_translates_description_in_requested_locale. This is a user-visible fix (fr-FR users now get French argument help).
- packages/geolocate/platforms/slack.py: **result.data -> **(result.data or {}) (mypy arg-type; data is T | None).

Handed to TASK-26.1.3: packages/access/sync/interactions/slack.py:32 and packages/geolocate/platforms/slack.py:14 import SlackPlatformProvider under TYPE_CHECKING from infrastructure.platforms.providers.slack, which no longer exists (mypy import-untyped). Pointing them at integrations.slack.provider would need new contract (e) entries, which AC #3 forbids; 7c re-signs both register_commands onto SlackCommandRegistrar, so the import goes away there.

Evidence (from app/):
- ruff check .: All checks passed!
- lint-imports: 8 kept, 0 broken; (e) 35 ignored imports (43 before)
- mypy: 67 errors repo-wide (69 before); 0 in touched files except the 2 stale TYPE_CHECKING imports above (pre-existing, handed to 7c)
- pytest tests --ignore=tests/smoke: 3534 passed, 6 failed: the known TASK-90 order leaks (test_webhooks_aws_sns x3, directory test_google x3); make test green (2779 + 760 passed)
- legacy_surface: 17 passed before and after
- rg: no import of the five names from integrations.slack.models or integrations.slack.parser
<!-- SECTION:NOTES:END -->
