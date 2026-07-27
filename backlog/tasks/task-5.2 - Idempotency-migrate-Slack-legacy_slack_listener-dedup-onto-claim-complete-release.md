---
id: TASK-5.2
title: Delete the dead legacy_slack_listener Slack idempotency adapter
status: To Do
assignee: []
created_date: '2026-07-24 17:57'
updated_date: '2026-07-27 14:07'
labels:
  - security
  - phase-0
  - reliability
milestone: m-0
dependencies:
  - TASK-5.1
references:
  - decisions/reliability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1349'
parent_task_id: TASK-5
priority: high
ordinal: 75000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Delete the dead legacy_slack_listener Slack idempotency adapter and its helper generate_slack_idempotency_key (app/integrations/slack/utils.py). Both have zero callers anywhere in the repo (confirmed repo-wide, not just app/).

This code was introduced during an earlier attempt to co-locate the Slack vendor Web client and the inbound Slack transport together under app/integrations/slack/ - a concern mix the current decisions explicitly separate: the authenticated Slack Web API client lives in app/integrations/slack/ (no lifecycle), while the inbound transport (Bolt runtime, verification, dispatch, parser, formatter, help, SlackService reply Protocol) lives in app/infrastructure/slack/ per decisions/transport-slack.md. A sync-to-async asyncio.to_thread handler adapter in the vendor-client layer is the wrong shape in both dimensions:

- Its thread-isolation mechanism is obsoleted by the async-Bolt direction (TASK-33): under AsyncApp, handlers are async def and ack-then-work in the same listener, so no thread adapter is needed.
- Redelivery dedup belongs at the transport dispatch boundary in app/infrastructure/slack/ per decisions/reliability.md (every mutating handler is idempotent via an atomic conditional claim keyed on a sender-assigned id), not as a decorator in the vendor-client layer.

Because it is unused, migrating it onto the TASK-5.1 claim/complete/release primitive (the previous framing of this task) would only produce a still-dead artifact in the wrong layer. The correct disposition is deletion.

Deleting utils.py also unblocks TASK-5.4: it is the last app/integrations/ reference to the legacy get_idempotency_service, which TASK-5.4 removes once nothing references it.

The real redelivery-dedup requirement, and the open product question this file used to embody - what stable idempotency_id to use for Slack events that carry no trigger_id, action, or view (payload hashes are prohibited by decisions/reliability.md; that record points to the sender-assigned Slack event_id) - are carried forward to TASK-26 (where the transport dispatch is built). They are neither resolved nor implemented here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/integrations/slack/utils.py is deleted, removing both legacy_slack_listener and generate_slack_idempotency_key; a repo-wide grep for legacy_slack_listener, generate_slack_idempotency_key, and integrations.slack.utils returns no references in app/ code
- [ ] #2 No idempotency behavior is added anywhere in app/integrations/slack/ by this task; the Slack redelivery-dedup requirement and the open idempotency_id question for Slack events lacking trigger_id/action/view are recorded on TASK-26 for the transport dispatch to own
- [ ] #3 Quality gates are green with the file removed (uv run mypy ., uv run ruff check ., uv run pytest tests --ignore=tests/smoke), with no import errors introduced by the deletion
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass and no module imports integrations.slack.utils anywhere in the tree
- [ ] #2 PR references decisions/reliability.md and decisions/transport-slack.md and states that Slack redelivery dedup is deferred to the transport dispatch (TASK-26), not implemented here
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Fresh plan (supersedes the prior migrate-onto-claim/complete/release plan, which is void now that the file is being deleted rather than rewritten).

Preconditions verified at planning time:
- Repo-wide grep confirms legacy_slack_listener and generate_slack_idempotency_key have ZERO callers (searched the whole workspace, excluding .venv/.mypy_cache/__pycache__).
- No test file references integrations.slack.utils, generate_slack_idempotency_key, or legacy_slack_listener, so there is no test to migrate - only, if present, a stray import to remove.

Ordered steps:
1. Re-run the zero-caller check at implementation time (guard against something wiring it up since planning): grep across app/ and tests/ for legacy_slack_listener, generate_slack_idempotency_key, integrations.slack.utils, and integrations/slack/utils (expect no hits outside the file itself).
2. Delete app/integrations/slack/utils.py.
3. Verify app/integrations/slack/__init__.py (and any package re-export) does not import from utils; if it does, remove that import line.
4. Run quality gates from app/: uv run mypy . (venv-excluded), uv run ruff check ., uv run pytest tests --ignore=tests/smoke. Fix any dangling import surfaced by the deletion (expected: none, given zero callers).

Carry-forward (not implemented here, recorded on TASK-26 as part of this task):
- The transport dispatch in app/infrastructure/slack/ must make every mutating Slack handler idempotent via the TASK-5.1 claim/complete/release primitive, keyed feature:intent:idempotency_id with the idempotency_id being the sender-assigned Slack event_id (decisions/reliability.md).
- Open product question for that work: how to handle Slack events that carry no trigger_id, action, or view and therefore no obvious sender-assigned stable id - payload hashes are prohibited by decisions/reliability.md. This is a product decision (reject vs defer vs adopt another Slack-provided id), left explicitly unresolved and owned by TASK-26, not decided here.

Blast radius and rollback: a single-file deletion with zero live callers; trivially reverted by restoring the file. No settings, schema, or terraform changes. Unblocks TASK-5.4 by removing the last integrations/ reference to the legacy get_idempotency_service.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-27 14:07
---
Disambiguation (added 2026-07-27): this task deletes ONLY the dead per-handler idempotency decorator legacy_slack_listener (app/integrations/slack/utils.py, zero callers). It does NOT touch LegacySlackBootstrap (app/integrations/slack/bootstrap.py) - a LIVE sync Bolt App factory used as an async-migration transition helper (provider.py:180 runtime plus ops/dev/sre module callers). Same 'legacy' prefix, unrelated concern. LegacySlackBootstrap is retired by TASK-33 (async Bolt convergence) and relocated by TASK-26, not by any TASK-5.* subtask.
---
<!-- COMMENTS:END -->
