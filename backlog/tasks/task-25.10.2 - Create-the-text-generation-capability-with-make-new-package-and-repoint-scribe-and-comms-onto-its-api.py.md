---
id: TASK-25.10.2
title: >-
  Create the text-generation capability with make new-package and repoint scribe
  and comms onto its api.py
status: To Do
assignee: []
created_date: '2026-11-09T13:41:00Z'
updated_date: '2026-11-09T15:42:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.10.1
  - TASK-114.4
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
Second slice of TASK-25.10 (migrate). The Summarizer port and its OpenAI implementation leave the vendor package for app/capabilities/text_generation/, the first package under app/capabilities/, and both incident consumers import only its api.py. Behaviour is unchanged; plan it at pickup against main after 25.10.1 merges.

CREATE: make new-package ARGS='capability text_generation --classification generic --consumer features.incident.scribe --consumer features.incident.comms' (no --settings: the slice arrives in 25.10.3). Dry run on a scratch copy (2026-11-09): the generator adds capabilities to root_packages, the wheel packages and every contract that lists features, the entry point text_generation = capabilities.text_generation and the key "text_generation" = true in [plugins.incident_response]. It also emits empty hookspecs.py, interfaces.py, service.py and entrypoints/; this capability has no extension point, no service and no inbound handler, so those are deleted in the same PR (dead code).

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
- [ ] #1 api.py holds the TextGenerator Protocol (is_available, generate with required instructions and optional max_output_tokens) and get_text_generator(); with no [openai.tenant] entry it returns an implementation that reports unavailable (is_available False, TEXT_GENERATION_UNAVAILABLE) without building a client; adapters/openai.py is the only module in the capability importing integrations.openai
- [ ] #2 An in-memory fake in adapters/in_memory.py explicitly subclasses the Protocol and is exercised by a conformance suite shared with the OpenAI adapter; make check-fake-coverage passes
- [ ] #3 integrations/openai/ holds only __init__.py, client.py and settings.py; its summarizer entries are gone from bin/baselines/vendor_package_contract.txt; make check-vendor-package-contract passes
- [ ] #4 features/incident/scribe/service.py imports the capability's api.py only and the 'features.incident.scribe.service -> integrations.openai' ignore is deleted; scribe's draft and summarize tests pass unchanged in assertions
- [ ] #5 comms' local TextGenerator Protocol and adapters/text_generation.py are deleted; comms services depend on the capability's Protocol; text_generation_available is gone and the form reads is_available() from the injected generator; the form has no AI section when text generation is unavailable and save and approve still work (existing tests, now on the in-memory fake)
- [ ] #6 Tests under tests/unit/capabilities/text_generation/ pass make check-test-seams with no strict baseline entry (the adapter is faked at the httpx edge); the comms test_seams_strict.txt entries for text_generation_available are absent
- [ ] #7 decisions/incident-management.md, outbound-clients.md, feature-packages.md, product-scope.md and plugins.md are updated with dated Changes lines; full gates plus make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams and check-fake-coverage pass, with output in notes
- [ ] #8 app/capabilities/text_generation/ is created with make new-package (classification generic, consumers features.incident.scribe and features.incident.comms, with --adapters and no other optional entry; TASK-114.3), so no generated file is deleted by hand; its entry point and [plugins.incident_response] key exist; capabilities is an import-linter root package; its README names the feature consumers and states the vocabulary is feature-free; make check-package-shape passes with no new baseline entry
- [ ] #9 decisions/plugin-architecture.md ('Text generation is a capability') and plugins.md (optional dependencies) state the availability rule: the capability always provides an implementation, a no-op answering is_available() false when unconfigured, and a consumer offering an optional action asks is_available() first; dated Changes lines
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09 (25.10 review, human): split and size exception approved. Now depends on TASK-114.3, so the generator emits only api.py plus --adapters, and nothing is deleted by hand.
Q2, comms TextGenerator: the ADRs already decide this, no gap. incident-management.md:128 lists comms' local TextGenerator as tolerated only until TASK-25.10. feature-packages.md lets a package import capabilities' api.py and keeps interfaces.py for Protocols that the package's own adapters implement. TASK-186 kept it only as a mechanical move, deferring here. Upcoming consumers (145.9 summarize in response, 145.11 draft in postmortem, 134 template fill, 165.8 personalisation) would each otherwise re-declare it, while OpenTelemetry's API-package model has libraries depend on the published API only. Deleted; parent AC #2 rewording is in the TASK-25.10 comment.
Q3, availability: ADR gap. plugins.md and plugin-architecture.md say an optional dependency's absence is reported as unavailable, never an error, but not how a consumer asks before offering an action (the form's AI section). Options: (a) the capability always provides an implementation, a no-op when unconfigured, and the Protocol exposes is_available(). This is OpenTelemetry's no-op default API (OTEP 0005), and it keeps one always-resolvable factory per Protocol, matching TASK-109's eager-validating registry. (b) the provider returns TextGenerator | None, as Spring's ObjectProvider.getIfAvailable does. That forces every consumer, required ones included, to narrow a None that boot already rules out. Recommend (a). ADR text, riding with this PR: plugin-architecture.md 'Text generation is a capability' gains 'the capability always provides an implementation; unconfigured, it answers is_available() false and TEXT_GENERATION_UNAVAILABLE on every call; a consumer offering an optional action asks is_available() first'. plugins.md's optional-dependency paragraph gains the general rule: an optional capability exposes its availability on its api.py Protocol.
Production safety: behaviour unchanged. The unconfigured implementation is today's comms UnavailableTextGenerator, moved, and comms' fallback path keeps its tests, which move onto the in-memory fake with available False.

2026-11-09 (human): Q3 ruled: the capability always provides an implementation, a no-op when unconfigured, with is_available() on its Protocol; the ADR text rides with this PR (AC added).

2026-11-09: now depends on TASK-114.4 (the generator slice of the 114.3 re-plan) instead of TASK-114.3; AC #8's '--adapters and no other optional entry' comes from 114.4.
<!-- SECTION:NOTES:END -->
