---
id: TASK-25.1
title: >-
  Migrate Google Workspace remainder (Drive/Docs/Calendar/Meet/Sheets/legacy
  Directory consumers) off the execute_google_api_call dispatcher
status: To Do
assignee: []
created_date: '2026-07-31 18:32'
updated_date: '2026-09-02 13:30'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace
parent_task_id: TASK-25
priority: high
ordinal: 111000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator for the Google-remainder slice of TASK-25. Confirmed via repo grep (2026-07-31): ALL 11 files in integrations/google_workspace/ route through the execute_google_api_call dispatcher (google_service.py / google_service_next.py) that decisions/sdk-typing.md retires - not just Directory (TASK-22.4's scope, which only covers the infrastructure/directory/{factory,google}.py Provider path). 16 distinct legacy production consumer files (all under app/modules/ or app/jobs/, none in packages/) call the non-_next integration modules directly: google_directory (permissions/handler.py, provisioning/{users,groups}.py, reports/google_groups.py), google_drive (incident/{incident_document,incident_helper,incident_folder,core,incident_roles}.py, role/role.py, jobs/scheduled_tasks.py, reports/google_groups.py), google_docs (incident/{incident_document,incident_status,incident_conversation,information_update}.py), google_calendar (incident/schedule_retro.py), sheets (incident/incident_folder.py, aws/spending.py, reports/google_groups.py), meet (incident/core.py). gmail.py and gmail_next.py have ZERO production consumers (confirmed via grep) - delete outright, no migration needed. This coordinator is Done only when all its per-surface children are Done; TASK-25's own AC#1/#2 (vendor package exports factories+classify+settings only; no client returns OperationResult) apply to each child.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 make client-usage-matrix / a repo-wide grep of execute_google_api_call and get_google_api_command_parameters shows zero call sites outside google_service.py/google_service_next.py itself (both slated for TASK-23 deletion once this coordinator's children land)
- [ ] #2 Every one of the 16 identified legacy consumer files is migrated behavior-neutrally (existing tests pass with identical outcomes) onto a factory-built, stub-typed Resource (google-api-python-client-stubs, per decisions/sdk-typing.md item 3) + classify_google_error, per its owning child subtask
- [ ] #3 gmail.py and gmail_next.py are deleted (zero production consumers, confirmed)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-01 16:54
---
PLANNING NOTE (2026-09-01, task-planner, while planning TASK-25.1.2): this coordinator's Description undercounted the Docs consumer surface. Repo-wide 'import google_docs' grep found a 5th real production consumer never listed here or in TASK-25.1.2's original text: app/packages/incident_draft/adapters/google_docs.py (a real packages/<feature>/adapters/ file per decisions/feature-packages.md, calls google_docs.get_document/batch_update directly, registered/live via packages/incident_draft/providers.py). TASK-25.1.2's AC#2 has been corrected to name it explicitly (5 consumer files, not 4). Same lesson as prior AWS/Google-remainder passes: always re-grep a prose consumer list before trusting it, even one written from a 'grep-confirmed' claim.
---

created: 2026-09-02 13:30
---
PLANNING NOTE (2026-09-02, task-planner, while planning TASK-25.1.5). Two corrections to this coordinator.

AC#1 IS STALE: it says google_service.py and google_service_next.py are "both slated for TASK-23 deletion once this coordinator's children land". google_service_next.py was indeed deleted by TASK-23.1, but TASK-23 shipped Done with its AC#3 explicitly EXCLUDING the non-_next google_service.py and the get_google_api_command_parameters docstring scraper, deferring both back to TASK-25.1 - so the two tasks pointed at each other and nobody owned the deletion. Filed as the new TASK-25.1.7 (child of this coordinator, dep TASK-25.1.5): pure deletion of google_service.py plus its 482-line test file, plus the baseline prune. This coordinator now has seven children; AC#1's parenthetical should be read as "deleted by TASK-25.1.7", not TASK-23.

CONSUMER COUNT: the Description says 16 legacy consumer files. Drive's share is nine, not the eight listed - packages/incident_draft/adapters/google_docs.py also calls google_drive.create_file_from_template, get_file_by_id and find_files_by_name. That is the same file the 2026-09-01 note already added for Docs; it is a Drive consumer too. Its Drive calls are owned by the new TASK-25.1.5.1 (child of TASK-25.1.5), which was split out of TASK-25.1.5 on size grounds.
---
<!-- COMMENTS:END -->
