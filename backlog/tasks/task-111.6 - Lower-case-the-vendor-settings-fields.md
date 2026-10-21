---
id: TASK-111.6
title: Lower-case the vendor settings fields
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-21T21:08:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.2
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1753
parent_task_id: TASK-111
type: feature
ordinal: 412000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical: the fields of the integrations/<vendor>/settings.py slices (slack, google_workspace, aws, openai, notify, trello, opsgenie, maxmind, sentinel) become lower snake_case with case_sensitive=False; every reader follows. Environment names do not change. Split in two by vendor group if it exceeds the size gate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The vendor slices declare lower snake_case fields with case_sensitive=False and read the same environment names as before; only aliases equal to the upper-cased field name are dropped, differing aliases stay for 111.9 to 111.11
- [ ] #2 AWSSettings.SERVICE_ROLE_MAP becomes service_role_map, so no settings attribute stays upper case
- [ ] #3 No behaviour change: the existing tests pass with only attribute renames
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #5 Both subtasks TASK-111.6.1 and TASK-111.6.2 are done
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR PLAN. Gate verdict 2026-10-21: whole task is 27 production files (9 settings.py + 18 reader files), ~220 changed production LOC, one subsystem, mechanical. File gate (~10) trips; LOC gate does not. Split into two PRs (human pre-approved), by the downstream rows:
- TASK-111.6.1 Slack + Google Workspace (rows 111.9, 111.10): 9 files, ~110 LOC, in gate. PLANNED (see its plan).
- TASK-111.6.2 AWS, OpenAI, Notify, Trello, OpsGenie, MaxMind, Sentinel (rows 111.11, 111.12): 18 files, ~110 LOC plus the SERVICE_ROLE_MAP rename (one token in ~10 more reader files); file-count exception approved by the human 2026-10-21. Depends on 111.6.1 (both extend the pin file). Planned after 111.6.1 merges.
TASK-111.5.1 is merged (#1768): no Waits-on; the base InfrastructureSettings flip is not a prerequisite because every vendor slice inherits BaseSettings with its own model_config.

Decisions (human, 2026-10-21):
- AWSSettings.SERVICE_ROLE_MAP (derived property, 12 reader files) is renamed service_role_map in 111.6.2. PEP 8 'Method Names and Instance Variables': lowercase with underscores; upper case is for constants (https://peps.python.org/pep-0008/). It is derived, not a field, so it reads no environment name; no alias question. 111.11's description does not replace it, so leaving it would keep the only upper-case attribute on any slice.
- GoogleResourcesConfig flips to case_sensitive=False in 111.6.1 (no impact: nothing sets a lower-case google_resources).
- 111.9/111.10 depend on 111.6.1; 111.11/111.12 on 111.6.2.
- ACs updated to match.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-21T21:03:00Z

---

Proposal (not applied): reword AC #1 to 'the vendor slices declare lower snake_case fields with case_sensitive=False and read the same environment names as before; only aliases equal to the upper-cased field name are dropped; differing aliases stay for 111.9-111.12', and add AC 'both subtasks 111.6.1 and 111.6.2 are done'. Also: 111.9 and 111.10 should depend on 111.6.1, and 111.11 and 111.12 on 111.6.2 (they currently depend on 111.6).

---
<!-- COMMENTS:END -->
