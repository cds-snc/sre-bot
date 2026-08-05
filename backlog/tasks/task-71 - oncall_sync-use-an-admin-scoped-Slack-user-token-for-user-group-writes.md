---
id: TASK-71
title: 'oncall_sync: use an admin-scoped Slack user token for user-group writes'
status: To Do
assignee: []
created_date: '2026-08-05 19:10'
labels:
  - oncall-sync
  - slack
  - configuration
dependencies: []
references:
  - decisions/service-accounts.md
  - decisions/platform-transports.md
  - decisions/configuration.md
  - app/packages/oncall_sync/providers.py
  - app/packages/oncall_sync/adapters/slack.py
  - app/integrations/slack/settings.py
priority: high
ordinal: 122000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The `oncall_sync` feature mirrors the current on-call user into a Slack user group (`usergroups.users.update`, and `usergroups.create`/`usergroups.enable` when needed). It currently performs these writes with the shared inbound Slack **bot** token via `SlackClientManager.get_client()` — the same credential the inbound Slack transport uses for replies/commands.

This fails in production with `permission_denied` (previously `missing_scope`): the workspace gates "who can create/edit user groups" to Admins/Owners, and per Slack's model a bot token (`xoxb-`) can never satisfy `usergroups.*` writes under that setting regardless of scopes — only an admin/owner-authorized **user token** (`xoxp-`) works.

Beyond the runtime failure, reusing the shared bot token is an architecture violation: a feature that *mutates* Slack is a "managed system-of-record" (role 3) and must use a separate, least-privilege, **admin-scoped** credential behind its own port — never the shared inbound bot token (`decisions/platform-transports.md`, `decisions/configuration.md`, and the new `decisions/service-accounts.md`).

Outcome: add a dedicated admin-scoped Slack user-token setting and rewire `oncall_sync` to perform its user-group writes with that credential instead of the shared bot token. The `xoxp-` token itself is provisioned out-of-band from a dedicated Slack service identity (see `decisions/service-accounts.md`) and injected into the deployment config/secrets by the operator; that provisioning is not part of this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A dedicated admin-scoped Slack user token setting (e.g. SLACK_ONCALL_ADMIN_TOKEN) exists as a typed field in a settings slice with a cached provider; it has no plaintext default and never appears in logs or repr.
- [ ] #2 get_user_group_sync_target() in app/packages/oncall_sync/providers.py builds SlackUserGroupTarget from a WebClient authenticated with the admin token, not from SlackClientManager.get_client() (the shared inbound bot token).
- [ ] #3 No oncall_sync usergroups.* write (usergroups.users.update / usergroups.create / usergroups.enable) is issued with the shared inbound bot token.
- [ ] #4 When the admin token is missing or empty, the feature surfaces a clear error naming the variable rather than silently falling back to the bot token.
- [ ] #5 Tests cover: the provider wires the admin-scoped client; a usergroup write is issued via the admin client; and the missing-token behavior.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 mypy and ruff clean; pytest for the affected feature/settings passes.
- [ ] #2 Operator step (human-verified, outside this PR): the SLACK_ONCALL_ADMIN_TOKEN secret is provisioned in the AWS deployment config/secrets so the running task can read it.
<!-- DOD:END -->
