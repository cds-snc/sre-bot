# On-call Sync

Sync OpsGenie on-call schedules to Slack UserGroups to make contacting on-call folks in Slack easier. This allows folks to use @foo-on-call in Slack instead of trying to figure out who's currently on-call.

## How it works

Synced rotations are defined in [rotations.json](./rotations.json).

Every 5 minutes, SRE Bot will fetch the current on-call individual for each rotation and update the linked Slack UserGroup if necessary. SRE Bot will also update the schedule-level UserGroup to contain all folks on-call for the nested rotations.

## Getting started

1. Figure out your OpsGenie schedule ID and rotation names. To find the schedule ID, navigate to OpsGenie, click "Who is on-call" at the top, click on your schedule, then grab the ID from the URL. The rotation names are copied directly from this schedule view.
2. Update [rotations.json](./rotations.json). **The Slack UserGroup handle and name does not need to already exist. SRE Bot will create the group automatically**.
3. Push up a PR, get it approved, and merge. Your group should be created and live within 10-15 minutes.

## Slack Service Identity

- Identity: Dedicated Slack service account for on-call user-group synchronization, with workspace Admin or Owner privileges.
- Credential type: Slack user token (xoxp-) configured as SLACK_USER_TOKEN.
- Scopes: usergroups:write, usergroups:read, users:read.email.
- Owner: Platform team shared ownership; never tied to an individual engineer account.
- Rotation trigger: Rotate immediately on compromise suspicion, ownership changes, or loss of required Admin/Owner role.