---
id: TASK-151
title: Handle gone Slack views and messages gracefully when the bot updates them
status: To Do
assignee: []
created_date: '2026-10-14 19:31'
labels:
  - slack
  - reliability
  - incident
dependencies: []
references:
  - decisions/outbound-clients.md
  - app/contracts/slack/reply.py
  - app/integrations/slack/settings.py
priority: medium
ordinal: 385000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
PROBLEM
The bot often writes to a Slack surface that no longer exists: a modal the user already closed, a view whose trigger expired, or a message that was deleted. Slack then answers with an error such as not_found, and today that surfaces as an unhandled listener error with a traceback, even when the user's action itself succeeded.

Observed 2026-10-14 (legacy incident flow): /sre incident show, change the status, click OK on the update modal before the bot finishes. modules/incident/information_update.py handle_update_field_submission wrote the field, logged the activity and posted the channel message, then called client.views_update(view_id=body["view"]["root_view_id"], ...) on the info modal, which the user had already closed. Slack returned {'ok': False, 'error': 'not_found'}; Bolt logged slack_listener_error at error level with a full traceback. Nothing was lost; only the refresh of a closed modal failed.

WHY IT HAPPENS
- Most Slack writes go straight to the Web client with no error handling: about 19 views_update, 18 views_open, 3 views_push and 1 chat_update calls in app/modules, and 2 views_update calls in app/packages (counted 2026-10-14).
- classify_slack_error (TASK-25.4) has no entry for the stale-surface codes: views.update not_found, views.open/views.push expired_trigger_id and invalid_trigger_id, views.update hash_conflict. The NOT_FOUND catalogue (integrations/slack/settings.py) lists only channel/user/message/subteam codes, so these fall through as unmapped.
- The SlackReplySender contract (contracts/slack/reply.py: post_message, post_ephemeral, open_view, update_view) is the classified path, but nothing says how a caller treats "the surface is gone" as distinct from a real failure.

TARGET
- A write to a surface that is gone is an expected, classified outcome: it never raises out of a listener and never logs at error level with a traceback. It is logged once, at info or warning, with the operation, the view or message id, the callback/action id and the Slack error code (no tokens).
- The caller decides what to do with it per surface. A best-effort refresh of a view the user closed is dropped silently. A stale trigger (expired_trigger_id) on a user-initiated open tells the user to try again. A hash_conflict re-reads or drops, never overwrites newer content.
- The data write and the UI refresh are separate steps, so a failed refresh never looks like a failed action.

SCOPE (to be sized and split by planning)
- Classification: add the stale-surface codes to the Slack catalogue and give them a distinct, documented meaning on OperationResult (e.g. NOT_FOUND with a stable error_code), with tests.
- Contract: decide whether SlackReplySender needs an explicit best-effort variant or documented semantics for update_view/open_view on a gone surface, and whether chat.update joins the contract.
- Package code: the app/packages call sites (incident scribe status-update views) go through the classified path and handle the gone-surface outcome.
- Legacy app/modules: decide per call site between a minimal wrap (the incident information_update path above first, since it is user-visible) and leaving it to the rebuild in TASK-145.8 (incident status/show/update in packages). Bulk rewriting legacy modules is not the goal.
- Listener boundary: integrations/slack/bootstrap.py log_listener_error should record an unhandled gone-surface SlackApiError as a warning without a traceback, as a backstop.

OUT OF SCOPE
Retrying writes to a gone surface; re-opening closed modals; changing Slack retry handlers (TASK-25.4); the incident feature rebuild itself (TASK-145.8).

RELATED
TASK-25.4 (classify_slack_error, done), TASK-26.1.3 (reply Protocol, done), TASK-145.8 (rebuilds incident show/update; should adopt this behaviour), TASK-140.8.2 and TASK-140.9 (scribe views that use views_update with hash).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Stale-surface Slack codes (not_found on views.update, expired_trigger_id, invalid_trigger_id, hash_conflict, message_not_found) are classified to a documented outcome, with unit tests
- [ ] #2 A write to a gone view or message through the classified path never raises out of a listener and logs one warning or info event with operation, surface id, callback or action id and error code
- [ ] #3 The legacy incident information_update flow no longer errors when the info modal was closed before the update finished (reproduction above), and the field update still succeeds
- [ ] #4 The Slack listener error boundary logs an unhandled gone-surface SlackApiError as a warning without a traceback
- [ ] #5 The decision on legacy app/modules call sites (wrap now vs leave to TASK-145.8 and other rebuilds) is recorded on the task, and TASK-145.8 is updated to adopt the behaviour
<!-- AC:END -->
