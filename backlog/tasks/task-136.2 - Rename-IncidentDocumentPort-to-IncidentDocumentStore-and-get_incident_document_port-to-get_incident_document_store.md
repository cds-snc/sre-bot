---
id: TASK-136.2
title: >-
  Rename IncidentDocumentPort to IncidentDocumentStore and
  get_incident_document_port to get_incident_document_store
status: Done
assignee: []
created_date: '2026-10-02 00:37'
updated_date: '2026-10-02 15:09'
labels:
  - plugin-architecture
  - naming
milestone: m-7
dependencies:
  - TASK-136.1
references:
  - decisions/feature-packages.md
  - app/packages/incident_draft/service.py
parent_task_id: TASK-136
priority: medium
ordinal: 299000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-136. Applies the Protocol naming rule to the incident_draft document interface: IncidentDocumentPort (packages/incident_draft/service.py) becomes IncidentDocumentStore and the provider function get_incident_document_port becomes get_incident_document_store, with every user rewritten and no alias at the old names. Renamed here rather than deferred to TASK-135 or TASK-38, which still own IncidentChannelPort and get_incident_channel_port (untouched by this slice). Mechanical rename only. Decided by the human in chat on 2026-10-02.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 IncidentDocumentPort is renamed to IncidentDocumentStore and get_incident_document_port to get_incident_document_store in packages/incident_draft (service, providers, adapters/google_docs, README, tests); rg finds neither old name in app/, and no alias exists
- [x] #2 IncidentChannelPort and get_incident_channel_port are untouched: their identifier occurrences in app/ are identical before and after
- [x] #3 Docstrings and README text in the touched incident_draft files describe the document interface (and the Summarizer interface) as 'interface' instead of 'port'
- [x] #4 No behaviour change: the TASK-36 legacy_surface suite is green with no assertion change
- [x] #5 Full CI sequence from app/ passes: ruff check, make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test, and mypy shows no new errors in touched files
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Applies the Protocol naming rule recorded by TASK-136.1 (roles, not patterns; 'interface' in prose) to the incident_draft document interface. Mechanical rename; decisions/feature-packages.md (providers.py wires Protocols into the service) is unchanged by it.

Decisions (settled in chat 2026-10-02, not reopened here):
- IncidentDocumentPort becomes IncidentDocumentStore and get_incident_document_port becomes get_incident_document_store, here and now (not deferred to TASK-135 or TASK-38). No alias at the old names.
- IncidentChannelPort and get_incident_channel_port are untouched (TASK-135 owns them), including in the files this slice edits.
- The concrete GoogleDocsIncidentDocument and the DocumentSection/DraftWriteResult types keep their names; only the Protocol, the provider function and the test stub change.
- Prose 'Summarizer port' and 'document port' in the touched incident_draft files becomes 'interface' (the Summarizer class itself is not renamed).

Found call sites (rg IncidentDocumentPort|get_incident_document_port, 2026-10-02; no reference in Makefile, .github, pyproject, app/bin or decisions/; closed backlog tasks 26.1.2 and 25.1.6.6 and TASK-135 text mention the old name and are not edited):
- packages/incident_draft/service.py: :203 class IncidentDocumentPort(Protocol) (runtime_checkable); :250 parameter annotation 'documents: IncidentDocumentPort | None'; :260 docstring; :5 module docstring; :281 and :283 lazy 'from packages.incident_draft.providers import get_incident_document_port' and its call; :7 and :262 prose 'Summarizer port'.
- packages/incident_draft/providers.py: :16 'def get_incident_document_port() -> GoogleDocsIncidentDocument' (lru_cache) and its docstring :17.
- packages/incident_draft/adapters/google_docs.py: :1 module docstring, :144 class docstring.
- packages/incident_draft/platforms/slack.py: :10 docstring 'via the document port'; :128 'channel: Port reading the incident channel.' (prose only; the channel names stay).
- packages/incident_draft/README.md: :297 ('IncidentDocumentPort Protocol and the Summarizer port'), :301 ('Summarizer port'), :303 ('DI wiring for the document port').
- Tests: tests/unit/packages/incident_draft/test_incident_draft_service.py :61 class _StubDocumentPort, :62 docstring, 41 construction sites (:102 to :851); tests/unit/packages/incident_draft/test_incident_draft_adapter.py:1 docstring. No test patches get_incident_document_port or imports IncidentDocumentPort by name.
- Not found, so not in scope: any other importer of providers.get_incident_document_port (only service.py:281).

Steps:
1. Tests first: add tests/unit/packages/incident_draft/test_incident_draft_providers_document_store.py: the service module exposes IncidentDocumentStore, the providers module exposes get_incident_document_store, neither module has the old names, and get_incident_document_store (with GoogleDocsIncidentDocument patched or constructed with its existing default, matching how test_incident_draft_adapter.py builds it) returns an instance satisfying isinstance(..., IncidentDocumentStore). It fails until step 2.
2. service.py: rename the Protocol and update annotation, lazy import and call; reword the three docstring lines. providers.py: rename the function and docstring. adapters/google_docs.py: two docstrings.
3. platforms/slack.py: the two docstring lines above (no name touched). README.md: three lines.
4. Rename the test stub to _StubIncidentDocumentStore across test_incident_draft_service.py (single-token replace, 41 sites) and fix the docstrings in it and in test_incident_draft_adapter.py, in place.
5. rg for the old names in app/ returns nothing; rg -c 'IncidentChannelPort|get_incident_channel_port' over app/ is identical to the count taken before the change (record both numbers in the notes).

Test matrix: existing suites guard behaviour (test_incident_draft_service.py, test_incident_draft_adapter.py, test_incident_draft_slack.py, tests/integration/legacy_surface); the one new test pins the new public names and absence of the old. No new behaviour tests.

Verify (from app/): uv run ruff check .; make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test; mypy on touched files (no new errors; the runtime_checkable Protocol is used by service.py's default resolution, which mypy checks); rg -n 'IncidentDocumentPort|get_incident_document_port|_StubDocumentPort' /workspace/app (empty); legacy_surface green without assertion changes.

AC map: #1 steps 1-4 + new test + rg; #2 step 5 (before/after count); #3 steps 2-3 (rg -i '\bport\b' on the touched incident_draft files shows only the untouched IncidentChannelPort/get_incident_channel_port identifiers); #4 legacy_surface; #5 gates.

Size: 5 production files (service.py, providers.py, adapters/google_docs.py, platforms/slack.py, README.md), about 20 changed lines; 2 existing test files edited (about 45 lines, mostly the stub token) plus 1 new. One subsystem; well under the gate.
Behaviour: none. The lazy import in service.py:281 resolves the provider by function name at call time, so a missed rename would raise ImportError only on the default-resolution path: the new providers test and the service tests that omit 'documents' cover it.
Blast radius: incident_draft only. Rollback: git revert.
Ordering: merges after TASK-136.1 (both edit incident_draft/platforms/slack.py, lines 127 and 128 are adjacent). TASK-135 (incident reshape) should rebase onto it; it mentions IncidentDocumentPort in its text.

Doubts to verify: (1) service.py:281 is the only caller of get_incident_document_port (rg, expected yes). (2) Nothing resolves the old name by string, for example patch targets or monkeypatch.setattr in tests/integration/legacy_surface/conftest.py (it patches get_incident_channel_port at :186-187 only; re-run rg). (3) The new providers test must not touch Google: confirm GoogleDocsIncidentDocument() construction is lazy (read adapters/google_docs.py __init__) or patch it, otherwise assert on the function's return annotation via get_type_hints instead.

Changes made at implementation (2026-10-02):
- The new test file does not assert the absence of the old names. Writing them as string literals put both old names back into app/, which contradicts AC #1 and this plan's own verify line (rg over app/ empty). Absence is proven by rg instead.
- The new test file gained a default-resolution test instead: all 40 draft_incident_document calls in test_incident_draft_service.py inject documents=, so the lazy import of the provider in service.py had no coverage (the plan assumed it had).
- 'from __future__ import annotations' removed from the three touched files that carried it (adapters/google_docs.py, test_incident_draft_service.py, test_incident_draft_adapter.py): deprecated under the CPython 3.14 baseline, and deprecated constructs in touched files are removed in the same task.
- Doubts resolved: (1) service.py is the only caller of the provider function; (2) nothing resolves the old name by string; (3) GoogleDocsIncidentDocument has no __init__, so the real factory runs in the test without touching Google.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed (mechanical rename, no behaviour change):
- packages/incident_draft/service.py: Protocol IncidentDocumentPort -> IncidentDocumentStore (class, parameter annotation, lazy provider import and call, docstrings); 'Summarizer port' -> 'Summarizer interface' in two docstrings.
- packages/incident_draft/providers.py: get_incident_document_port -> get_incident_document_store (still lru_cache, still returns GoogleDocsIncidentDocument). No alias at either old name.
- packages/incident_draft/adapters/google_docs.py: two docstrings; removed the deprecated 'from __future__ import annotations'.
- packages/incident_draft/platforms/slack.py: two docstring lines ('document interface', 'Interface reading the incident channel'); no identifier touched.
- packages/incident_draft/README.md: three lines.
- tests/unit/packages/incident_draft/test_incident_draft_service.py: stub _StubDocumentPort -> _StubIncidentDocumentStore (41 sites, one call reflowed by ruff format), docstring, future-import removed. test_incident_draft_adapter.py: module docstring, future-import removed. No assertion changed in either.
- New: tests/unit/packages/incident_draft/test_incident_draft_providers_document_store.py (2 tests: the default factory returns the cached Google Docs adapter satisfying the Protocol; the service reads through the provider's store when none is injected). The first version failed before the rename (AttributeError on get_incident_document_store), then passed.

Evidence (2026-10-02, from app/):
- AC1: rg -n 'IncidentDocumentPort|get_incident_document_port|_StubDocumentPort' /workspace/app -> no match.
- AC2: rg -c 'IncidentChannelPort|get_incident_channel_port' over app/ -> 53 occurrences in 13 files before and after.
- AC3: rg -n -i '\bport\b' on the 5 touched production files and 3 test files -> no match.
- AC4: pytest tests/integration/legacy_surface -> 17 passed; no file under tests/integration changed.
- AC5: ruff check . -> All checks passed. make fmt-ci check-sdk-typing check-vendor-package-contract check-aws-platform-seam check-runtime-imports check-import-contracts test -> rc 0; 783 files already formatted; import contracts 8 kept, 0 broken; 2858 passed and 760 passed. mypy on packages/incident_draft plus the two edited test files: 33 errors before (HEAD contents) and 33 after, identical once line numbers are stripped; all pre-existing (union-attr on OperationResult.data in tests, infrastructure/i18n, integrations/openai settings). The new test file adds none.

Not touched, by scope: tests/unit/packages/incident_draft/test_incident_draft_slack.py:36 still says 'fake incident channel port' (channel prose, TASK-135's file set).

For the human: work is uncommitted on main; cut the branch, review, PR, then move to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-02 00:42
---
Plan approved 2026-10-02 (Guillaume Charest, in session), as written.
---
<!-- COMMENTS:END -->
