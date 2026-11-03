---
id: TASK-176
title: Human deferred deletes and closures after the configuration migration
status: To Do
assignee: []
created_date: '2026-10-29T14:15:00Z'
updated_date: '2026-10-29T17:25:00Z'
labels:
  - configuration
  - human
dependencies: []
references:
  - backlog/docs/doc-11
priority: low
ordinal: 460000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human-only steps left by the TASK-111 configuration migration, tracked here instead of on closed tasks (human, 2026-10-29). Each is a console or backlog step the agent cannot take (no AWS or Google credentials in agent sessions; only humans move tasks to Done). The agent asks about each open item at the start of every delivery session and checks it here when the human reports it done. New deferred human deletes found later are added as ACs here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SSM blob parameters sre-bot-config and sre-bot-config-infrastructure deleted in the AWS console (Systems Manager > Parameter Store, ca-central-1); unread since TASK-111.15.1, IAM read removed by TASK-111.15.2 (#1808)
- [ ] #2 Old GCP service-account key deleted in Google Cloud (IAM & Admin > Service accounts > the SRE service account > Keys); its terraform resource was destroyed by TASK-111.15.2, the value sat in terraform state
- [x] #3 doc-14 (production configuration inventory) archived, after the blobs are deleted; kept accurate until then
- [ ] #4 TASK-54 AC #4 checked and TASK-54 set Done, after the blobs are deleted
- [x] #5 TASK-158 archived (closed 2026-10-29 as superseded by TASK-111.10.3)
- [ ] #6 TASK-177 archived (folded into TASK-164 on 2026-10-29)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-29: created from the reminders carried on TASK-111.15.2 (AC #8g, DoD #1) after the human closed TASK-111.15 and 111.15.2. Logged as the last row of doc-11's Work queue.

2026-10-29: AC #5 checked, human reported TASK-158 archived (file in backlog/archive/tasks). AC #3 left open: doc-14 still in backlog/docs and the blobs (AC #1) are not yet deleted.

2026-10-29: AC #3 checked, human archived doc-14 (backlog/archive/docs) before the blob delete; the blob names stay recorded in AC #1.
<!-- SECTION:NOTES:END -->
