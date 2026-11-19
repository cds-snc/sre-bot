---
id: TASK-134
title: >-
  Add structured template fill to the text-generation capability and move
  incident_draft's generic answer parsing onto it
status: In Progress
assignee: []
created_date: 2026-10-01 14:05
updated_date: '2026-11-19T21:54:00Z'
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
  - https://github.com/cds-snc/sre-bot/issues/1679
priority: medium
type: task
ordinal: 293000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md ('Text generation is a capability'): producing text from source material and instructions is a capability. Features supply the source text, the instructions or template, and any feature-specific post-processing.

TASK-25.10 creates the capability with the one operation both consumers use today (source text plus instructions gives text). This task adds the second operation: fill a template section by section. The caller passes source text and an ordered list of sections, each a heading with its instructions; the capability returns one answer per section and says whether the model output was cut short.

TODAY. features/incident/scribe/service.py (about 1,030 lines, holding the draft and the summarize use cases) does all of this itself. Part of it is generic and moves: building the request for the model, parsing the JSON object it returns (_parse_answers, _first_json_object, _salvage_pairs, _coerce_answer; service.py:569-678), matching answers to headings, and detecting a truncated response. Part of it is incident-specific and stays in the incident feature: the incident-scribe prompt text, timeline splitting, metadata fields, pull-request link resolution and collapsing, and writing the draft document.

RULES
- The capability's vocabulary stays feature-free (plugin-architecture.md test 3): no incident, timeline, transcript or Slack term appears in app/capabilities/text_generation/.
- The operation returns frozen dataclasses through api.py, never a raw model payload.
- Behaviour-preserving for /sre incident draft: same document content for the same model output, pinned by the existing scribe draft service tests (tests/unit/features/incident/scribe/test_incident_scribe_draft_service.py) and the TASK-36 legacy_surface suite.
- migration.md rule 6: the capability is not widened to reproduce incident conventions.

TASK-145.11 (the report draft moves into incident/postmortem and scribe is deleted) waits for this task, so the draft moves already on the capability operation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The AI writing capability's api.py (app/capabilities/ai_writing/) exposes a structured-fill operation: source text plus ordered sections (heading and instructions) in, with a required max_output_tokens and an optional temperature like AIWriter.write, one answer per section and a truncation flag out, as frozen dataclasses inside OperationResult
- [x] #2 The generic request building, JSON answer parsing, salvage of a cut-off response and heading matching live in the capability with their tests; grep finds no incident, timeline, transcript or Slack vocabulary under app/capabilities/ai_writing/
- [x] #3 The incident scribe service (features/incident/scribe/service.py) calls the capability operation and keeps only incident-specific logic (prompt text, timeline, metadata fields, pull-request links, document writing); its existing tests pass with assertions unchanged
- [x] #4 The capability's in-memory fake covers the new operation and is what the scribe draft service tests use
- [x] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; the TASK-36 legacy_surface suite is green before and after
- [x] #6 comms' first-JSON-object extraction (features/incident/comms/service/prompt.py _first_object) uses the capability's generic parsing; comms keeps its strict rule (any partial or malformed answer is refused) and its tests pass unchanged
- [x] #7 The operation reports an unusable model answer (nothing recovered) as a permanent error AI_WRITING_UNPARSEABLE (registered in contracts/operations/codes.py), passes write errors through classified, and the unavailable writer answers AI_WRITING_UNAVAILABLE; scribe maps the unparseable case to its own DRAFT_UNPARSEABLE with the same message
- [x] #8 AI writing logs carry shape only (lengths, counts, whether a JSON object was found): no source or model text in any capability or scribe draft event; decisions/observability.md states the rule
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (TASK-134), planned 2026-11-19 against main 3d7264fc (TASK-25.10.3 #1879 merged). Read "text generation / TextGenerator / generate" as "AI writing / AIWriter / write" (task notes). Status: APPROVED 2026-11-19 (human), with the rulings in "Decisions" below (one PR, size exception; shape-only AI logging with an observability.md amendment; fields carry instructions; diagnostics stay out of FilledTemplate; list-of-records output is a separate extracting capability).

REFERENCES READ: decisions/plugin-architecture.md (AI writing is a capability; :68 "a template filled section by section" and "extracting" as a separate capability; :90 test 3 feature-free vocabulary; :167 api.py deprecation rule), observability.md (:20 30-day retention; :34 failure logs carry shape, never payload text), configuration.md (:55, :178 bounds are typed settings), feature-packages.md (layout table: capability = api.py + domain.py + service.py + adapters/), outbound-clients.md, migration.md rule 6, doc-11 rows 18a/18b, doc-15, doc-16, TASK-145.11 (AC #9: metadata options become template-profile data), TASK-147.1/147.3/147.7, TASK-165.8, TASK-124.5 (superseded by 145.13). External: OpenAI structured outputs guide https://developers.openai.com/api/docs/guides/structured-outputs ; OpenTelemetry GenAI spans (content not captured by default) https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md ; OWASP Logging Cheat Sheet https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

== 1. CALL SITES FOUND (main 3d7264fc) ==
Capability (app/capabilities/ai_writing/): api.py:19-45 (AIWriter: is_available, write(source,*,instructions,max_output_tokens,temperature=None); get_ai_writer), adapters/openai.py:25-90 (OpenAIWriter.write; _extract_text/_finish_reason/_usage), adapters/in_memory.py:27-57 (InMemoryAIWriter, WritingCall, respond(source, instructions), scripted result), adapters/unconfigured.py:11-22, settings.py:10-27, providers.py:14-25, README.md. No domain.py/service.py yet.
Scribe (app/features/incident/scribe/service.py), generic code that MOVES: _parse_answers :571-596; _coerce_answer :599-615; _first_json_object :649-677; _salvage_pairs :680-697; _match_answer :727-737; _normalize_heading :740-744; the section and metadata-field rendering inside _build_payload :499-512 (_transcript_line :515 stays); truncation detection = was_truncated (:370-371, :422 DraftedDocument.partial).
Scribe call sites that CHANGE: draft_incident_document :298-433 (:350-351 write -> fill_template; :370-398 parsing -> FilledTemplate; :389 raw_preview log dropped; :406 _build_fields; :422 partial), _build_drafts :700-724, _build_fields :747-764, _log_timeline_shape :437-465 (:464 raw_preview dropped), _log_answer_coverage :468-496, import json :28. STAY in scribe: _DRAFT_INSTRUCTIONS :72 (incl. the METADATA FIELDS block :154-163 until 145.11 moves it to profile data), _MODEL_FIELD_LABELS :169, _PR_*/_TIMELINE patterns, _split_run_on_timeline :618, _is_human_only :859, _is_list_heading :865, _transcript_line/_format_time :515-540, PR links :767-856, DraftedDocument, error codes, INCIDENT_DRAFT__MAX_OUTPUT_TOKENS (4000, passed per call). summarize_transcript :949 untouched.
Comms: features/incident/comms/service/prompt.py:99-108 _first_object (only caller parse_drafted_fields :80); docstring :1-9. comms' write at service/draft.py:378 unchanged.
Tests touching moved code: tests/unit/features/incident/scribe/test_incident_scribe_draft_service.py (private _parse_answers import :23, calls :240, :383, :389; local _StubSummarizer :40-65); tests/unit/features/incident/comms/test_incident_comms_status_update_prompt.py:40-95. TASK-36 legacy_surface patches draft/summarize wholesale: unaffected.
Pre-existing vocabulary hits under the capability: api.py:32 and README.md:5 ("a transcript"); README consumers list :40-41 (features.incident.* required by the capability_readme check).

== 2. DECISIONS ==
D1 Operation: AIWriter gains `async fill_template(self, source: str, *, sections: Sequence[TemplateSection], instructions: str, max_output_tokens: int, temperature: float | None = None, fields: Sequence[TemplateField] = ()) -> OperationResult[FilledTemplate]`. Same budget/temperature rules as write. fields = extra answer keys filled in the same JSON object (one model call). (human 2026-11-19, ruling A) fields carry optional instructions now, so TASK-145.11 (AC #9, metadata options as template-profile data) and TASK-165.8 (per-type templates) move per-field rules with the field without widening the public API. Scribe passes labels only this PR (its METADATA FIELDS rules stay in its prompt until 145.11).
D2 Types (domain.py, frozen dataclasses, re-exported by api.py): TemplateSection(heading, instructions=""); TemplateField(label, instructions=""); TemplateAnswer(key, text) ("" when unanswered); FilledTemplate(sections: tuple[TemplateAnswer,...] one per requested section in order, fields: tuple[TemplateAnswer,...] one per requested field in order, truncated: bool). (human, ruling B) No diagnostics (unmatched or blank keys) on the public result: they are logged by the capability as shape. No raw model text in the result. Not Pydantic (internal boundary).
D3 Layering: domain.py = types + pure rules (extract_json_object, parse_answers, coerce, salvage, normalize/match, match report); service.py = fill_template(writer, source, ...): build request, call writer.write, parse, log. The three adapters delegate in one line (OpenAIWriter, InMemoryAIWriter; Unconfigured returns AI_WRITING_UNAVAILABLE). The fake runs the REAL parser over its respond/scripted raw text, so scribe's raw model strings flow through unchanged.
D4 Strict vs salvage (comms, AC #6): api.py exports extract_json_object(raw) -> dict[str, object] | None: first JSON object, fences/prose tolerated, NO salvage, NO coercion. Comms' parse_drafted_fields calls it; its field checks stay in comms. fill_template uses it as its first stage, then coerces and salvages. No strict flag on fill_template. Comms' raw_decode form replaces scribe's brace scanner; equivalence pinned by a characterization corpus written first against the old code. Comms' future bounded feature-specific fields (165.8) use the same extractor: no change needed.
D5 Failures: write error passes through classified; nothing recovered (empty, prose, non-object) = permanent_error AI_WRITING_UNPARSEABLE (new ErrorCode, contracts/operations/codes.py); scribe maps it to DRAFT_UNPARSEABLE (message and code unchanged). Truncated + salvaged = success with truncated=True. Truncated stays parse-derived as today (human, OQ3): finish_reason is not used; write() keeps returning text; a future write() consumer needing the signal widens the result in its own task.
D6 Request text: "Template sections:\n\n### h\nInstructions: ...\n\n..." then "Metadata fields:\n- label" (or "- label: instructions" when a field has them; omitted when no fields) then the caller's source last. Scribe's source stays "Incident channel transcript:\n...". Only model-visible change: "Report sections:" -> "Template sections:" (human, OQ1: accepted; stated in the PR; no caption parameter).
D7 Vendor structured output: NOT used (human, OQ2). Prompt-instructed JSON + parse/salvage; a cut-off response still needs salvage under strict json_schema, and the adapter serves OpenAI-compatible endpoints. Can later be an OpenAIWriter-internal override with no API change.
D8 Logs are shape only (human, OQ4/OQ5; ADR gap closed): AI writing source text and model output are content and never logged as text. Capability events ai_writing_fill_truncated_salvaged and ai_writing_fill_unparseable carry raw_length, object_found, key_count, matched/unmatched/blank counts and the requested headings left blank (caller's own headings, not model output). No preview, so NO log_preview_chars setting (former A3 dropped). Scribe: the timeline-shape and unparseable logs lose raw_preview (raw_length kept); the coverage log reads FilledTemplate (blank sections) and no longer counts metadata labels as unmatched (today it warned on every run). Out of scope, mentioned in the PR only: adapters/openai.py:109 logs a 500-char vendor error body.
D9 Scope held (migration.md rule 6): timeline splitting, list-heading bulleting, PR links, human-only headings, organisation wording stay in scribe (move to postmortem in 145.11).
D10 (human, ruling C) List-of-records output (AI-proposed action items, TASK-147.1/147.3) is "extracting" (plugin-architecture.md:68), a separate capability named for its purpose; fill_template is never widened into list output. Recorded in the ADR amendment (A8).
Domain-model evolution gate: value objects only (never stored, no store/migration/cascade). Matrix: section answered / blank / absent / key drift (case, numbering, punctuation) / duplicate normalised headings (both resolve to the same answer, as today) / non-string values (list, dict, number) / field answered or blank / field with instructions / unmatched key / truncated with and without salvage / no sections and no fields (caller guards; documented). Consumers: scribe now; 145.11 moves the same call into postmortem (sections and fields become template-profile data); 165.8 feeds per-type sections and fields with no API change. TemplateSection vs core's DocumentSection: different layers, core's is incident vocabulary and stays; scribe maps DocumentSection -> TemplateSection.

== 3. SIZE GATE ==
Estimate (verbatim moves counted once): capability domain.py ~150 (~110 moved from scribe, 9 from comms), service.py ~80, api.py +~30, openai.py +~8, in_memory.py +~12, unconfigured.py +~10; contracts/operations/codes.py +1; scribe/service.py ~-150 +~50; comms prompt.py -10 +3. ~9 production files, ~340-380 LOC, two subsystems. (human 2026-11-19) ONE PR, size exception this round, two commits each green: (1) dark capability op (A steps), (2) scribe and comms migration with the old code deleted (B steps). No subtasks created.

== 4. STEPS (TDD: failing tests first per step) ==
A1 contracts/operations/codes.py: register AI_WRITING_UNPARSEABLE beside AI_WRITING_UNAVAILABLE.
A2 capabilities/ai_writing/domain.py (new): TemplateSection, TemplateField, TemplateAnswer, FilledTemplate; extract_json_object (comms raw_decode form); parse_answers(raw) -> (answers | None, truncated) moved from scribe with _coerce_answer, _salvage_pairs; normalize_heading, match_answer moved; a match report (counts, blank requested headings) for logging. Docstrings feature-free.
A4 capabilities/ai_writing/service.py (new): build_request (D6), fill_template(writer, ...) (write -> parse -> FilledTemplate; shape-only logs D8).
A5 api.py: fill_template on AIWriter; re-export the types and extract_json_object (__all__); reword docstring :32.
A6 adapters: OpenAIWriter.fill_template, InMemoryAIWriter.fill_template (records through the underlying write, so WritingCall.source is the composed request), unconfigured (AI_WRITING_UNAVAILABLE).
A7 README.md: document the op, the strict extractor, shape-only logging; reword :5; consumers list unchanged.
A8 decisions/plugin-architecture.md: AIWriter has write() and fill_template(); list-of-records output is a separate extracting capability (D10); Changes line 2026-11-19. decisions/observability.md: rule "AI writing source text and model output are content: logged as shape only (lengths, counts, whether a JSON object was found), never as text; content capture, if ever needed, is opt-in and off by default (OpenTelemetry GenAI conventions)"; Changes line 2026-11-19. ADR edits ride with this PR.
B1 comms/service/prompt.py: delete _first_object; parse_drafted_fields calls api.extract_json_object; keep `import json` only if still used; fix module docstring (drop the TASK-134 sentence).
B2 scribe/service.py: DocumentSection -> TemplateSection, _MODEL_FIELD_LABELS -> TemplateField; draft_incident_document calls summarizer.fill_template(source=..., sections=..., fields=..., instructions=_DRAFT_INSTRUCTIONS, max_output_tokens=settings.MAX_OUTPUT_TOKENS); AI_WRITING_UNPARSEABLE -> DRAFT_UNPARSEABLE_CODE; other errors pass through; _build_drafts/_build_fields/_log_* read FilledTemplate; delete _parse_answers, _coerce_answer, _first_json_object, _salvage_pairs, _match_answer, _normalize_heading, the sections/fields rendering in _build_payload, raw_preview logging, `import json` if unused. Update module docstring and scribe README.
B3 Tests rewired (below); remove dead code found in touched files.

== 5. AC TRACEABILITY ==
AC1 -> A2,A4,A5,A6 -> test_ai_writing_template_fill.py + conformance
AC2 -> A2,A4 -> test_ai_writing_template_parse.py, test_ai_writing_template_headings.py, test_ai_writing_template_request.py, test_ai_writing_vocabulary.py
AC3 -> B2 -> test_incident_scribe_draft_service.py (document assertions unchanged)
AC4 -> A6,B3 -> test_ai_writing_conformance.py + draft service tests on InMemoryAIWriter
AC5 -> gates (section 7)
AC6 -> B1 -> test_incident_comms_status_update_prompt.py unchanged and green
AC7 -> A1,A4,B2 -> error-contract tests in test_ai_writing_template_fill.py and the scribe unparseable test
AC8 -> A4,A8,B2 -> log tests in test_ai_writing_template_fill.py and the scribe draft tests (no model or source text in any event)
Every step maps to an AC (A7, A8: docs for AC1/AC2/AC8).

== 6. TEST MATRIX (fake at the Protocol seam; vendor edge via MockTransport) ==
test_ai_writing_template_parse.py: clean object; prose-wrapped (moved scribe :389); code-fenced; truncated mid-value salvages complete pairs with escapes (moved :240); truncated with nothing salvageable -> None; empty; "not json at all"; top-level array; array value joined by lines; dict value flattened; non-string/blank values dropped; extract_json_object parametrized: complete, fenced+prose, truncated, not-an-object, nested braces in strings; characterization corpus: old comms raw_decode and old scribe scanner agree on every input yielding an object (written first against the old code).
test_ai_writing_template_headings.py: exact; normalised (numbering, case, punctuation); drift-matched; blank answer; duplicate normalised keys; fields matched by label; match report counts.
test_ai_writing_template_request.py: sections block, no-instructions fallback, fields block present/absent, field with instructions, source last and verbatim.
test_ai_writing_template_fill.py: success; truncated=True; unparseable -> PERMANENT_ERROR AI_WRITING_UNPARSEABLE; write RATE_LIMITED with retry_after passes through; unavailable -> AI_WRITING_UNAVAILABLE; instructions/budget/temperature forwarded; salvaged and unparseable events carry shape fields and no source or model text.
test_ai_writing_conformance.py (extended): fill over openai (MockTransport) and in_memory; unavailable pair; missing max_output_tokens -> TypeError; fake enrolment passes.
test_ai_writing_openai_adapter.py: fill sends max_completion_tokens, no temperature unless set.
test_ai_writing_vocabulary.py: no incident/timeline/transcript/Slack under app/capabilities/ai_writing (python files, README outside "## Feature consumers").
Scribe test_incident_scribe_draft_service.py: _StubSummarizer replaced by InMemoryAIWriter (same raw strings); received_* reads become writer.calls[...]; the three direct _parse_answers tests move to the capability parse tests; document/code assertions unchanged; new: unparseable output maps to DRAFT_UNPARSEABLE with no raw text logged; metadata labels do not trigger the coverage warning.
Comms: tests unchanged.
Legacy: TASK-36 legacy_surface before and after.

== 7. VERIFICATION ==
During TDD: cd app && uv run ruff check . and the targeted files only (tests/unit/capabilities/ai_writing, tests/unit/features/incident/scribe, tests/unit/features/incident/comms/test_incident_comms_status_update_prompt.py, tests/integration/legacy_surface). At the end, once each, sequentially: uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (fix what it finds), then uv run pytest tests --ignore=tests/smoke. Also make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams, check-fake-coverage, test-legacy. Report command and output. Not run: tests/smoke.

== 8. ASSUMPTIONS AND DOUBTS (verify) ==
1 Extractor parity: characterization corpus run before deleting the old code.
2 Only the three adapters implement AIWriter in production code: rg "AIWriter" app --glob '!tests'.
3 package-shape accepts domain.py/service.py in a capability: make check-package-shape.
4 import-linter contract (integrations.openai only in adapters/openai.py) unaffected: service.py imports nothing vendor.
5 Scribe tests pin "Metadata fields:" and "### Trigger": D6 keeps both (draft service tests :150-155, :469-472, :565, :921).

== 9. BLAST RADIUS AND ROLLBACK ==
Commit 1 additive, unused. Commit 2: /sre incident draft and comms status-update draft parsing; wrong parity shows as a changed draft document or a comms draft accepted/refused differently; pinned by the draft service, TASK-36 and comms tests. Logs lose raw_preview (no alarm or metric filter reads incident_draft_* events: terraform/ searched). One git revert of the PR restores today's behaviour. No config, terraform or env change; no deploy ordering. Stack M (145.10 -> 145.11) starts after this merges; 145.11 moves the same call into postmortem.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06 (human, TASK-186 review): both incident consumers of answer parsing move onto the capability (plugin-architecture.md, text generation is a capability), not only scribe.

2026-11-19 (human, #1877 review of TASK-25.10.2): the text-generation capability is named ai_writing: capabilities/ai_writing, Protocol AIWriter with is_available() and write(source, *, instructions, max_output_tokens=None), get_ai_writer(), error code AI_WRITING_UNAVAILABLE, log events openai_write_*. Its purpose is AI-written text only; any other AI use is a separate capability named for its purpose (plugin-architecture.md). Read 'text generation', TextGenerator and generate in this task as AI writing, AIWriter and write.

2026-11-19 (TASK-25.10.3): AIWriter.write is now write(source, *, instructions, max_output_tokens: int, temperature: float | None = None): every caller states its own budget, and a temperature is sent only when set. The model is [ai_writing] model (capabilities/ai_writing/settings.py), no longer the OpenAI vendor slice's. The structured-fill operation takes the same parameters (AC #1); scribe's draft keeps INCIDENT_DRAFT__MAX_OUTPUT_TOKENS (4000) as its budget. ACs #1 and #2 reworded to name app/capabilities/ai_writing/ (rename, human, #1877 review); read the description's app/capabilities/text_generation/ as app/capabilities/ai_writing/.

2026-11-19 (human, Q1/Q6 of planning): one PR with a size exception this round (~10 production files, 340-390 LOC, capability + incident feature); two commits: dark capability op, then scribe and comms migration with the old code deleted. TASK-134.1 split not created.

2026-11-19 (human): plan approved with rulings: OQ1 'Template sections:' caption; OQ2 no vendor structured output; OQ3 truncation stays parse-derived; OQ4/OQ5 shape-only AI logging, observability.md amended in this PR, no log_preview_chars setting; A fields carry optional instructions (TemplateField); B no diagnostics on FilledTemplate; C list-of-records output is a separate extracting capability (plugin-architecture.md). AC #8 added.

2026-11-19 implemented on main 3d7264fc (working tree; branch task-134-ai-writing-template-fill), two commits.
Commit 1 (dark): capabilities/ai_writing/domain.py (TemplateSection, TemplateField, TemplateAnswer, FilledTemplate; extract_json_object; parse_answers, coerce_answer, salvage, normalize_heading, match_answer moved from scribe; fill; describe_match for logs), service.py (fill_template over any AIWriter: build_request 'Template sections:' + 'Metadata fields:' + source last; AI_WRITING_UNPARSEABLE; shape-only events ai_writing_fill_unparseable, ai_writing_fill_truncated_salvaged, ai_writing_fill_coverage), api.py (fill_template on AIWriter, __all__ re-exports), the three adapters (openai and in_memory delegate to service; unconfigured answers AI_WRITING_UNAVAILABLE), contracts/operations/codes.py AI_WRITING_UNPARSEABLE, README, decisions/plugin-architecture.md and decisions/observability.md amended with Changes lines.
Commit 2: comms prompt.py parse_drafted_fields on api.extract_json_object (_first_object deleted; strict rule unchanged); scribe service.py drafts with one fill_template call (DocumentSection -> TemplateSection, metadata labels -> TemplateField, AI_WRITING_UNPARSEABLE -> DRAFT_UNPARSEABLE same message); deleted _parse_answers, _coerce_answer, _first_json_object, _salvage_pairs, _match_answer, _normalize_heading, _build_payload, _log_answer_coverage (its job is the capability's ai_writing_fill_coverage, which no longer counts metadata labels as unmatched), raw_preview logging, import json; scribe README updated. Draft tests on InMemoryAIWriter (received_* reads became writer.calls[-1]); the three _parse_answers tests moved to test_ai_writing_template_parse.py; two new scribe tests (no transcript or model text logged; metadata answers raise no coverage warning).
Parity: before any change, the old scribe brace scan + json.loads and the old comms raw_decode were run over a 15-input corpus and agreed on every input; the corpus is pinned in test_ai_writing_template_parse.py. Order: the parity check ran first; the capability tests were written right after the capability code in commit 1 (not strictly test-first); scribe and comms assertions were unchanged throughout.
Model-visible change: request caption 'Report sections:' -> 'Template sections:' (OQ1); worth reading one live /sre incident draft after deploy.
Gates: ruff check . All checks passed; ruff format --check 1279 files already formatted; mypy 40 errors in 13 files, all pre-existing (modules/incident/* etc.), none in touched files (mypy was run a second time only to filter its output for touched paths); pytest tests --ignore=tests/smoke 7971 passed; make check-import-contracts 15 kept 0 broken; check-settings-key-ownership OK; check-package-shape OK (3 baselined); check-test-seams OK; check-fake-coverage OK; make test-legacy 774 passed before the migration and after.
Out of scope, unchanged: adapters/openai.py _error_body logs up to 500 chars of the vendor error body.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-19T21:33:00Z

---

Plan 2026-11-19, proposed AC wording changes (no AC reworded or removed; human decides). (1) AC #2 grep: the capability README must list features.incident.scribe and .comms under '## Feature consumers' (required by the capability_readme package-shape rule), so the grep should cover *.py and the README outside that list; today's hits api.py:32 and README.md:5 ('a transcript') are reworded in this task. (2) AC #3/#4: the three tests that import the private _parse_answers (test_incident_scribe_draft_service.py :240, :383, :389) move to the capability's parse tests with AC #2; every document and error-code assertion in the scribe tests stays unchanged, while the local _StubSummarizer is replaced by InMemoryAIWriter so received_payload/received_instructions/received_max_output_tokens become writer.calls[...] reads (accessor swap, same assertions). (3) Size gate is marginal: proposed split into TASK-134.1 (dark capability op, ~8 files, ~280 LOC) and this task narrowed to the scribe/comms migration (2 files, ~210 LOC); not created, awaiting human approval; doc-11 row 18a says single PR from main, so a size exception with two commits is the alternative.

---
<!-- COMMENTS:END -->
