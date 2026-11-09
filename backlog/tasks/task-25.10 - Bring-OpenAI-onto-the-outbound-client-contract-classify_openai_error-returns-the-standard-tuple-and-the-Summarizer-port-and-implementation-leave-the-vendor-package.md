---
id: TASK-25.10
title: >-
  Bring OpenAI onto the outbound-client contract: classify_openai_error returns
  the standard tuple, and the Summarizer port and implementation move to the
  text-generation capability
status: To Do
assignee: []
created_date: 2026-09-18 16:51
updated_date: '2026-11-09T15:43:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-106
  - TASK-110
  - TASK-114.2
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/openai/client.py
  - app/integrations/openai/summarizer.py
  - decisions/plugin-architecture.md
  - decisions/feature-packages.md
  - app/packages/incident/scribe/service.py
  - https://github.com/cds-snc/sre-bot/issues/1600
parent_task_id: TASK-25
priority: medium
ordinal: 243000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The OpenAI integration is non-compliant with decisions/outbound-clients.md and migrates as part of that effort. outbound-clients.md lists it as a tolerated divergence until this closes.

TODAY:
- app/integrations/openai/client.py: build_openai_client returns an httpx.AsyncClient with a timeout and no retry policy. classify_openai_error returns an OperationResult instead of the contract's (OperationStatus, error_code, retry_after) tuple. It is baselined as operation-result:integrations/openai/client.py.
- app/integrations/openai/summarizer.py: the Summarizer Protocol (a port), the OpenAISummarizer implementation that returns OperationResult, response-parsing helpers and get_summarizer. It is baselined as both module: and operation-result: (bin/baselines/vendor_package_contract.txt lines 8, 20, 21).
- client.py, summarizer.py and settings.py still use 'from __future__ import annotations', which CLAUDE.md marks as deprecated on 3.14. That counts as a bug to fix in touched files.

CONSUMERS (re-grep):
- features/incident/scribe/service.py:55 imports Summarizer and get_summarizer (the draft and summarize use cases); the import-linter ignore 'features.incident.scribe.service -> integrations.openai' covers it.
- features/incident/comms/adapters/text_generation.py:17 binds the comms TextGenerator port to get_summarizer, with the UnavailableTextGenerator fallback when the OpenAI settings cannot load.

OWNER DECIDED (decisions/plugin-architecture.md, 'Text generation is a capability'; decisions/incident-management.md). The Summarizer port and its OpenAI implementation move to a new capability, app/capabilities/text_generation/.
- api.py holds the port, its domain types and the provider function. It keeps the one operation both consumers use today: source text plus instructions gives text, as OperationResult. Its names are feature-free: no incident or Slack vocabulary.
- adapters/openai.py holds the OpenAI implementation and the response-parsing helpers. It is the only file importing integrations.openai, does try/except plus classify, and builds OperationResult.
- An in-memory fake of the port lives in the package (cloud-portability.md fake contract).
- Features keep their own prompt text and post-processing and pass them in.
The structured template-fill operation is TASK-134, not this task. The vendor package keeps only the client factory, classification and settings.

SEQUENCING. This is the first package under app/capabilities/ unless a workplace capability (TASK-119 to TASK-121, TASK-138) lands first, so it waits for the generator and shape check (TASK-114). Whichever capability lands first adds capabilities to the import-linter root_packages (app/pyproject.toml:209).

TARGET. integrations/openai/ exports build_openai_client (timeout plus a retry policy set once at construction, stated explicitly), classify_openai_error returning the standard tuple with ErrorCode registry members (UNAUTHENTICATED for 401, FORBIDDEN for 403), and settings. The port and implementation live in app/capabilities/text_generation/ as described above. Both incident consumers (scribe and comms) are repointed to its api.py with behaviour unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/openai/ contains only __init__.py, client.py and settings.py; classify_openai_error returns (OperationStatus, error_code, retry_after); every openai entry in bin/baselines/vendor_package_contract.txt is removed
- [ ] #2 The port and its OpenAI implementation live in app/capabilities/text_generation/ (api.py, adapters/openai.py, an in-memory fake, README with classification and feature consumers); the package passes the TASK-114 shape check and its vocabulary is feature-free; the capability always provides an implementation, a no-op answering is_available() false when the OpenAI tenant entry is absent, never an error; features/incident/scribe/service.py imports only its api.py; comms' local TextGenerator interface and adapters/text_generation.py are deleted and comms depends on the capability's api.py Protocol (incident-management.md:128); behaviour is unchanged (comms treats text generation as optional and falls back when it is unavailable; scribe requires it while scribe exists, TASK-172) and covered by their existing tests; the 'features.incident.scribe.service -> integrations.openai' import-linter ignore is removed
- [x] #3 The OpenAI client's retry policy is explicit at construction (or explicitly none, with the reason recorded), alongside its timeout
- [x] #4 Classification tests cover each mapped HTTP status family and Retry-After, plus one unmapped exception propagating; no 'from __future__ import annotations' remains in touched files
- [ ] #5 decisions/outbound-clients.md no longer lists OpenAI as a tolerated divergence; ruff, mypy, lint-imports, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
- [ ] #6 The capability has its pyproject entry point and an enablement key in the base configuration file (decisions/plugins.md); if it is the first package under app/capabilities/, the same PR adds capabilities to the import-linter root_packages
- [ ] #7 integrations/openai/settings.py holds the connection only: [openai] timeout_seconds (plus the retry policy of AC #3) and [openai.tenant] base_url, with OPENAI__API_KEY; max_output_tokens, temperature and the tenant's model are gone from the vendor slice, and production.toml and local.toml move model to the capability's table in the same PR
- [ ] #8 capabilities/text_generation/settings.py holds the model ([text_generation] model): empty in base.toml, set in production.toml and local.toml (the organisation's value, configuration.md); an unset model makes the capability report unavailable, and a required consumer declares Requirement('text_generation.model'); each feature use case passes its own output budget from its own settings (scribe's catch-up summary gains one, 3000 as today, so production sends the same); the port carries an optional per-call temperature, omitted when unset; decisions/configuration.md drops the generation-parameters tolerance
- [ ] #9 The text-generation capability is created with make new-package (TASK-114.2; after TASK-114.4 it emits only the parts it uses); its README names its feature consumers; its enablement key sits in [plugins.incident_response] (one consuming area, product-scope.md 2026-11-06)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-06 (TASK-186 review): settle at pickup whether comms' local TextGenerator (features/incident/comms/interfaces.py after TASK-186) is deleted in favour of the capability's api.py Protocol, as incident-management.md:128 implies, or kept behind comms/adapters/text_generation.py as AC #2 reads; reconcile the ADR line either way. comms keeps its status-update prompt (service/prompt.py after TASK-186).

2026-11-09 (plan session): the size gate trips. Unsplit, the task is about 30 production files across integrations/openai, the new capability, scribe, comms and server configuration, and it mixes a vendor contract change, a move and a settings migration. Split expand -> migrate -> contract, sequential, each a single PR from main:
- TASK-25.10.1 vendor client contract: tuple classification, explicit connect retries. Planned; awaits approval.
- TASK-25.10.2 create the capability with make new-package; scribe and comms repointed to api.py; the comms TextGenerator question settled there (deleted); text_generation_available ends. Plan at pickup; a size exception is proposed.
- TASK-25.10.3 generation parameters move to the capability and the callers (ACs #7 and #8). Plan at pickup.
Parent ACs, by slice: #1 (tuple: .1; files and baseline: .2), #2 .2, #3 .1, #4 .1, #5 (outbound-clients: .1 and .2; configuration.md: .3), #6 .2, #7 .3, #8 .3, #9 .2. Check each parent AC as its slice merges.

2026-11-09 (human): AC #2 rewording approved as proposed in comment #1 (comms' local TextGenerator and adapters/text_generation.py deleted; comms depends on the capability's api.py Protocol), and aligned with the OQ3 ruling (no-op implementation plus is_available()). OQ6 ruled: the model is the organisation's value, so [text_generation] model is empty in base.toml and set in production.toml and local.toml; unset means unavailable, plus Requirement('text_generation.model') for required consumers; AC #8 reworded ('holds the default model' replaced). OQ4 ruled: TASK-114.3 as proposed (row 15g, before 25.10.2). TASK-25.10.1 merged (#1838, d3778e0a, 2026-11-09 15:06 UTC): ACs #3 and #4 checked (slice .1 only); #1 and #5 wait on .2 (and #5 on .3).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-09T13:42:00Z

---

Proposed AC #2 wording (25.10 plan, 2026-11-09): replace 'features/incident/comms/adapters/text_generation.py import only its api.py' with 'comms' local TextGenerator interface and adapters/text_generation.py are deleted; comms depends on the capability's api.py Protocol (incident-management.md:128)'. The capability reports unavailable itself, so the comms adapter would be dead code. Awaiting the human's ruling.

---
<!-- COMMENTS:END -->
