# User rotations

> [!WARNING]
> This feature is under development.

Manage a simple user rotation, with Slack usergroup syncing. This is a minimal alternative to OpsGenie. It is intended for non-critical usecases, like tracking who's responsible for merging dependency updates this week, or tracking who responds to user inquiries this week.

Create one JSON file per rotation in `rotations/`:

```json
{
  "slack-usergroup-handle": "canadalogin-website-atc",
  "slack-usergroup-name": "CanadaLogin Website ATC",
  "members": ["U01234567", "U07654321"],
  "rotation_type": "weekly",
  "weeks_per_shift": 1,
  "rotation_start": "2026-09-14T09:00:00-04:00"
}
```

`members` is a list of Slack user IDs. The first member starts at `rotation_start`, and each member receives `weeks_per_shift` weeks before the next member is selected. `rotation_type` currently supports only `weekly`.

Every five minutes, the on-call sync job reads the current assignment and updates the UserGroup named by `slack-usergroup-handle`. The UserGroup is created automatically when missing. Adding, removing, or reordering members changes subsequent assignments.