---
id: TASK-26.2
title: >-
  Move the Slack runtime, parser, formatter, help and transport settings to
  app/server/slack/ with every importer rewritten and no shims
status: To Do
assignee: []
created_date: '2026-09-24 19:58'
labels:
  - plugin-architecture
  - slack
milestone: m-7
dependencies:
  - TASK-26.1
  - TASK-36
references:
  - decisions/platform-entrypoints.md
  - decisions/platform-transports.md
  - decisions/transport-slack.md
parent_task_id: TASK-26
priority: high
type: task
ordinal: 248000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-26. Moves provider.py (Bolt runtime and Socket Mode lifecycle), bootstrap.py, parser.py, formatter.py, help.py, commands.py and the COMMAND_PREFIX transport settings from app/integrations/slack/ and app/infrastructure/slack/ into app/server/slack/. app/integrations/slack/ is left with the client factory, classify_slack_error and settings (TASK-25.4).

Mechanical move with no behaviour change. The one behaviour-neutral refactor carried over from the original scope is the parser tokenizer delegating to shlex.split, kept as its own commit.

Constraint (see TASK-26): legacy modules/ may not import app/server/. Each helper they use today gets the disposition recorded in the TASK-26 plan: contracts/slack for pure data, the handler contract for runtime helpers, or a consumer's adapter. No import-linter ignore entry is added, and no shim is left at an old path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/server/slack/ holds the runtime, verification, dispatch, parser, formatter, help and transport settings; app/infrastructure/slack/ is deleted
- [ ] #2 app/integrations/slack/ contains only the client factory, classify_slack_error and settings; the vendor_package_contract baseline has no Slack entries
- [ ] #3 grep finds no import of a moved module at its old path, no re-export shim, and no new import-linter ignore entry
- [ ] #4 Parser uses shlex.split; parser test suite still green
- [ ] #5 TASK-36 smoke suite green before and after; command names and behaviour unchanged
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
