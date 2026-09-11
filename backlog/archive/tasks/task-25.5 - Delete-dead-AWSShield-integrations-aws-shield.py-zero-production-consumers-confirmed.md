---
id: TASK-25.5
title: >-
  Delete dead AWSShield (integrations/aws/shield.py) - zero production consumers
  confirmed
status: To Do
assignee: []
created_date: '2026-08-05 16:13'
updated_date: '2026-09-11 15:36'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/aws/shield.py
parent_task_id: TASK-25
priority: high
ordinal: 124000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep -rn AWSShield and grep -rn shield app/integrations (case-sensitive, excluding the word inside unrelated identifiers) return zero hits outside version control history
- [ ] #2 app/integrations/aws/shield.py and its dedicated test files (tests/unit/integrations/aws/test_shield.py, test_executor.py, tests/smoke/integrations/aws/test_shield_smoke.py) are deleted
- [ ] #3 no production import of integrations.aws.shield exists anywhere in the repo before deletion (re-verified at implementation, not just at planning time)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-11 15:36
---
Folded into TASK-25.2.6 (2026-09-11, human-directed reassessment of TASK-25.2): the shield.py deletion ships in that slice because integrations/aws/settings.py is imported only by shield.py and its tests and is deleted in the same PR. Keep this task open for human closure once TASK-25.2.6 lands.
---
<!-- COMMENTS:END -->
