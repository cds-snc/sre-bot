---
id: TASK-139
title: >-
  Restructure the incident umbrella and scribe READMEs so developers can find
  where new incident work goes
status: Done
assignee: []
created_date: '2026-10-06 15:56'
updated_date: '2026-10-08 15:45'
labels:
  - incident
  - docs
dependencies:
  - TASK-110.2
references:
  - app/packages/incident/scribe/README.md
  - decisions/incident-management.md
priority: medium
type: docs
ordinal: 318000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Colleagues find the scribe subdomain hard to read: the umbrella has no README; the sibling folders documents/, drive/, meet/ and scheduling/ hold adapters the ADR plans to absorb; scribe's naming still says draft/summary (settings INCIDENT_DRAFT__/INCIDENT_SUMMARY__, locale files, the incident_draft:: range prefix); its interfaces are split between core/api.py and scribe/service.py; and the 399-line README puts architecture last. Docs only: no renames, no code moves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/packages/incident/README.md maps every folder of the umbrella with its current role and its target per decisions/incident-management.md, and has a 'where does new work go' table
- [x] #2 scribe/README.md opens with an at-a-glance table per use case (command, service function, interfaces, adapters, settings prefix, locale files, tests), followed by the architecture section with one call-path diagram
- [x] #3 scribe/README.md has an 'Adding a use case' checklist and a Naming note explaining the draft/summary names kept for env-var and catalogue stability
- [x] #4 The existing draft and summarize behaviour detail is kept, under a Reference section; no code, settings or file names change
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Docs only. Two files: app/packages/incident/README.md (new, ~150 lines) and app/packages/incident/scribe/README.md (restructured, ~450 lines). 0 production LOC, 1 subsystem: size gate passes.

Facts verified on main (e6fdc7ca):
- Umbrella folders: core/ (api.py: IncidentTranscriptReader, TranscriptMessage, get_incident_transcript_reader; adapters/slack.py: SlackIncidentTranscriptReader; domain.py), scribe/, documents/ (adapters/google_docs.py, utils.py), drive/ (adapters/google_drive.py), meet/ (adapters/google_meet.py), scheduling/ (availability.py, adapters/google_calendar.py). Consumers of the four siblings are legacy modules/incident/* and jobs/scheduled_tasks.py.
- import-linter contract incident-umbrella (app/pyproject.toml): "documents | drive | meet | scheduling | scribe" above "core", exhaustive.
- Registration on main: hookimpls in scribe/__init__.py, discovered by auto_discover_plugins (server/lifespan.py). The incident.scribe entry point lands with TASK-110.2 (PR #1539, not merged).
- Scribe: settings IncidentDraftSettings (INCIDENT_DRAFT__*), IncidentSummarySettings (INCIDENT_SUMMARY__*); locales incident_draft/incident_summary .en-US/.fr-FR.yml, i18n domain incident_scribe; named-range prefix incident_draft:: (adapters/google_docs.py:55); interfaces IncidentDocumentStore and IncidentReportLinkLookup in scribe/service.py, IncidentTranscriptReader in core/api.py, Summarizer in integrations.openai; 15 test files under app/tests/unit/packages/incident/scribe/.
- decisions/incident-management.md: TASK-140.1 is not merged, so status updates are not in the record.

Steps:
1. Create app/packages/incident/README.md: purpose and ADR link; a folder map with columns folder | current role | consumers today | target per ADR (core -> core; scribe -> scribe/ incident.scribe; documents+drive -> core IncidentReport adapter, TASK-38.2/38.3; meet -> lifecycle video-call adapter; scheduling -> capabilities/calendar, TASK-138). Then target-only units (lifecycle/, retrospective/, common/, features/incident/ move TASK-124.5), each labelled "target, not yet created" and never linked. Then the layer rule (core only through core/api.py; the import-linter contract id) and the "where does new work go" table. (AC1)
2. In scribe/README.md, open with intro plus an at-a-glance table with one row per use case (draft, summarize) and columns command | service function | interfaces | adapters | settings prefix | locale files | tests. (AC2)
3. Move Architecture up under the table: file roles plus one ASCII call-path diagram (platforms/slack.py -> service.py -> core/api.py + IncidentReportLinkLookup + IncidentDocumentStore + Summarizer -> adapters), with registration wording that is true on main. (AC2)
4. Add an "Adding a use case" checklist covering service function + Protocol, adapter + providers.py, settings class, locale files + i18n registration, platforms/slack.py registration, tests named test_incident_scribe_<usecase>_<action>.py, and the README row. Add a Naming note: INCIDENT_DRAFT__/INCIDENT_SUMMARY__, the incident_draft/incident_summary catalogues and incident_draft:: ranges are kept for env-var, catalogue-key and existing-document stability; new use cases name themselves by use case. (AC3)
5. Move the existing draft and summarize sections verbatim under "## Reference", demoting headings one level and fixing the in-page anchors. (AC4)
6. Verify: every backticked path/identifier resolves via rg/ls on the branch; anchors resolve; git diff --stat shows only the two READMEs + task file. Optional: ruff/pytest are unaffected by .md files, so record that instead of running the 70s mypy. (AC4)
7. Follow-up: comment on TASK-140.1 to add the status-update row to the umbrella README's table when the ADR lands.

AC traceability: AC1 -> 1; AC2 -> 2,3; AC3 -> 4; AC4 -> 5,6.
Blast radius: docs only; one git revert restores everything.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Docs-only change: app/packages/incident/README.md (new) and app/packages/incident/scribe/README.md (restructured; former draft/summarize sections moved verbatim under ## Reference, verified by diff modulo heading level). Registration documented as the incident.scribe entry point (TASK-110.2 merged, 5d6aa0f5). Folders the ADR names but that don't exist yet (lifecycle/, retrospective/, common/, features/incident/) are labelled target and not linked. TASK-140.1 not merged: the umbrella's 'where does new work go' table has no status-update row; follow-up recorded on TASK-140.1. Gates: ruff clean; mypy 57 pre-existing errors, 0 in touched files (Markdown only); pytest 3715 passed / 6 failed (known TASK-90 order leaks: aws_sns x3, google directory x3); tests/unit/packages/incident 433 passed.

2026-10-06 (TASK-140.1): decisions/incident-management.md now places external status updates in scribe/ (use case, StatusPagePublisher and its copy-ready adapter), StatusUpdate records and StatusUpdateStore in core/, and the interim find_incident_for_conversation adapter in core/. The status-update row in app/packages/incident/README.md's 'where does new work go' table is tracked on TASK-140.1.
<!-- SECTION:NOTES:END -->
