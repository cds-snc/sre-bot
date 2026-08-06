# On-call Sync

## Slack Service Identity

- Identity: Dedicated Slack service account for on-call user-group synchronization, with workspace Admin or Owner privileges.
- Credential type: Slack user token (xoxp-) configured as SLACK_USER_TOKEN.
- Scopes: usergroups:write, usergroups:read, users:read.email.
- Owner: Platform team shared ownership; never tied to an individual engineer account.
- Rotation trigger: Rotate immediately on compromise suspicion, ownership changes, or loss of required Admin/Owner role.