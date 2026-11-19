---
id: TASK-25.10.2
title: >-
  Create the AI writing capability with make new-package and repoint scribe and
  comms onto its api.py
status: In Progress
assignee: []
created_date: '2026-11-09T13:41:00Z'
updated_date: '2026-11-19T17:34:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.10.1
  - TASK-114.4
  - TASK-114.6
references:
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - decisions/plugins.md
  - decisions/cloud-portability.md
  - decisions/incident-management.md
  - decisions/testing.md
  - app/integrations/openai/summarizer.py
  - app/features/incident/comms/interfaces.py
  - app/features/incident/comms/providers.py
  - app/features/incident/comms/service/form.py
  - app/features/incident/scribe/service.py
parent_task_id: TASK-25.10
priority: medium
ordinal: 493000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
RENAMED 2026-11-19 (human, #1877 review): the capability is ai_writing (capabilities/ai_writing, Protocol AIWriter with is_available() and write(), get_ai_writer(), AI_WRITING_UNAVAILABLE, log events openai_write_*). The text below keeps the plan-time names (text_generation, TextGenerator, generate).

Second slice of TASK-25.10 (migrate). The Summarizer port and its OpenAI implementation leave the vendor package for app/capabilities/text_generation/, the first package under app/capabilities/, and both incident consumers import only its api.py. Behaviour is unchanged; plan it at pickup against main after 25.10.1 merges.

CREATE: make new-package ARGS='capability text_generation --classification generic --consumer features.incident.scribe --consumer features.incident.comms --adapters' (no --settings: the slice arrives in 25.10.3). Dry run on a scratch copy (2026-11-09): the generator adds capabilities to root_packages, the wheel packages and every contract that lists features, the entry point text_generation = capabilities.text_generation and the key "text_generation" = true in [plugins.incident_response]. With TASK-114.4 a capability gets only __init__.py, README.md and api.py by default and --adapters adds adapters/__init__.py; nothing generated is deleted by hand.

PROPOSED SHAPE (review at the 25.10 plan checkpoint, 2026-11-09):
- api.py: TextGenerator Protocol (named for its role; feature-free): is_available() -> bool, and async generate(source, *, instructions, max_output_tokens=None) -> OperationResult[str], with instructions required (every caller passes its own today; the vendor's incident-worded default is deleted). get_text_generator() provider (cached): the OpenAI adapter when [openai.tenant] is set, else the unconfigured one, which answers is_available() False and TEXT_GENERATION_UNAVAILABLE on generate (plugin-architecture.md: unavailable, never an error).
- adapters/openai.py: OpenAISummarizer and its response helpers, moved and renamed OpenAITextGenerator; the only importer of integrations.openai. adapters/unconfigured.py: the unavailable implementation (today's comms UnavailableTextGenerator, moved). adapters/in_memory.py: the fake, explicitly subclassing the Protocol, enrolled in a conformance suite (cloud-portability.md rule 4, make check-fake-coverage).
- integrations/openai/summarizer.py deleted with its exports; module: and operation-result: summarizer.py baseline entries deleted.
- scribe: service.py imports the capability's api.py only; the import-linter ignore 'features.incident.scribe.service -> integrations.openai' is deleted.
- comms (the TextGenerator question noted on TASK-25.10): comms' local TextGenerator Protocol (interfaces.py) is deleted; comms services type against the capability's Protocol, as incident-management.md:128 lists the local one as a divergence until 25.10 and feature-packages.md lets a package import capabilities' api.py. adapters/text_generation.py is deleted: the capability now reports unavailable itself. providers.get_status_update_text_generator() returns api.get_text_generator(). text_generation_available() is deleted from providers.py: service/form.py takes the generator (default from the provider) and reads is_available(). This ends its providers.py seam exemption under TASK-187: tests pass the capability's in-memory fake, or patch the provider getter, which stays sanctioned until the registry.
- Declared capability order (plugins.md): not exercised. This capability declares no hookspec and imports no other capability. plugins.md records that the first capability to need an order (a hookspec or a lower capability import) declares it, and where.
- ADRs in the same PR: incident-management.md (divergence line 128 closed), outbound-clients.md (OpenAI tolerance removed), feature-packages.md (lines 14 and 118: scribe's openai import gone), product-scope.md (text_generation in the Incident response row), plugins.md (order note).

SIZE: about 8 new files, most generated or moved, about 12 modified and 3 deleted. Roughly 350 production LOC, of which about 180 are the moved adapter. Over the ~10-file guide: a size exception is proposed (one concept, a move plus generator boilerplate, behaviour unchanged), as granted to TASK-186. The alternative is to split scribe and comms into two PRs, which would leave the vendor summarizer and the capability alive side by side between them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 api.py holds the AIWriter Protocol (is_available, write with required instructions and optional max_output_tokens) and get_ai_writer(); with no [openai.tenant] entry it returns an implementation that reports unavailable (is_available False, AI_WRITING_UNAVAILABLE) without building a client; adapters/openai.py is the only module in the capability importing integrations.openai, and import-linter contract (o) holds that integrations.openai is imported only by capabilities.ai_writing.adapters.openai, besides server
- [x] #2 An in-memory fake in adapters/in_memory.py explicitly subclasses the Protocol and is exercised by a conformance suite shared with the OpenAI adapter; make check-fake-coverage passes
- [x] #3 integrations/openai/ holds only __init__.py, client.py and settings.py; its summarizer entries are gone from bin/baselines/vendor_package_contract.txt; make check-vendor-package-contract passes
- [x] #4 features/incident/scribe/service.py imports the capability's api.py only and the 'features.incident.scribe.service -> integrations.openai' ignore is deleted; scribe's draft and summarize tests pass unchanged in assertions
- [x] #5 comms' local TextGenerator Protocol and adapters/text_generation.py are deleted; comms services depend on the capability's AIWriter; text_generation_available is gone and the form reads is_available() from the injected AI writer; the form has no AI section when AI writing is unavailable and save and approve still work (existing tests, now on the in-memory fake)
- [x] #6 Tests under tests/unit/capabilities/ai_writing/ pass make check-test-seams with no strict baseline entry (the adapter is faked at the vendor-client edge); no ai_writing or summarizer entry is added to bin/baselines/test_seams_strict.txt, and its stale header comment about text_generation_available is reworded
- [x] #7 decisions/incident-management.md, outbound-clients.md, feature-packages.md, product-scope.md and plugins.md are updated with dated Changes lines; full gates plus make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and check-fake-coverage pass, with output in notes
- [x] #8 app/capabilities/ai_writing/ is created with make new-package (classification generic, consumers features.incident.scribe and features.incident.comms, with --adapters and no other optional entry; TASK-114.4, TASK-114.6), so no generated file is moved, edited away or deleted by hand; its entry point and contract (m) protected module are capabilities.ai_writing.plugin and its [plugins.incident_response] key exists; its README names the feature consumers, states the vocabulary is feature-free, and states the key switches only the plugin module; make check-package-shape passes with no new baseline entry
- [x] #9 decisions/plugin-architecture.md states the platform/extension split (capabilities and contracts/ are the platform this project maintains, features the extension surface, in-tree or in an adopter's own distribution), that a capability is always present (its provider always resolves; one whose backing is optional is a no-op answering is_available() false, and a consumer offering an optional action asks is_available() first; AI writing answers AI_WRITING_UNAVAILABLE), and that a capability's api.py is public plugin API beside contracts/, a breaking change following hookspec-deprecation.md from the first release an adopter consumes; plugins.md states that a capability's enablement key switches only its plugin module (surfaces, requirements, credential checks), never its api.py, and availability comes from configuration; product-scope.md states an adopter adds behaviour as feature plugins over the capabilities and contracts, and a new vendor for a capability comes as an adapter inside it; plugin-architecture.md names the capability ai_writing for its purpose (a language model writing text from a source and instructions) and states that any other AI use is a separate capability named for its purpose, sharing the vendor integration; dated Changes lines
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
BASE: main 6f9b7645 plus unmerged d2e81c54 (TASK-114.5, tooling only: app/bin guards read roots/public_api/adapters_dir from bin/package_layout.py; check_fake_coverage's public_api scan reads capabilities/*/api.py). Plan against that tree; if 114.5 merges first nothing changes, if this lands first rebase onto it. TASK-114.4 is merged (#1847). Note: app/capabilities/ already exists (oncall, TASK-146.1.1), so this is not the first package under it; it is the first capability whose api.py Protocol is consumed by features that have an adapter-subclass fake in check_fake_coverage's scan, and the first to need the plugin-module split below.

GENERATOR DRY RUN (scratch copy of app/, 2026-11-19, command as in the task, no --settings): emits exactly
 1. app/capabilities/text_generation/__init__.py (15 lines: plugin_init template, a @hookimpl register_requirements returning [])
 2. app/capabilities/text_generation/README.md (12 lines; Classification generic; Feature consumers scribe, comms; purpose line left as a <placeholder>)
 3. app/capabilities/text_generation/api.py (4 lines, docstring only)
 4. app/capabilities/text_generation/adapters/__init__.py (1 line)
 5. app/pyproject.toml: [project.entry-points.sre_bot] text_generation = "capabilities.text_generation" (after oncall, ~line 50) and the module "capabilities.text_generation" appended to contract (m) protected_modules (~line 456)
 6. app/config/base.toml: text_generation = true under [plugins.incident_response] (after oncall = true, ~line 279)
 No other file. Root packages, wheel packages and the feature-listing contracts already contain capabilities (oncall), so they are untouched. check_package_shape passes on the output with the existing baseline (3 baselined violations unchanged). No config/ci.toml edit (no requirement declared). Next-step hint printed: add the product-scope.md row text; run uv sync.
 FINDING: a lint-imports run on the scratch copy with a feature importing capabilities.text_generation.api FAILS contract (m): 'features.incident.scribe.service -> capabilities.text_generation.api' is illegal because the entry point names the package, which protects every submodule. oncall avoids it with entry point capabilities.oncall.plugin. The generator has no plugin.py option. See Decision D1.

DECISIONS TAKEN IN THIS PLAN (human may overrule at review)
 D1 (deviation from the generated output, flagged): the plugin module is capabilities.text_generation.plugin, not the package. Moves the generated hookimpl from __init__.py into plugin.py, __init__.py becomes docstring-only, entry point and protected_modules value change to capabilities.text_generation.plugin (plugins.md 2026-11-04 allows this when settings are read before plugin loading; TASK-25.10.3 adds settings.py, so it is needed there anyway). Preferred route: a prerequisite tooling task adds a --plugin option to new_package/package_layout.toml (plugin.py is already an optional layout entry) so nothing is hand-edited; fallback: hand-edit these three spots in this PR and record it. See open question Q1.
 D2 api.py holds TextGenerator (Protocol, not runtime_checkable) and get_text_generator(), which lazily imports providers (same shape as capabilities/oncall/api.py:60-66, cycle: adapters import api). providers.py holds @lru_cache get_text_generator_singleton() (OpenAI adapter when get_openai_settings().tenant is set, else Unconfigured; logs text_generation_unconfigured once at build). providers.py is the sanctioned test seam under check_test_seams (a public def in providers.py); api.py is not, so consumer tests must patch capabilities.text_generation.providers.get_text_generator_singleton, never a consumer's imported name.
 D3 Protocol: is_available() -> bool; async generate(source: str, *, instructions: str, max_output_tokens: int | None = None) -> OperationResult[str]. The vendor's incident-worded _DEFAULT_INSTRUCTIONS is deleted (verified: all 3 callers pass instructions: scribe/service.py:351, :984, comms/service/draft.py:379).
 D4 scribe keeps its keyword name summarizer= on draft_incident_document (service.py:303) and summarize_transcript (:953), typed TextGenerator | None, so ~70 test call sites keep their keywords; only the stub method names change summarize -> generate. 145.9.3 and 145.11 rewrite those halves.
 D5 OpenAITextGenerator keeps the vendor call body, log events renamed openai_summarize_* -> openai_generate_* (check no alert or doc reads them first, see assumptions) ; the in-adapter tenant-None guard (CONFIG_NOT_CONFIGURED) is dropped because the provider never builds the adapter without a tenant; its test is replaced by the provider test.
 Behaviour delta (called out for review): unconfigured now answers TEXT_GENERATION_UNAVAILABLE for scribe as well as comms (was CONFIG_NOT_CONFIGURED for scribe). Unreachable in production: scribe declares Requirement('openai.tenant') (scribe/__init__.py:28) so boot fails first.

ORDERED STEPS (TDD: tests first in each step; ruff and targeted tests only until the end)
 1. Generate. cd app && make new-package ARGS='capability text_generation --classification generic --consumer features.incident.scribe --consumer features.incident.comms --adapters'; uv sync. Apply D1 (pyproject entry point and protected module -> .plugin; plugin.py holds register_requirements returning (); __init__.py docstring). Fill README purpose line (feature-free vocabulary; names consumers scribe and comms; AC #8).
 2. Tests first, tests/unit/capabilities/text_generation/: test_text_generation_conformance.py, test_text_generation_openai_adapter.py (moved from tests/unit/integrations/openai/test_openai_summarizer.py, 224 lines, patching the edge as now), test_text_generation_providers.py (moved and merged from test_openai_summarizer_unconfigured.py and comms test_incident_comms_text_generation_availability.py / _adapter.py), test_text_generation_plugin_registration.py (hookimpl present, returns no requirement, entry point matches). Conformance: one parametrised fixture across [OpenAITextGenerator over httpx.MockTransport, InMemoryTextGenerator(available=True)] for success text, instructions and budget forwarded, classified errors; second fixture across [UnconfiguredTextGenerator, InMemoryTextGenerator(available=False)] for is_available False, TEXT_GENERATION_UNAVAILABLE permanent error, no client built; enrolment test as capabilities/oncall's (test_oncall_in_memory_lookup_conformance.py:95): 'capabilities/text_generation/api.py:TextGenerator' in find_covered_protocols() and 'TextGenerator' in find_fakes().
 3. capabilities/text_generation/api.py: Protocol plus get_text_generator() (D2, D3). adapters/openai.py: OpenAISummarizer body, response helpers (_error_body, _extract_summary, _finish_reason, _usage) and logger moved from integrations/openai/summarizer.py:47-181, renamed OpenAITextGenerator(TextGenerator), method generate(source, ...), still reads OpenAISettings from integrations.openai (model, max_output_tokens, temperature stay in the vendor slice until 25.10.3). adapters/unconfigured.py: UnconfiguredTextGenerator moved from comms/adapters/text_generation.py:23-37 (is_available False). adapters/in_memory.py: InMemoryTextGenerator(TextGenerator) with scripted result, available flag, and a recorded calls list. providers.py per D2. All adapters explicitly subclass the Protocol.
 4. scribe: features/incident/scribe/service.py:61 import api (TextGenerator, get_text_generator); :303 and :953 annotation; :349 and :980 'summarizer or get_text_generator()'; :351 and :984 .generate(...); docstrings :7, :20, :313, :961-962 reworded. Delete 'features.incident.scribe.service -> integrations.openai' from pyproject.toml:346 (contract (e); unmatched_ignore alerting makes it mandatory). scribe tests: stubs in test_incident_scribe_draft_service.py:40, test_incident_scribe_summary_service.py:27 get generate(); test_incident_scribe_conversation_summarize.py:197-203 patches capabilities.text_generation.providers.get_text_generator_singleton instead of service.get_summarizer.
 5. comms: delete interfaces.py TextGenerator (:14-26; StatusPagePublisher stays) and adapters/text_generation.py; providers.py:11-23 loses the TextGenerator imports, get_status_update_text_generator and text_generation_available (get_status_page_publisher stays). service/draft.py:51 import TextGenerator from the capability api, :252/:372 types, :379 .generate(...), :591-592 _default_generator returns get_text_generator(). service/form.py:26 import dropped; the four functions that set ai_available (start :55, open :71, save :106/:111, fill) take 'generator: TextGenerator | None = None' and read (generator or get_text_generator()).is_available() once. entrypoints/slack.py:103 callers unchanged. comms tests: the 10 monkeypatch.setattr(form, 'text_generation_available', ...) sites (unit: new_entrypoint:121,195; review_entrypoint:163,329; save_entrypoint:157,208; form_save:103,203; integration: save_dispatch:122, generate_dispatch:203, review_dispatch:123) switch to the providers seam returning InMemoryTextGenerator(available=...) or to the generator= argument; test_incident_comms_text_generation_adapter.py and _availability.py are deleted (cases moved in step 2); tests/integration/server/test_lifespan_incident_plugins_openai_requirement.py:22,39,43,85 rewired to the capability provider and is_available(); comms tests that stub generate/summarize in test_incident_comms_status_update_generate*.py move to .generate.
 6. Vendor package: delete integrations/openai/summarizer.py; integrations/openai/__init__.py drops lines 10-13 and the three names from __all__ and the docstring; delete bin/baselines/vendor_package_contract.txt lines 8 and 20; delete tests/unit/integrations/openai/test_openai_summarizer*.py (moved in step 2). integrations/openai/ then holds __init__.py, client.py, settings.py only (AC #3). Optional hardening (Q3): contract (o) 'integrations.openai is imported only by capabilities.text_generation.adapters.openai besides the host (server)', modelled on contract (n).
 7. Guards and baselines: bin/baselines/test_seams_strict.txt header line 7 comment about text_generation_available reworded; no entries added; check there are none for the moved tests. tests/integration/server/test_lifespan_plugin_loading.py (expected plugin list near :40-46) gains text_generation. Re-run the unit tests in tests/unit/bin that touch the generator output (test_bin_package_toml_edit.py, test_bin_fake_coverage_check.py) only if they read live pyproject.
 8. ADRs, dated 2026-11-19 Changes lines with '(TASK-25.10.2, human ...)': incident-management.md:138 drop the Summarizer/TextGenerator tolerance (and :60 stays); outbound-clients.md:79 delete the OpenAI tolerance line, add a Changes line; feature-packages.md:14 and :119 drop the scribe integrations.openai import; product-scope.md:22 Incident response row gains '`text_generation` capability'; plugins.md:61 optional-dependency paragraph gains 'an optional capability exposes its availability on its api.py Protocol' (AC #9) and an order note (no hookspec and no lower-capability import, so no order declared; the first capability needing one declares it and where); plugin-architecture.md:64 'Text generation is a capability' gains 'the capability always provides an implementation; unconfigured, it answers is_available() false and TEXT_GENERATION_UNAVAILABLE on every call; a consumer offering an optional action asks is_available() first' (AC #9). configuration.md:117 is NOT edited here (25.10.3 owns it). Also refresh READMEs: comms README:32, :93-96, :100, :156; scribe README:21, :48, :96, :447 (docs only).
 9. Gates at the end, once each in sequence from app/: ruff check; make check-import-contracts check-settings-key-ownership check-package-shape check-test-seams check-fake-coverage check-vendor-package-contract; mypy; then full pytest tests --ignore=tests/smoke. Paste outputs in --notes.

AC TRACEABILITY
 #1 steps 3 and 6 (api, providers, adapters/openai importing integrations.openai; optional contract (o)); tests: test_text_generation_providers.py (unconfigured builds no client), conformance suite, contract (m)/(e) via check-import-contracts.
 #2 steps 2 and 3; tests: conformance suite and enrolment test; make check-fake-coverage.
 #3 step 6; make check-vendor-package-contract.
 #4 step 4; scribe draft, summary and conversation_summarize suites with assertions unchanged (stub method renamed only).
 #5 step 5; tests: comms form_save, new/review/save entrypoint and dispatch tests (AI section absent when is_available False, save and approve still work), providers unit test.
 #6 steps 2, 5, 7; make check-test-seams with no new baseline line (the adapter tests patch integrations.openai.client.build_openai_client, classified EDGE; consumer tests use the providers.py seam).
 #7 and #9 step 8 and step 9.
 #8 step 1 (with D1 flagged).

TEST MATRIX (tests/unit/capabilities/text_generation/): happy (success text, instructions in system message, user content is source); boundary (max_output_tokens None uses vendor setting, explicit overrides; negative temperature omitted; empty content logs empty and returns ''); failure (429 with Retry-After, 5xx, connect error, truncated finish_reason length, unknown exception propagates); availability (unconfigured and in-memory unavailable: is_available False, TEXT_GENERATION_UNAVAILABLE, no client built); provider caching (cache_clear in fixture) and tenant switch; plugin (hookimpl, entry point equals protected module, enablement key present, boot lists).

DOMAIN-MODEL EVOLUTION: not applicable. No entity, record, or persisted shape changes; the Protocol is a behaviour contract and OperationResult[str] is unchanged.

SIZE (approved exception, one concept: generator boilerplate plus a move, behaviour unchanged). Production files: 9 new (4 generated: __init__, README, api, adapters/__init__; plugin.py; providers.py; adapters/openai.py, unconfigured.py, in_memory.py), 8 modified (scribe/service.py, comms/service/draft.py, service/form.py, providers.py, interfaces.py, integrations/openai/__init__.py, pyproject.toml, config/base.toml), 2 deleted (integrations/openai/summarizer.py, comms/adapters/text_generation.py), plus 2 baseline lines; ~19 production files against the ~23 approved. LOC: ~175 moved (adapter body ~150, unconfigured ~25), ~35 generated, ~120 hand-written (api 50, providers 25, in_memory 35, plugin 10), ~60 edited lines in existing files, ~245 deleted. Tests: about 20 files touched (2 moved, 2 deleted, 1 new conformance, 1 plugin test, ~10 one-line seam rewires, 3 stub renames). Docs: 6 ADRs and 2 READMEs.

ASSUMPTIONS AND HOW TO VERIFY
 - Patching capabilities.text_generation.adapters.openai.build_openai_client classifies EDGE (check_test_seams.classify follows the import binding to integrations): verify with make check-test-seams after step 2.
 - Provider seam works through the lazy import in api.get_text_generator: verify by the conversation_summarize test.
 - No consumer reads the log event names openai_summarize_*: rg across app/, terraform/, docs before renaming; keep names if any hit.
 - The in-memory fake in capabilities/*/adapters/in_memory.py is found by check_fake_coverage find_fakes (oncall precedent: adapters/in_memory.py).
 - Ordering with 114.5 (see BASE).
 - Entry point change needs uv sync before tests; CI installs fresh.

BLAST RADIUS AND ROLLBACK: scribe draft and summarize and comms drafting all route through the new provider; a wrong provider choice would disable AI drafting silently for comms (it falls back to hand-written). One git revert restores the vendor summarizer and comms adapter because nothing outside this PR depends on the capability until 25.10.3 (which depends on this merge, not the reverse). No env, terraform or production.toml change; the base.toml key is inert. Entry point added: deployments need the wheel rebuilt, which every release does.

REVISIONS 2026-11-19 (human rulings; supersede the items above where they differ)
 - Q1 approved with the platform/extension framing: this task depends on TASK-114.6 (row 15j), so the generator emits plugin.py and names capabilities.text_generation.plugin as entry point and contract (m) protected module. D1's hand edits are dropped; step 1 is the generator command plus uv sync and the README purpose line only. The description's 'first package under app/capabilities/' is stale (oncall exists); AC #8 carries the correction.
 - Q2 approved with the framing: the key switches only the plugin module; README line says text_generation's key switches nothing yet. ADR text per AC #9 (plugin-architecture.md platform/extension split, always-present capability, api.py public plugin API with hookspec-deprecation.md from the first adopter release; plugins.md key rule; product-scope.md adopter line and vendor-as-adapter line).
 - Q3 approved: step 6 adds import-linter contract (o) 'integrations.openai is imported only by capabilities.text_generation.adapters.openai, besides the host (server)', modelled on (n), with a plugin-architecture.md Checks line (AC #1).
 - Q4 approved: scribe keeps summarizer=; TASK-145.9.3 and TASK-145.11 carry a note to name it for its role when they move the functions.
 - Q5 approved: log events renamed openai_summarize_* -> openai_generate_* (no reader in terraform/, bin/, .github/; scribe README:420 updated); the PR body lists the rename.
 - Q6 settled by plugin-architecture.md:64 and TASK-25.10.3 AC #3: max_output_tokens stays optional here.
 - AC #6 and #8 reworded, #1 gains contract (o), #9 widened (human, 2026-11-19).
 - Rebase note: #1873 edits config/base.toml and incident-management.md, #1867 incident-management.md (text conflicts only).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (25.10 review, human): split and size exception approved. Now depends on TASK-114.3, so the generator emits only api.py plus --adapters, and nothing is deleted by hand.
Q2, comms TextGenerator: the ADRs already decide this, no gap. incident-management.md:128 lists comms' local TextGenerator as tolerated only until TASK-25.10. feature-packages.md lets a package import capabilities' api.py and keeps interfaces.py for Protocols that the package's own adapters implement. TASK-186 kept it only as a mechanical move, deferring here. Upcoming consumers (145.9 summarize in response, 145.11 draft in postmortem, 134 template fill, 165.8 personalisation) would each otherwise re-declare it, while OpenTelemetry's API-package model has libraries depend on the published API only. Deleted; parent AC #2 rewording is in the TASK-25.10 comment.
Q3, availability: ADR gap. plugins.md and plugin-architecture.md say an optional dependency's absence is reported as unavailable, never an error, but not how a consumer asks before offering an action (the form's AI section). Options: (a) the capability always provides an implementation, a no-op when unconfigured, and the Protocol exposes is_available(). This is OpenTelemetry's no-op default API (OTEP 0005), and it keeps one always-resolvable factory per Protocol, matching TASK-109's eager-validating registry. (b) the provider returns TextGenerator | None, as Spring's ObjectProvider.getIfAvailable does. That forces every consumer, required ones included, to narrow a None that boot already rules out. Recommend (a). ADR text, riding with this PR: plugin-architecture.md 'Text generation is a capability' gains 'the capability always provides an implementation; unconfigured, it answers is_available() false and TEXT_GENERATION_UNAVAILABLE on every call; a consumer offering an optional action asks is_available() first'. plugins.md's optional-dependency paragraph gains the general rule: an optional capability exposes its availability on its api.py Protocol.
Production safety: behaviour unchanged. The unconfigured implementation is today's comms UnavailableTextGenerator, moved, and comms' fallback path keeps its tests, which move onto the in-memory fake with available False.

2026-11-09 (human): Q3 ruled: the capability always provides an implementation, a no-op when unconfigured, with is_available() on its Protocol; the ADR text rides with this PR (AC added).

2026-11-09: now depends on TASK-114.4 (the generator slice of the 114.3 re-plan) instead of TASK-114.3; AC #8's '--adapters and no other optional entry' comes from 114.4.

2026-11-09 (TASK-114.4 plan, awaiting approval): if approved, a capability gets only __init__.py, README.md and api.py by default, so this task's command becomes: capability text_generation --classification generic --consumer features.incident.scribe --consumer features.incident.comms --adapters; the step deleting the empty hookspecs.py, interfaces.py, service.py and entrypoints/ goes. Re-check at this task's pickup.

2026-11-19: **Implemented** on task-25.10.2-text-generation-capability from main d4fcf24f (114.6 merged #1876), ACs #1-#9 checked, In Progress.
- Generated with make new-package ARGS='capability text_generation --classification generic --consumer features.incident.scribe --consumer features.incident.comms --adapters' plus uv sync: __init__.py, plugin.py, README.md, api.py, adapters/__init__.py, entry point text_generation = capabilities.text_generation.plugin, the same module in contract (m), text_generation = true under [plugins.incident_response]. Only the generator's placeholders were filled (purpose line, README body); no generated file moved, edited away or deleted.
- capabilities/text_generation: api.py TextGenerator (is_available, async generate(source, *, instructions, max_output_tokens=None)) and get_text_generator() (lazy providers import, oncall shape); providers.py get_text_generator_singleton (OpenAI when [openai.tenant] is set, else UnconfiguredTextGenerator, logs text_generation_unconfigured once); adapters/openai.py OpenAITextGenerator (vendor body moved, default instructions and the tenant-None guard deleted per D3/D5) and build_openai_text_generator(); adapters/unconfigured.py; adapters/in_memory.py InMemoryTextGenerator (available, respond, result, recorded calls).
- Deleted: integrations/openai/summarizer.py and its exports and 2 baseline lines; comms adapters/text_generation.py, interfaces.py TextGenerator, providers get_status_update_text_generator and text_generation_available; the scribe.service -> integrations.openai ignore. Contract (o) added (plugin-architecture.md Checks line).
- comms form: start/open/save take generator: TextGenerator | None and read is_available() through _ai_available; fill keeps deriving from the result code. Tests: 7 files moved from patching form.text_generation_available to the providers seam returning InMemoryTextGenerator(available=...); 8 stubs renamed summarize -> generate with is_available.
- Log events renamed openai_summarize_* -> openai_generate_* (Q5); the usage and truncated events' summary_length field is now text_length; comms' incident_status_update_text_generation_unconfigured is now text_generation_unconfigured. No reader outside the repo docs (rg over app/, terraform/, bin/, .github/, decisions/).
- tests/unit/bin/test_bin_package_toml_edit.py: the rename test asserted a live ignore string that this PR deletes; it now adds its own ignore line to the pyproject text before renaming (same assertion).
- ADRs (dated 2026-11-19 Changes lines): plugin-architecture.md (platform/extension split, always-present capability, api.py public plugin API with hookspec-deprecation.md, text generation unavailable wording, contract (o) Checks line); plugins.md (a capability's key switches only its plugin module; optional capability reports on its Protocol; capability order undeclared until first need); product-scope.md (adopter feature plugins, vendor as adapter, text_generation row); feature-packages.md:14/:119; outbound-clients.md OpenAI tolerance deleted; incident-management.md tolerance deleted. READMEs: comms, scribe, capability.
- Gates (from app/): ruff check . All checks passed; make check-import-contracts Contracts: 15 kept, 0 broken; check-settings-key-ownership OK; check-package-shape OK (3 baselined); check-test-seams OK (47 + 12 baselined, none added); check-fake-coverage OK (4 baselined gaps); check-vendor-package-contract OK (13 baselined, was 15); mypy Found 40 errors in 13 files (pre-existing, legacy modules/ and infrastructure/i18n, integrations/slack; none in touched files; same as 114.6); pytest tests --ignore=tests/smoke first run 1 failed (the bin rename test above), 7890 passed; after the fix 7891 passed.
- Merge blast radius: scribe draft/summarize and comms AI drafting route through the capability provider; behaviour unchanged (unconfigured scribe now answers TEXT_GENERATION_UNAVAILABLE instead of CONFIG_NOT_CONFIGURED, unreachable since scribe requires openai.tenant). New entry point: the release image's wheel carries it. No terraform, SSM or production.toml change; deploy-checks not required. One git revert undoes it.

2026-11-19 (human, #1877 review): renamed to ai_writing before merge. Package regenerated with make new-package ARGS='capability ai_writing --classification generic --consumer features.incident.scribe --consumer features.incident.comms --adapters' (the text_generation generator edits removed first; only placeholders filled, 'Ai writing' title corrected to 'AI writing'). AIWriter.write(), get_ai_writer(), get_ai_writer_singleton, OpenAIWriter, UnconfiguredAIWriter, InMemoryAIWriter, build_openai_writer; ErrorCode.AI_WRITING_UNAVAILABLE replaces TEXT_GENERATION_UNAVAILABLE; log events openai_write_* and ai_writing_unconfigured; contract (o) names capabilities.ai_writing.adapters.openai; comms' parameter is ai_writer (comms prose already uses 'another writer' for a concurrent person). Slack action ids and locale keys (status_update.generate, generate_unavailable) unchanged: they name the Draft with AI button and live in open modals. ADR Decision text and today's Changes lines renamed; older dated lines kept; plugin-architecture.md states the purpose boundary. Open downstream tasks (25.10, 25.10.3, 134, 145, 145.9, 145.9.3, 145.11, 140.11, 140.12, 114) carry a rename note.

Rename gates (from app/): ruff check . All checks passed; check-import-contracts Contracts: 15 kept, 0 broken; check-settings-key-ownership OK; check-package-shape OK (3 baselined); check-test-seams OK (47 + 12 baselined); check-fake-coverage OK (4 baselined); check-vendor-package-contract OK (13 baselined); mypy Found 40 errors in 13 files (pre-existing, none in touched files); pytest tests --ignore=tests/smoke 7891 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-19T13:50:00Z

---

Plan review proposals (no AC deleted or reworded; for the human to decide):
- Description and AC #8: the generated entry point text_generation = capabilities.text_generation makes import-linter contract (m) reject any feature importing capabilities.text_generation.api (verified on a scratch copy: features.incident.scribe.service -> capabilities.text_generation.api illegal). Propose AC #8 reads: entry point text_generation = capabilities.text_generation.plugin, protected module the same; the generator gains a --plugin option first (new tooling task) or the three spots are hand-edited and recorded. Also 'the first package under app/capabilities/' is stale: capabilities/oncall exists.
- AC #6: 'the comms test_seams_strict.txt entries for text_generation_available are absent' is already true (line 7 is a comment, not an entry). Propose: 'no text_generation or summarizer entry is added to test_seams_strict.txt and the stale header comment is reworded'.
- AC #1: add 'an api.py-level getter delegates to providers.py, the sanctioned test seam' only if the human wants the seam named; otherwise leave.

---

created: 2026-11-19T14:04:00Z

---

2026-11-19 program-scope assessment of plan Q1-Q6 (proposed, awaiting approval). Q1 ADR gap (plugins.md:39 names the plugin submodule only for settings read early; every capability's api.py is imported by features, which contract (m) forbids on a package entry point; 146.1.1 D4 precedent; 25.10.3 and TASK-83.4 hit it again): plugins.md:39 reworded so a capability and any package with settings.py always use a plugin module, generator fix in new TASK-114.6 (row 15j) before this task; D1's hand edits then go and this task depends on 114.6. Q2 ADR gap (a disabled plugin is never imported cannot hold for a capability's api.py): a capability's key switches only its plugin module's hooks; api.py stays importable; availability comes from configuration; README line; plugins.md line rides here. Q3 contract (o) added (precedent (n), plugin-architecture.md:64), AC #1 gains it. Q4 keep summarizer=; note on 145.9.3 and 145.11. Q5 rename openai_summarize_* to openai_generate_* (no reader outside scribe README:420). Q6 settled by plugin-architecture.md:64 and 25.10.3 AC #3.

---

created: 2026-11-19T14:17:00Z

---

2026-11-19 (human): Q3, Q4, Q5 and the AC #6/#8 rewordings approved as recommended. Q1/Q2 pending under the human's framing (capabilities are the project's platform, strict and always present; features are the extension surface adopters write). Proposed ADR text riding here: plugin-architecture.md platform/extension split, capability always present (provider always resolves, availability on the Protocol), api.py public plugin API with hookspec-deprecation.md from the first adopter release; product-scope.md:18 adopter extension line; plugins.md Q2 key rule. AC changes (#1 contract (o), #6, #8, #9 widened to the always-present rule) applied in one pass after Q1/Q2 are confirmed.

---

created: 2026-11-19T14:28:00Z

---

2026-11-19 (human): plan approved with Q1-Q6 rulings and the platform/extension framing (see plan REVISIONS). Implementation waits on TASK-114.6 (row 15j).

---
<!-- COMMENTS:END -->
