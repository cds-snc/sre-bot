---
id: TASK-25.10.3
title: >-
  Move generation parameters out of the OpenAI vendor slice: default model in
  the AI writing capability, output budget and temperature per call
status: Done
assignee:
  - '@me'
created_date: '2026-11-09T13:41:00Z'
updated_date: '2026-11-20T22:06:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.10.2
references:
  - decisions/configuration.md
  - decisions/plugin-architecture.md
  - decisions/plugins.md
  - app/integrations/openai/settings.py
  - app/config/base.toml
  - app/config/production.toml
  - app/config/local.toml
  - app/features/incident/scribe/settings.py
  - app/server/configuration/host_configuration.py
parent_task_id: TASK-25.10
priority: medium
ordinal: 494000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Third slice of TASK-25.10 (contract): TASK-25.10's ACs #7 and #8. The vendor slice keeps only the connection (configuration.md: a vendor slice holds endpoint, credential and transport tuning). Plan at pickup against main after 25.10.2 merges.

TODAY: OpenAISettings carries max_output_tokens (3000, the fallback when a caller passes none), temperature (-1.0, omitted when negative) and the tenant's model (production.toml:45-48 and local.toml:20-23, gpt-5.6-luna). Scribe's catch-up summary passes no budget, so it uses the vendor's 3000. Scribe's draft passes 4000 and comms 2000. scribe declares Requirement('openai.tenant').

TARGET:
- integrations/openai/settings.py: [openai] timeout_seconds and connect_retries (25.10.1); [openai.tenant] base_url only; OPENAI__API_KEY unchanged. max_output_tokens, temperature and tenant.model are deleted.
- capabilities/ai_writing/settings.py (settings-singleton skill; the generator's settings template): [ai_writing] model. production.toml and local.toml move model from [openai.tenant] to [ai_writing] in the same PR. Production sends the same model.
- The Protocol's write (AIWriter) takes max_output_tokens as required and temperature: float | None = None, omitted from the request when None. No caller sets one, so production sends no temperature, as today.
- scribe's catch-up summary gains its own budget, INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS default 3000, in IncidentSummarySettings (the file's existing form), so production sends the same.
- Where an unset model fails, ruled 2026-11-09 (human, OQ6): the model is the organisation's value (configuration.md:33, :87), so base.toml has [ai_writing] model = '' (unset) and production.toml and local.toml set it. Unset, the capability reports unavailable through 25.10.2's no-op implementation and logs ai_writing_model_unset once at build. A required consumer adds Requirement('ai_writing.model') beside 'openai.tenant', resolved through the built slice (host_configuration.py builds it, plugins.md 2026-11-05), so boot names the missing key. Today that is scribe only, while it exists; response and postmortem declare no AI writing requirement (145.9/145.11 ruling, 2026-11-09). comms falls back.
- decisions/configuration.md drops the generation-parameters tolerance (line 119 on main 98da95f7); plugin-architecture.md's Changes gains the date.

Blast radius: production.toml changes the configuration production boots with. A model left in [openai.tenant] fails boot (extra=forbid on the tenant), so the move is atomic in one PR, and one revert restores it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 OpenAISettings holds timeout_seconds, connect_retries, the tenant's base_url and the key only; an [openai] max_output_tokens or temperature key, or a model in [openai.tenant], fails boot; base.toml, production.toml and local.toml match
- [x] #2 capabilities/ai_writing/settings.py reads [ai_writing] model; base.toml leaves it empty (unset: the organisation's value, configuration.md:87); production.toml and local.toml set it to the model they set before; the OpenAI adapter sends it
- [x] #3 AIWriter.write requires max_output_tokens and takes an optional temperature that is omitted from the request when unset; scribe's draft (4000), scribe's catch-up summary (new INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS, 3000) and comms (2000) each pass their own budget, so production sends the same parameters as before
- [x] #4 With the tenant set and the model unset, the capability reports unavailable (the no-op implementation, ai_writing_model_unset logged once at build); scribe declares Requirement('ai_writing.model') beside 'openai.tenant' and aborts boot naming ai_writing.model; comms falls back to the hand-written form
- [x] #5 decisions/configuration.md no longer tolerates generation parameters in the vendor slice; full gates plus make check-import-contracts, check-settings-key-ownership, check-package-shape and check-test-seams pass, with output in notes
- [x] #6 classify_openai_error maps json.JSONDecodeError (an unparseable body) to PERMANENT_ERROR INVALID_RESPONSE, per the outbound-clients.md rule added by TASK-25.6
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (2026-11-19, against origin/main 98da95f7). Paths below are main's; main still has capabilities/text_generation/, TextGenerator, generate(), get_text_generator(), TEXT_GENERATION_UNAVAILABLE. The ai_writing rename (human, #1877 review) is not on main (commit 56091baf is on local branch task-25.10.2-text-generation-capability, in no remote branch). Read text_generation as ai_writing, TextGenerator as AIWriter, generate as write, get_text_generator as get_ai_writer, UnconfiguredTextGenerator as the capability's no-op writer, text_generation_unconfigured as ai_writing_unconfigured. PRECONDITION: the rename merges first as its own mechanical PR (gate item 3); implementation branches from that main: task-25.10.3-ai-writing-generation-parameters.

CALL SITES FOUND
- integrations/openai/settings.py: OpenAITenant.model :25; OpenAISettings docstring :47; max_output_tokens :59; temperature :60-66 (-1.0 omitted); model property :89-92. timeout_seconds :70 and connect_retries :74 stay.
- capabilities/text_generation/adapters/openai.py: payload model :42 (settings.model), budget :43 (max_output_tokens or settings.max_output_tokens), temperature :49-52 (>= 0), docstring :6 and :37-39, build function :149-154 (tenant None -> None). Same signature (max_output_tokens: int | None = None) in api.py:23, adapters/unconfigured.py:15, adapters/in_memory.py:44 (+ GenerationCall :22).
- capabilities/text_generation/providers.py:15-21: lru_cache singleton, logs text_generation_unconfigured when no tenant. plugin.py:12-15 register_requirements returns [] (stays: the capability requires nothing; consumers do).
- Settings wiring: the generator's template app/bin/package_templates/settings.py.tmpl (ConfigurationSlice, toml_table_header=("$table",), env_prefix, get_<table>_settings lru_cache) is the shape; hand-write it, the package exists. Host: server/configuration/host_configuration.py:_validate_slices :220-264 builds feature slices (:243-247); add get_ai_writing_settings() there. Resolution: server/plugins/requirements.py:42-46 SETTINGS_SLICES holds vendors only; :81-82 any other table resolves through built_slices(), a slice not built is unmet (plugins.md 2026-11-05). So no change to requirements.py. Import rules: contract (a) server above capabilities; (m) protects only capabilities.*.plugin, so the host may import capabilities.ai_writing.settings, as it imports features.incident.common.settings.
- scribe: features/incident/scribe/__init__.py:27-33 requirements; service.py:349-355 draft passes 4000 (get_incident_draft_settings().MAX_OUTPUT_TOKENS, settings.py:40); service.py:979-984 summary passes no budget; settings.py:49-65 IncidentSummarySettings (flat BaseSettings with INCIDENT_SUMMARY__ aliases). README.md:398-402 documents [openai] max_output_tokens/temperature (rewrite).
- comms: features/incident/comms/service/draft.py:378 already passes settings.MAX_OUTPUT_TOKENS (2000, INCIDENT_STATUS_UPDATE__MAX_OUTPUT_TOKENS); form.py:190 is_available(). No change. Only these three production callers of generate exist.
- Config: base.toml:123-131 ([openai] keys and comment; plugins key text_generation :282); production.toml:45-48; local.toml:20-23. ci.toml sets incident.scribe=false, no OpenAI.
- Decisions: configuration.md:119 (tolerance bullet under 'Tolerated until closed' :113; the task text says :116); :33 and :87 are the cited rules; Changes entry near :159-160. plugin-architecture.md Changes :164 (default model in the capability slice) and :168; add dated entries.
- AC #6: NOT done on main. integrations/openai/client.py:37-67 classify_openai_error ends 'raise exc' with no json.JSONDecodeError branch (opsgenie's client.py:59-60 has it); adapter response.json() at adapters/openai.py:58 sits inside the try, so an unparseable body re-raises as a bug today. Needs the branch, `import json`, and a test.

STEPS (three ordered commits; each green)
Commit 1, AC #6. client.py: add 'if isinstance(exc, json.JSONDecodeError): return PERMANENT_ERROR, INVALID_RESPONSE, None' before the final raise.
Commit 2, per-call parameters, behaviour-preserving (AC #3). api.py/unconfigured.py/in_memory.py/adapters/openai.py: write(source, *, instructions, max_output_tokens: int, temperature: float | None = None); GenerationCall gains temperature; adapter sends the budget it is given and sets payload['temperature'] only when not None (the openai_generate_* events become openai_write_* from the rename). scribe settings.py: IncidentSummarySettings.MAX_OUTPUT_TOKENS: int = Field(default=3000, alias='INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS'); service.py:984 passes it. Vendor fields still exist, unread. README of the capability and scribe updated.
Commit 3, atomic config move (AC #1, #2, #4, #5). New capabilities/ai_writing/settings.py: AIWritingSettings(ConfigurationSlice), table ai_writing, env_prefix AI_WRITING__, model: str = Field(default='', description=...), get_ai_writing_settings(). Adapter takes AIWritingSettings and OpenAISettings, sends settings.model. providers.py: tenant None -> no-op writer + ai_writing_unconfigured; tenant set and model '' -> no-op writer + ai_writing_model_unset (once: lru_cache build); else OpenAI adapter. openai/settings.py: delete the three fields, the model property, fix docstrings (extra=forbid on both rejects stale keys). host_configuration.py: build get_ai_writing_settings(). scribe __init__.py: add Requirement('ai_writing.model') after 'openai.tenant'. base.toml: drop the two keys and comment, add [ai_writing] model = '' with comment; production.toml and local.toml: remove model from [openai.tenant], add [ai_writing] model = 'gpt-5.6-luna'. decisions: configuration.md remove :119 bullet, dated Changes entry; plugin-architecture.md Changes entry.

TEST MATRIX (TDD, red first; app/tests/..., names per standard)
- integrations/openai/test_openai_client.py: JSONDecodeError -> (PERMANENT_ERROR, INVALID_RESPONSE, None); KeyError still raises.
- unit/capabilities/ai_writing/test_ai_writing_openai_adapter.py (update): sends the given budget as max_completion_tokens; temperature absent when None, present for 0.0 and 0.7; model from the slice; unparseable 200 body -> PERMANENT_ERROR INVALID_RESPONSE (via the adapter) and logs; existing 4xx/5xx/timeout cases kept.
- test_ai_writing_conformance.py: both writers; budget required (TypeError without), temperature recorded by the fake; unavailable writer answers AI_WRITING_UNAVAILABLE.
- test_ai_writing_settings_load.py (new): default '', [ai_writing] model read, AI_WRITING__MODEL env override, unknown key fails.
- test_ai_writing_providers.py: tenant+model -> OpenAI adapter; tenant+model '' -> unavailable and ai_writing_model_unset logged exactly once over repeated calls; no tenant -> unavailable, ai_writing_unconfigured.
- unit/integrations/openai/test_openai_settings_load.py and test_openai_settings_tenant_validate.py: [openai] max_output_tokens, temperature and [openai.tenant] model each fail; tenant base_url validation unchanged.
- unit/infrastructure/configuration/test_configuration_files_openai.py:54 (table keys == {connect_retries, timeout_seconds}); new test_configuration_files_ai_writing.py (base model '', production and local 'gpt-5.6-luna', no model under [openai.tenant]); test_configuration_settings_production_names.py:197-198 drop both rows; EXPECTED_MASKED in test_configuration_slices_secret_typing.py:175 and test_server_configuration_phase_logging_render.py:48 drop openai.max_output_tokens.
- unit/features/incident/scribe/test_incident_scribe_summary_settings.py (3000 default, env override), test_incident_scribe_summary_service.py (summary passes 3000 and a configured value), draft service test (4000 kept); comms fakes (7 test files) take required max_output_tokens and temperature; comms tests assert 2000 unchanged.
- integration/server/test_lifespan_incident_plugins_openai_requirement.py: expected failures gain ('incident.scribe','ai_writing.model'); new: tenant set, model unset, scribe on -> boot aborts naming ai_writing.model; comms reports unavailable (is_available false) with scribe off.
- integration/server/test_server_plugins_configuration_requirements.py:62 FEATURE_SLICE_GETTERS += get_ai_writing_settings (it mirrors the host); production and local files still satisfy every plugin; unset model fails. test_lifespan_vendor_slice_validation.py:357 uses model under [openai.tenant]: now expects boot failure.
- Plugin test: scribe requirements include ai_writing.model; response, postmortem declare none.

TRACEABILITY: #1 commit 3 + openai settings/file tests; #2 commit 3 + settings/adapter tests; #3 commit 2 + scribe/comms tests; #4 commit 3 + providers/lifespan tests; #5 commit 3 + gates; #6 commit 1.

ENV, TERRAFORM, TOOLING
- terraform/ and .github/workflows on main mention only OPENAI__API_KEY (terraform/ssm.tf:27); nothing names OPENAI__MAX_OUTPUT_TOKENS, OPENAI__TEMPERATURE or OPENAI__TENANT__MODEL, and app/.env.example:60 lists only the key. INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS and AI_WRITING__MODEL are optional with defaults, provisioned nowhere. No terraform, IAM, SSM or env-name publication: bin/deploy-checks.zsh pre/post is NOT required; no RETIRED entry (the names were never published). Optional: human runs make env-checks once to see no Codespaces secret holds the three retired names.
- check-settings-key-ownership: new table ai_writing is named once and present in base.toml; AI_WRITING__ prefix satisfies env-naming; INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS is unique among flat aliases. Expected clean; run it.

SIZE GATE: 15 production files (openai settings, client; ai_writing settings new, api, adapters openai/unconfigured/in_memory, providers; scribe settings, service, __init__; host_configuration; 3 toml), about 140 changed production LOC (about +95/-45), plus 4 doc files (2 decisions, 2 READMEs). One subsystem (app tree; no terraform or CI). Rule 1 file count (~10) is exceeded; stated exception: the toml move cannot split (extra=forbid), the signature change touches every writer, and three of the files are one-to-three-line edits. Reviewable as the three commits above; the signature commit is behaviour-preserving (all callers already pass or now pass the same budget). Fallback if the reviewer objects: commit 1 becomes its own PR.

ASSUMPTIONS (verify at implementation)
1. Rename merged first (git ls-tree origin/main app/capabilities/ai_writing). 2. A stale env var with an OPENAI__ prefix and no field is ignored by the slice (grep shows none set; the toml keys fail through extra=forbid, tested). 3. 'model' as a field name raises no pydantic protected-namespace warning (OpenAITenant already uses it). 4. AI_WRITING__ env names pass audit_env_coverage (run bin checks). 5. The ai_writing enablement key (base.toml:282) disables only plugin.py, not the settings slice, which is always built.

BLAST RADIUS AND ROLLBACK
Before: production boots with [openai.tenant] model gpt-5.6-luna, a vendor 3000 budget fallback, no temperature. After: model from [ai_writing] in production.toml; same model, same 3000/4000/2000 budgets, no temperature. Wrong shipping modes: model not moved -> boot fails loudly at the configuration phase (extra=forbid), never silently; model empty -> scribe aborts boot naming ai_writing.model, comms falls back. No env or terraform ordering constraint. One git revert restores code and toml together.

GATES: ruff and targeted tests during TDD. At the end, once each, sequentially: cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)', then cd app && uv run pytest tests --ignore=tests/smoke; plus make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams. Output in notes.

DOWNSTREAM (not edited)
- TASK-145.9.3 and TASK-134 notes carry 'write(source, *, instructions, max_output_tokens=None)': stale against the final (required max_output_tokens, temperature: float | None = None). 145.9.3 comment #1 says rename scribe's summarizer= to text_generator=: should be ai_writer= (AIWriter). 145.9.3 does not mention that its moved summary needs the new INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS budget and its IncidentSummarySettings. TASK-134 ACs #1, #2 and rules still say text-generation capability and app/capabilities/text_generation/ (now ai_writing); its new structured-fill operation must take a required budget too.

OPEN QUESTIONS
1. Rename not on main: wait for it (recommended; plugin-architecture.md Changes 2026-11-19 names text_generation, and mixing a rename with this behaviour change breaks the size gate).
2. File-count exception, or peel AC #6 into its own PR (recommended: one PR, three commits; precedent TASK-25.10.2).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (25.10 review), Q6, where an unset model fails. The ADRs cover it, no gap. configuration.md:33 puts a capability's defaults in its own slice. configuration.md:87 says production.toml holds the deploying organisation's values, while base.toml stays the framework's. The gateway's model name is this organisation's choice, so it stays out of base.toml: base.toml has [text_generation] model = '' (unset), and production.toml and local.toml set it, as AC #7 reads. Spring AI does ship a library default (spring.ai.openai.chat.model = gpt-5-mini, docs.spring.io/spring-ai/reference/api/chat/openai-chat.html). That fits a framework that knows its vendor's catalogue, not a deployment-specific gateway. Unset model: the capability reports unavailable, through 25.10.2's no-op implementation, and logs text_generation_model_unset once at build. Required consumers add Requirement('text_generation.model') beside 'openai.tenant', resolved through the built slice (host_configuration.py, plugins.md 2026-11-05), so boot names the missing key (plugins.md: requirement is the consumer's). Production safety: production.toml and local.toml move the same model in the same PR. A model left under [openai.tenant] fails boot (extra=forbid), so the move cannot half-apply, and one revert restores it. Note: which plugins are 'required consumers' after scribe dissolves is open on TASK-145.9 and TASK-145.11 (2026-11-09).

2026-11-09 (human): OQ6 ruled as recommended: [text_generation] model empty in base.toml, set in production.toml and local.toml; unset means unavailable, plus Requirement('text_generation.model') for required consumers (scribe while it exists). Description and ACs #2 and #4 updated; the 'or the alternative ruled at plan' clause is gone.

2026-11-19 (human, #1877 review of TASK-25.10.2): the text-generation capability is named ai_writing: capabilities/ai_writing, Protocol AIWriter with is_available() and write(source, *, instructions, max_output_tokens=None), get_ai_writer(), error code AI_WRITING_UNAVAILABLE, log events openai_write_*. Its purpose is AI-written text only; any other AI use is a separate capability named for its purpose (plugin-architecture.md). Read 'text generation', TextGenerator and generate in this task as AI writing, AIWriter and write.

2026-11-19 (human): plan approved. OQ1 ruled: wait for the ai_writing rename; it merged as #1878 (34b49494), and main has app/capabilities/ai_writing, so the plan's text_generation names read as ai_writing. OQ2 ruled: one PR, three commits (AC #6; per-call write parameters; atomic config move), with the stated file-count size exception.

2026-11-19 implementation (branch task-25.10.3-ai-writing-generation-parameters from main 34b49494, after #1878). Three commits, each green on its own; the index patches are in tmp/task-25.10.3/c1.patch, c2.patch and c3.patch (gitignored), checked to rebuild the working tree exactly.
- Commit 1 (AC #6): integrations/openai/client.py maps json.JSONDecodeError to PERMANENT_ERROR INVALID_RESPONSE. Tests: client classification, plus an adapter case (a 200 with an HTML body returns INVALID_RESPONSE and logs openai_write_failed).
- Commit 2 (AC #3): write(source, *, instructions, max_output_tokens: int, temperature: float | None = None) on api.py, unconfigured, in_memory (WritingCall records the temperature) and the OpenAI adapter, which sends the given budget and sends a temperature only when one is set. Scribe's IncidentSummarySettings.MAX_OUTPUT_TOKENS (INCIDENT_SUMMARY__MAX_OUTPUT_TOKENS, 3000) is passed by summarize_transcript; the draft (4000) and comms (2000) are unchanged. 8 hand-written test fakes take the new signature. Capability and scribe READMEs updated.
- Commit 3 (ACs #1, #2, #4, #5): new capabilities/ai_writing/settings.py (AIWritingSettings, [ai_writing] model, AI_WRITING__ prefix, default ''). The adapter takes model= and settings=. providers.py: no tenant -> ai_writing_unconfigured; tenant with no model -> ai_writing_model_unset; each case logs once, at the lru_cache build. OpenAISettings loses max_output_tokens, temperature, OpenAITenant.model and the model property. host_configuration builds get_ai_writing_settings(). Scribe adds Requirement('ai_writing.model'). base.toml: [openai] keeps connect_retries and timeout_seconds, and [ai_writing] model = ''. production.toml and local.toml move model = 'gpt-5.6-luna' to [ai_writing]. configuration.md drops the tolerance bullet and gains a Changes entry; plugin-architecture.md gains a Changes entry.
- Tests added or changed: ai_writing settings load (new), configuration files ai_writing (new), providers (model unset: unavailable, logged once), openai settings load/tenant validate (generation keys and tenant model fail boot), lifespan vendor-slice validation (stale tenant model, max_output_tokens and temperature each fail boot), scribe report-ids (an unset model aborts naming ai_writing.model), requirements resolve and the lifespan scribe requirement list (ai_writing.model), production-names, secret typing and phase-logging masked sets (openai.max_output_tokens gone).
- Size: 16 production code/config files (+128/-71) plus 4 docs; approved file-count exception (OQ2).
Gates (from app/, at the end, sequential):
- uv run ruff check . -> All checks passed!
- make check-import-contracts -> Contracts: 15 kept, 0 broken.
- make check-settings-key-ownership -> OK
- make check-package-shape -> OK (3 baselined)
- make check-test-seams -> OK (47 strict, 12 legacy baselined)
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 40 errors in 13 files (the existing baseline: modules/, infrastructure/i18n, features/incident/scheduling; none in touched files)
- uv run pytest tests --ignore=tests/smoke -> 7916 passed
Downstream updated through the CLI: TASK-145.9.3 (note: write signature, ai_writer=, the summary budget moves with summarize); TASK-134 (ACs #1 and #2 name app/capabilities/ai_writing/, AC #1 takes the required budget and optional temperature; note).
For the reviewer: app/.env.example was not inspected here (access denied in this session); no CI drift check covers it. Optional: make env-checks once (retired OpenAI names in Codespaces secrets). deploy-checks pre/post not required.

2026-11-20: closed by the agent: PR #1879 merged 2026-11-19 (3d7264fc); all ACs checked.
<!-- SECTION:NOTES:END -->
