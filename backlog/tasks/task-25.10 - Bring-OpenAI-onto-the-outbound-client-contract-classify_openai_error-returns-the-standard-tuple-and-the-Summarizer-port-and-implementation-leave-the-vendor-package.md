---
id: TASK-25.10
title: >-
  Bring OpenAI onto the outbound-client contract: classify_openai_error returns
  the standard tuple, and the Summarizer port and implementation leave the
  vendor package
status: To Do
assignee: []
created_date: '2026-09-18 16:51'
updated_date: '2026-09-24 20:10'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-106
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/openai/client.py
  - app/integrations/openai/summarizer.py
  - app/packages/incident_draft/service.py
  - app/packages/incident_summary/service.py
  - decisions/plugin-architecture.md
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

CONSUMERS (re-grep): packages/incident_draft/service.py and packages/incident_summary/service.py. Both import Summarizer and get_summarizer from integrations.openai. packages/incident_summary/settings.py refers to integrations.openai.settings in prose.

DESIGN QUESTION FOR THE PLANNER (raise it in chat, do not decide it in the plan). Summarizer is a port with two feature consumers. Options:
- a business-agnostic infrastructure service (Path A, decisions/layers.md: promote on the second consumer);
- a capability package (decisions/capability-packages.md, still Draft);
- a per-feature adapter in each consumer.
The choice decides where OpenAISummarizer and its parsing helpers live. The vendor package keeps only the client factory, classification and settings.

TARGET. integrations/openai/ exports build_openai_client (timeout plus a retry policy set once at construction, stated explicitly), classify_openai_error returning the standard tuple, and settings. The Summarizer port and implementation live in their decided owner, doing try/except + classify and building OperationResult. Both features are repointed with behaviour unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/openai/ contains only __init__.py, client.py and settings.py; classify_openai_error returns (OperationStatus, error_code, retry_after); every openai entry in bin/baselines/vendor_package_contract.txt is removed
- [ ] #2 The Summarizer port and OpenAI implementation live in the owner the human decided; incident_draft and incident_summary are repointed with unchanged behaviour covered by their existing tests
- [ ] #3 The OpenAI client's retry policy is explicit at construction (or explicitly none, with the reason recorded), alongside its timeout
- [ ] #4 Classification tests cover each mapped HTTP status family and Retry-After, plus one unmapped exception propagating; no 'from __future__ import annotations' remains in touched files
- [ ] #5 decisions/outbound-clients.md no longer lists OpenAI as a tolerated divergence; ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:10
---
2026-09-24 (human decision): the Summarizer's home is decided during this task's planning. decisions/plugin-architecture.md narrows the options to two, and app/infrastructure/ is not one of them (hosting-only). (a) Per-subdomain adapters: features/incident/draft and features/incident/summary each own a small adapters/openai.py behind their own port. Subdomains may not import each other, and common/ holds no I/O, so one shared adapter inside the incident umbrella is not an option. (b) A summarization capability at app/capabilities/summarization/ with api.py, justified only if it passes the three capability tests. TASK-124.5 (incident umbrella move) depends on this task, so the Summarizer moves once, to its final home.
---
<!-- COMMENTS:END -->
