---
id: TASK-25.10
title: >-
  Bring OpenAI onto the outbound-client contract: classify_openai_error returns
  the standard tuple, and the Summarizer port and implementation move to the
  text-generation capability
status: To Do
assignee: []
created_date: '2026-09-18 16:51'
updated_date: '2026-10-02 17:44'
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
parent_task_id: TASK-25
priority: medium
ordinal: 243000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-09-18 (human decision): the OpenAI integration was introduced in parallel with the outbound-client refactor, is non-compliant, and migrates as part of that effort. It is listed as a tolerated divergence in decisions/outbound-clients.md until this closes.

TODAY (verified 2026-09-18):
- app/integrations/openai/client.py: build_openai_client returns an httpx.AsyncClient with a timeout and no retry policy. classify_openai_error returns an OperationResult instead of the contract's (OperationStatus, error_code, retry_after) tuple. It is baselined as operation-result:integrations/openai/client.py.
- app/integrations/openai/summarizer.py: the Summarizer Protocol (a port), the OpenAISummarizer implementation that returns OperationResult, response-parsing helpers and get_summarizer. It is baselined as both module: and operation-result:.
- client.py, summarizer.py and settings.py still use 'from __future__ import annotations', which CLAUDE.md marks as deprecated on 3.14. That counts as a bug to fix in touched files.

CONSUMERS (re-grep): packages/incident/scribe/service.py, the one service module of the scribe subdomain since TASK-135.4 (it holds both the draft and the summarize use case). It imports Summarizer and get_summarizer from integrations.openai. packages/incident/scribe/settings.py refers to integration settings in prose.

OWNER DECIDED (human, 2026-10-01; decisions/plugin-architecture.md, "Text generation is a capability"). The Summarizer port and its OpenAI implementation move to a new capability, app/capabilities/text_generation/. The earlier options (an infrastructure service, or a per-feature adapter in each consumer) are rejected.
- api.py holds the port, its domain types and the provider function. It keeps the one operation both consumers use today: source text plus instructions gives text, as OperationResult. Its names are feature-free: no incident or Slack vocabulary.
- adapters/openai.py holds the OpenAI implementation and the response-parsing helpers. It is the only file importing integrations.openai, does try/except plus classify, and builds OperationResult.
- An in-memory fake of the port lives in the package (cloud-portability.md fake contract).
- Features keep their own prompt text and post-processing and pass them in.
The structured template-fill operation is TASK-134, not this task. The vendor package keeps only the client factory, classification and settings.

SEQUENCING. This is the first package under app/capabilities/ unless a workplace capability (TASK-119 to TASK-121) lands first, so it waits for entry-point loading (TASK-110) and the generator and shape check (TASK-114), as those do. Whichever capability lands first adds capabilities to the import-linter root packages.

TARGET. integrations/openai/ exports build_openai_client (timeout plus a retry policy set once at construction, stated explicitly), classify_openai_error returning the standard tuple, and settings. The port and implementation live in app/capabilities/text_generation/ as described above. Both features are repointed to its api.py with behaviour unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/openai/ contains only __init__.py, client.py and settings.py; classify_openai_error returns (OperationStatus, error_code, retry_after); every openai entry in bin/baselines/vendor_package_contract.txt is removed
- [ ] #2 The port and its OpenAI implementation live in app/capabilities/text_generation/ (api.py, adapters/openai.py, an in-memory fake, README with classification and feature consumers); the package passes the TASK-114 shape check and its vocabulary is feature-free; the incident scribe subdomain (packages/incident/scribe, the former incident_draft and incident_summary) imports only its api.py, with unchanged behaviour covered by its existing tests
- [ ] #3 The OpenAI client's retry policy is explicit at construction (or explicitly none, with the reason recorded), alongside its timeout
- [ ] #4 Classification tests cover each mapped HTTP status family and Retry-After, plus one unmapped exception propagating; no 'from __future__ import annotations' remains in touched files
- [ ] #5 decisions/outbound-clients.md no longer lists OpenAI as a tolerated divergence; ruff, mypy, lint-imports, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:10
---
2026-09-24 (human decision): the Summarizer's home is decided during this task's planning. decisions/plugin-architecture.md narrows the options to two, and app/infrastructure/ is not one of them (hosting-only). (a) Per-subdomain adapters: features/incident/draft and features/incident/summary each own a small adapters/openai.py behind their own port. Subdomains may not import each other, and common/ holds no I/O, so one shared adapter inside the incident umbrella is not an option. (b) A summarization capability at app/capabilities/summarization/ with api.py, justified only if it passes the three capability tests. TASK-124.5 (incident umbrella move) depends on this task, so the Summarizer moves once, to its final home.
---

created: 2026-09-28 14:55
---
2026-09-28: classify_openai_error today returns OperationResult with error_code UNAUTHORIZED/FORBIDDEN literals. When moving it onto the outbound-client tuple contract, emit ErrorCode registry members (TASK-105.2), using UNAUTHENTICATED for 401 and FORBIDDEN for 403, consistent with the AWS/Google follow-up task.
---
<!-- COMMENTS:END -->
