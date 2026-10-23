---
id: TASK-25.10
title: >-
  Bring OpenAI onto the outbound-client contract: classify_openai_error returns
  the standard tuple, and the Summarizer port and implementation move to the
  text-generation capability
status: To Do
assignee: []
created_date: 2026-09-18 16:51
updated_date: '2026-10-23T17:09:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-106
  - TASK-110
  - TASK-114
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
- [ ] #2 The port and its OpenAI implementation live in app/capabilities/text_generation/ (api.py, adapters/openai.py, an in-memory fake, README with classification and feature consumers); the package passes the TASK-114 shape check and its vocabulary is feature-free; features/incident/scribe/service.py and features/incident/comms/adapters/text_generation.py import only its api.py, with unchanged behaviour (including the comms unconfigured fallback) covered by their existing tests; the 'features.incident.scribe.service -> integrations.openai' import-linter ignore is removed
- [ ] #3 The OpenAI client's retry policy is explicit at construction (or explicitly none, with the reason recorded), alongside its timeout
- [ ] #4 Classification tests cover each mapped HTTP status family and Retry-After, plus one unmapped exception propagating; no 'from __future__ import annotations' remains in touched files
- [ ] #5 decisions/outbound-clients.md no longer lists OpenAI as a tolerated divergence; ruff, mypy, lint-imports, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
- [ ] #6 The capability has its pyproject entry point and an enablement key in the base configuration file (decisions/plugins.md); if it is the first package under app/capabilities/, the same PR adds capabilities to the import-linter root_packages
<!-- AC:END -->
