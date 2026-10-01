---
id: TASK-134
title: >-
  Add structured template fill to the text-generation capability and move
  incident_draft's generic answer parsing onto it
status: To Do
assignee: []
created_date: '2026-10-01 14:05'
labels:
  - plugin-architecture
  - capabilities
milestone: m-7
dependencies:
  - TASK-25.10
references:
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - decisions/outbound-clients.md
priority: medium
type: task
ordinal: 293000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Human decision 2026-10-01 (decisions/plugin-architecture.md, "Text generation is a capability"): producing text from source material and instructions is a capability. Features supply the source text, the instructions or template, and any feature-specific post-processing.

TASK-25.10 creates the capability with the one operation both consumers use today (source text plus instructions gives text). This task adds the second operation: fill a template section by section. The caller passes source text and an ordered list of sections, each a heading with its instructions; the capability returns one answer per section and says whether the model output was cut short.

TODAY. packages/incident_draft/service.py (about 750 lines) does all of this itself. Part of it is generic and moves: building the request for the model, parsing the JSON object it returns (_parse_answers, _first_json_object, _salvage_pairs, _coerce_answer), matching answers to headings, and detecting a truncated response. Part of it is incident-specific and stays in the incident feature: the incident-scribe prompt text, timeline splitting, metadata fields, pull-request link resolution and collapsing, and writing the draft document.

RULES
- The capability's vocabulary stays feature-free (plugin-architecture.md test 3): no incident, timeline, transcript or Slack term appears in app/capabilities/text_generation/.
- The operation returns frozen dataclasses through api.py, never a raw model payload.
- Behaviour-preserving for /sre incident draft: same document content for the same model output, pinned by the existing incident_draft service tests and the TASK-36 legacy_surface suite.
- migration.md rule 6: the capability is not widened to reproduce incident conventions.

Independent of the incident reshape task; either order works, and TASK-124.5 waits for both.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The text-generation capability's api.py exposes a structured-fill operation: source text plus ordered sections (heading and instructions) in, one answer per section and a truncation flag out, as frozen dataclasses inside OperationResult
- [ ] #2 The generic request building, JSON answer parsing, salvage of a cut-off response and heading matching live in the capability with their tests; grep finds no incident, timeline, transcript or Slack vocabulary under app/capabilities/text_generation/
- [ ] #3 incident_draft's service calls the capability operation and keeps only incident-specific logic (prompt text, timeline, metadata fields, pull-request links, document writing); its existing tests pass with assertions unchanged
- [ ] #4 The capability's in-memory fake covers the new operation and is what the incident_draft service tests use
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; the TASK-36 legacy_surface suite is green before and after
<!-- AC:END -->
