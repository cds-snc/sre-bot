---
id: TASK-81
title: >-
  Replace the incident-folder LEGACY_FOLDER_DISPLAY_LIMIT shim with real Slack
  pagination or search
status: To Do
assignee: []
created_date: '2026-09-08 18:57'
labels:
  - incident
  - slack
  - product
milestone: m-3
dependencies: []
references:
  - app/modules/incident/incident_folder.py
priority: low
ordinal: 157000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
modules/incident/incident_folder.py::LEGACY_FOLDER_DISPLAY_LIMIT = 25 truncates list_incident_folders() and list_folders_view() to the first 25 alphabetically-sorted folders. It was added as a temporary shim (TASK-25.1.5) once Drive folder-listing pagination was fixed, because folder_item() emits 3 Slack blocks per folder against Slack's 100-block modal limit, and the underlying static_select option lists hit Slack's 100-option limit past ~33 folders. It is a display truncation, not a fix: any incident folder past the 25th alphabetically is invisible in both the "list folders" modal and the product/folder picker.

This task designs and implements the real product fix — pagination (Slack "Load more" / next-page button pattern) or a search/filter input in the modal, replacing the hard truncation. It is a UX/product design task, not a mechanical migration, which is why it is split out from TASK-25.1.6.8.2 (Drive adapter migration) rather than bundled into it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 list_incident_folders() and list_folders_view() no longer silently truncate to LEGACY_FOLDER_DISPLAY_LIMIT; every incident folder is reachable through the Slack UI
- [ ] #2 The chosen UX (pagination or search) is implemented within Slack's 100-block modal and 100-option static_select limits
- [ ] #3 LEGACY_FOLDER_DISPLAY_LIMIT is deleted from incident_folder.py
<!-- AC:END -->
