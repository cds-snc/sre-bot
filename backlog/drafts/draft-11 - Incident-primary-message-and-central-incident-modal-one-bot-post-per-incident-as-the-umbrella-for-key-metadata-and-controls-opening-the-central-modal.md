---
id: DRAFT-11
title: >-
  Incident primary message and central incident modal: one bot post per incident
  as the umbrella for key metadata and controls, opening the central modal
status: Draft
assignee: []
created_date: '2026-10-07 15:17'
labels:
  - incident
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Direction recorded 2026-10-07 in decisions/incident-management.md ('The incident's primary message and central modal'). The bot's first post in an incident conversation becomes the incident's primary message: its reference is stored on the incident, it carries the key metadata and user controls and is kept current by editing it. Today each resource created at declare time posts its own message and each field change posts '@user has updated ...' (information_update.py, incident_status.py), which scatters the incident across the conversation; those posts fold into the primary message. Its main control opens the central incident modal (today /sre incident show, information_display.py), which gathers the incident's controls, status updates among them (TASK-140), and should match a later Backstage plugin view for a consistent experience across platforms. Specific commands stay as direct ways into the modals reached through the central one. Expansion after the behaviour-preserving TASK-38 rebuild (TASK-38.3 declare, TASK-38.4 show and update); relates to DRAFT-7.
<!-- SECTION:DESCRIPTION:END -->
