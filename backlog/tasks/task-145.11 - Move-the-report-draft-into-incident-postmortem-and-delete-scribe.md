---
id: TASK-145.11
title: Move the report draft into incident/postmortem and delete scribe
status: To Do
assignee: []
created_date: 2026-10-09 16:43
updated_date: '2026-11-06T19:12:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.10
  - TASK-145.9
  - TASK-134
references:
  - https://github.com/cds-snc/sre-bot/issues/1689
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 361000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer D2 of TASK-145. Move: /sre incident draft becomes a postmortem use case and features/incident/scribe is deleted. The draft rules that TASK-145.6.1 moved unchanged into core's Google Docs adapter come back to postmortem in the same layer. The draft output does not change.

THIS SLICE
- scribe/service.py's draft path becomes postmortem/report.py (fill the report for review) with postmortem/prompt.py (section prompts and metadata rules), the draft settings slice, the incident_draft catalogue and the IncidentDocumentStore use through core's IncidentReport. The command registers under incident.postmortem. It calls the text-generation capability's structured fill (TASK-25.10, TASK-134) as scribe does before the move.
- The draft rules leave core/adapters/google_docs.py and move to postmortem (decided 2026-11-05, human; incident-management.md log). core keeps only what two or more subdomains use, and an adapter only translates.
  - postmortem renders the drafted sections into a neutral block body: headings, paragraphs, bullets and links. Rendering covers the model-text-to-lines step (_render_body_lines, _is_subheading, _strip_markdown), PR-reference linking (_PR_REFERENCE_PATTERN), the AI-draft banner text and the " - AI draft" title suffix, and the fix for values the model writes twice (_doubled_value_repairs, _halve_if_doubled).
  - The template facts become a template profile that postmortem passes as data: groups dropped when empty, labels styled as body text, metadata labels, and the guidance restored under named headings (_ENSURED_GUIDANCE). The profile is a postmortem constant until TASK-165's per-type document templates supply it.
  - IncidentReport.write_draft_copy takes the block body and the profile. The Google adapter keeps only Docs mechanics: spans, indexes, named ranges, tables, styles, batchUpdate requests and the Drive copy.
  - _SRE_BOT_GENERATED_TIMELINE stays with the report's timeline (TASK-145.9).
- Tests renamed test_incident_postmortem_report_*; mock patch strings rewritten.
- features/incident/scribe/ is deleted: entry point "incident.scribe" removed from pyproject, any import-linter ignore entry naming scribe renamed to the module that now imports it (never added), the umbrella layers contract lists response | comms | postmortem above core above common, the umbrella README loses the scribe section.
- The report draft is also offered when the status reaches Ready to be Reviewed: response raises the transition through an extension point in common/ and postmortem registers the reaction at startup; no subdomain imports the other. Omit this bullet if it pushes the slice over the size gate and open a follow-up.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /sre incident draft is handled by postmortem/report.py; features/incident/scribe no longer exists and incident.scribe is not an entry point
- [ ] #2 The umbrella layers contract is response | comms | postmortem above core above common with exhaustive = true
- [ ] #3 The import-linter ignore list has not grown; every renamed entry maps to an existing module
- [ ] #4 The draft command's behaviour and output are unchanged (existing tests pass under their new names)
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [ ] #6 core/adapters/google_docs.py holds no draft rules: body rendering, PR linking, banner and title text, the doubled-value fix and the template profile live in postmortem. IncidentReport.write_draft_copy takes a neutral block body and a template profile, and the draft output is unchanged
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09); re-ground at pickup (after TASK-145.10 and TASK-145.9). Behaviour-preserving move plus the draft-rule extraction (step 3a; human 2026-11-05): the transition reaction (report draft offered at Ready to be Reviewed) is behaviour and is NOT in this layer; it becomes a follow-up task when the extension point exists.

## Discovered state
- Draft path after TASK-145.6 and TASK-145.9: scribe/service.py (draft functions, _DRAFT_INSTRUCTIONS at 338, section rendering 488+, about 700 lines), scribe/domain.py draft types, scribe/settings.py IncidentDraftSettings, scribe/providers.py, scribe/entrypoints (draft command, draft responses, render_error, to_slack_mrkdwn), locales incident_draft.*, tests test_incident_scribe_draft_*.py, test_incident_scribe_conversation_draft.py, test_incident_scribe_providers_document_store.py; legacy_surface conftest.py:27-38 and test_slack_command_registration_surface.py:22-24 import scribe service and domain.
- pyproject: entry point incident.scribe; ignore entry scribe.service -> integrations.openai; umbrella layers line.

## Steps
1. `git mv` scribe/service.py -> postmortem/report.py (the prompt constants and section rendering may be split into postmortem/prompt.py in the same move), scribe/domain.py -> merged into postmortem/domain.py, settings class into postmortem/settings.py, providers into postmortem/providers.py, entrypoints draft command and views into postmortem/entrypoints (shared helpers render_error and to_slack_mrkdwn: to core/api if comms or response also use them, else move), locales incident_draft.* into postmortem/locales.
2. Tests renamed test_incident_postmortem_report_*; patch strings rewritten; legacy_surface imports repointed.
3a. Draft rules out of core (human, 2026-11-05). In core/adapters/google_docs.py's section writer (from TASK-145.6.1), move the draft rules to postmortem (postmortem/report.py, or postmortem/draft_rendering.py if report.py grows too large):
  - the body rendering: _render_body_lines, _is_subheading, _strip_markdown, the line kinds;
  - PR-reference linking: _PR_REFERENCE_PATTERN and the link detection behind _pr_link_requests;
  - the banner text and the title suffix;
  - the doubled-value fix: _doubled_value_repairs and _halve_if_doubled, as rules over the drafted values;
  - the template profile as a frozen dataclass: _REMOVE_WHEN_EMPTY_LABELS, _REGULAR_TEXT_LABELS, _METADATA_LABELS, _ENSURED_GUIDANCE.

  The neutral block body (a heading, paragraph, bullet or link run) and the template profile are frozen dataclasses in core/domain.py, exported by core/api.py, because they form the IncidentReport port's signature. IncidentReport.write_draft_copy takes them. The adapter turns blocks into Docs requests and applies the profile to the template's structure, and keeps _RequestBuilder, span, index and table helpers, named ranges, styles, the copy and _SRE_BOT_GENERATED_TIMELINE (TASK-145.9). The moved section-writer tests are split: rendering and profile cases go to test_incident_postmortem_report_*; Docs request cases stay in test_incident_core_google_docs_sections.py with blocks as input. The expected documents do not change.
3. Delete features/incident/scribe/; pyproject: remove the incident.scribe entry point, rename the openai ignore entry to postmortem.report (not added), umbrella layers "response | comms | postmortem" above core above common, exhaustive; umbrella README drops scribe; INVENTORY row for draft repointed.
4. TASK-134 later moves the generic answer parsing from postmortem/report.py to the text-generation capability.

## AC traceability
AC1: steps 1, 3 -> registration test under incident.postmortem; `ls features/incident` has no scribe. AC2: step 3 -> lint-imports with the final layers contract. AC3: step 3 -> ignore list count unchanged. AC4: steps 2, 3a -> draft tests green under new names, unchanged expected documents. AC5: gates. AC6: step 3a -> rg in core/adapters/google_docs.py finds none of the moved names; the adapter test feeds blocks and a profile.

## Test matrix
No new behaviour: the moved suite is the proof; plugin loading test lists response, comms and postmortem.

## Assumptions and doubts
- render_error and to_slack_mrkdwn may be used by response (summarize) too; then they belong in core/api as shared presentation helpers (two consumers), decided at pickup.

## Size
A move of about 1,000 lines, plus the draft-rule extraction: about 250 moved lines and about 60 new (block and profile types, the adapter's block-to-request step); pyproject and README edits. Re-check the size gate at pickup; the human expects it to fit.

## Blast radius and rollback
A missed import breaks the draft command at boot; the lifespan test catches it. Single `git revert`.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 re-ground: the draft move keeps today's behaviour (fills the report document). Under the TASK-147 flag the draft writes proposals to the record instead (TASK-147.7), so the moved draft keeps its fill step behind a seam that slice can redirect.

2026-11-06 (TASK-36.1.2 OQ1/OQ6, human-approved): legacy pin and cutover rules apply: decisions/migration.md recipe steps 2 and 4, decisions/transport-slack.md (legacy ids), decisions/testing.md (seams during the legacy migration); checklist in the implementation-planning skill (Legacy Surfaces). Rebuild/cutover task: pins pass with assertions unchanged; fixtures rewired to the target Protocol fakes and their seam-baseline entries removed; legacy_only_* tests for behaviour it ends deleted; modal-internal ids take the plugin prefix, ids on posted messages stay as legacy aliases; new tests in the strict zone (make check-test-seams, TASK-187).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-05T15:54:00Z

---

2026-11-05 (human, raised in the TASK-145.6.1 review): scope grows. The draft rules that TASK-145.6.1 moved unchanged into core/adapters/google_docs.py return to postmortem in this layer: body rendering, PR-reference linking, banner and title, the doubled-value fix, and the template profile (empty-group drops, body-text labels, metadata labels, restored guidance). write_draft_copy takes a neutral block body and the profile; the adapter keeps only Docs mechanics. Plan step 3a, AC #6. The human expects no size-gate split; re-check at pickup.

---
<!-- COMMENTS:END -->
