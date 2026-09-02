---
id: TASK-25.1.6.2
title: Relocate the pure-domain helpers out of app/integrations/google_workspace
status: To Do
assignee: []
created_date: '2026-09-02 14:59'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/layers.md
  - app/integrations/google_workspace/google_calendar.py
  - app/integrations/google_workspace/google_docs.py
  - app/integrations/google_workspace/google_drive.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 133000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md: clients "contain no business logic". Several functions in app/integrations/google_workspace/ make no outbound call at all and never did - they are pure domain logic that has been sitting in a vendor package. They need a home outside integrations/ regardless of which adapter eventually owns the SDK calls, so this slice is INDEPENDENT of every other TASK-25.1.6 child and can run first.

CONFIRMED INVENTORY (grep, 2026-09-02):
- google_calendar.py: find_first_available_slot, identify_unavailable_users, get_federal_holidays, get_utc_hour. Only get_federal_holidays touches the network (the Canada Holidays API, not a Google API) - the other three are pure computation over an already-fetched freebusy response. TASK-25.1.1's plan explicitly left them alone ("pure helpers with zero google_service dependency - untouched").
- google_docs.py: extract_google_doc_id - a regex over a URL string.
- google_drive.py: the file_type -> mimeType map and its ValueError, and the Drive q-DSL query construction in find_files_by_name / list_folders_in_folder / list_files_in_folder. TASK-25.1.5 deliberately kept these as "what google_drive.py genuinely adds over the SDK". They are still business logic in a vendor package; they move with their consuming adapter rather than in this slice, and are named here only so the inventory is complete. DO NOT move them here.
- google_directory.py: list_groups_with_members, get_members_details, convert_google_groups_members_to_dataframe. Named in TASK-25.1.6's 2026-09-01 comment. Owned by the Directory migration children (TASK-25.1.6.3/.4/.5), NOT this slice.

SCOPE OF THIS SLICE: the four Calendar helpers and extract_google_doc_id only. Move them to a non-integrations home (modules/incident already consumes all of them; a shared utility module or the incident feature's own code, chosen at planning time), update the call sites, and delete them from the vendor modules. Behaviour-neutral: these are pure functions with existing test coverage that moves with them.

WHY IT MATTERS BEYOND TIDINESS: get_federal_holidays makes an HTTP call to a NON-Google API from inside app/integrations/google_workspace/. That is a second outbound vendor hidden inside another vendor's package, invisible to the client-usage matrix and to decisions/outbound-clients.md's per-vendor checks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 google_calendar.py contains only its two Google API functions (get_freebusy, insert_event); find_first_available_slot, identify_unavailable_users, get_federal_holidays and get_utc_hour live outside app/integrations/ with their existing tests relocated alongside them
- [ ] #2 google_docs.py contains only its Google API functions; extract_google_doc_id lives outside app/integrations/ with its tests
- [ ] #3 get_federal_holidays' non-Google outbound HTTP call is no longer made from inside app/integrations/google_workspace/, and its new location is recorded in the task notes
- [ ] #4 All call sites (modules/incident/schedule_retro.py, modules/incident/* Docs-URL consumers, and any others found by grep at implementation time) are updated; existing tests pass unchanged in substance
- [ ] #5 No behaviour change: these are pure functions moved verbatim, with import paths updated only
<!-- AC:END -->
