---
id: TASK-36.1.2
title: >-
  Pin the legacy incident response interactions (folder metadata, roles, retro,
  archive, reactions, field update) through the Bolt dispatch boundary
status: To Do
assignee: []
created_date: '2026-10-15 20:49'
updated_date: '2026-10-20 23:35'
labels:
  - migration
  - testing
milestone: m-5
dependencies:
  - TASK-36.1.1
references:
  - decisions/testing.md
  - decisions/migration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1739'
parent_task_id: TASK-36.1
priority: medium
ordinal: 396000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second slice of TASK-36.1, reusing the harness from the first slice. Pins the 16 incident_helper.py interactions TASK-145.8 and TASK-145.9 replace: actions add_folder_metadata, view_folder_metadata, delete_folder_metadata, confirm_click, user_select_action, archive_channel, update_incident_field; views view_folder_metadata_modal, add_metadata_view, view_save_incident_roles, view_save_event, update_field_modal; events reaction_added and reaction_removed, each as the floppy-disk matcher and the ack-only fallback. Further split by file (folder, roles and retro, conversation, field update) if the review size needs it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the 16 interaction rows has a dispatch-driven test covering ack, Slack-visible calls and faked side effects, or an explicit not-pinned reason with its owning ticket
- [ ] #2 INVENTORY.md marks these rows pinned by this task and names TASK-145.8 or TASK-145.9 as the rebuild ticket
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->
