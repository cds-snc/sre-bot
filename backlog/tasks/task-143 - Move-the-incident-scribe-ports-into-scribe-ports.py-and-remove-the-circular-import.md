---
id: TASK-143
title: >-
  Move the incident scribe ports into scribe/ports.py and remove the circular
  import
status: In Progress
assignee: []
created_date: '2026-10-07 19:46'
updated_date: '2026-10-07 20:41'
labels:
  - incident
  - refactor
dependencies: []
priority: medium
ordinal: 341000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical refactor, standalone PR off main, outside Stack H. TextGenerator (status_update.py) and IncidentDocumentStore and IncidentReportLinkLookup (service.py) are Protocols declared in the service modules that consume them. providers.py imports them from those modules, and the services import providers for their default adapters, so the cycle is worked around with three function-level imports (status_update._default_generator, service.py:294 and :355). Move the three Protocols to packages/incident/scribe/ports.py, import them from there in providers, services, adapters and tests, and import providers at module top in the services. No behaviour change. Stack H rebases onto it after it merges.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 TextGenerator, IncidentDocumentStore and IncidentReportLinkLookup are defined only in packages/incident/scribe/ports.py
- [x] #2 packages/incident/scribe has no function-level imports (ruff --select PLC0415 clean on the package)
- [x] #3 No behaviour change: existing scribe tests pass with only import paths updated
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Survey (worktree off origin/main aca15521):
- Definitions: TextGenerator (status_update.py:60), IncidentDocumentStore (service.py:224), IncidentReportLinkLookup (service.py:243); all @runtime_checkable Protocols.
- Importers: providers.py:13-14; tests test_incident_scribe_slack_adapter_lookup.py:10, test_incident_scribe_conversation_draft.py:14-17, test_incident_scribe_providers_document_store.py:12-14. Adapters (google_docs, slack, text_generation) implement them structurally and do not import them; platforms/entrypoints do not reference them.
- PLC0415 on the package: exactly 3 hits (service.py:294, service.py:355, status_update.py:337), all importing providers.
- Cycle: providers -> adapters/{google_docs,slack,text_generation} -> domain, integrations, infrastructure only; none import service/status_update. Once providers imports ports instead of the services, services -> providers is acyclic.

Steps:
1. Create packages/incident/scribe/ports.py with the three Protocols moved verbatim (runtime_checkable, docstrings), importing OperationResult and DocumentField/DocumentSection/DraftWriteResult/SectionDraft from domain.
2. service.py: delete the two Protocols, import them from ports, add top-level `from packages.incident.scribe import providers` and replace the two function-level imports with providers.get_incident_report_link_lookup() / providers.get_incident_document_store(). Module-attribute access keeps existing monkeypatch.setattr(providers, ...) tests working unchanged. Drop now-unused Protocol/runtime_checkable/Mapping imports.
3. status_update.py: same for TextGenerator and _default_generator (providers.get_status_update_text_generator()); drop the workaround comment.
4. providers.py: import IncidentReportLinkLookup and TextGenerator from ports.
5. Tests: repoint the three Protocol imports above to ports; no other test edits.
6. README.md in scribe: update the Interfaces row/text that says the Protocols live in service.py/status_update.py to ports.py.
7. ruff check --fix + ruff format; gates: ruff, PLC0415 on package, lint-imports, mypy (diff vs clean main), full non-smoke pytest (diff FAILED vs clean main).

Size: ~6 files + 3 test import lines, <100 LOC moved, single subsystem, purely mechanical.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch refactor/incident-scribe-ports (worktree /tmp/wt-scribe-ports, rebased on origin/main 187a76c5). Uncommitted, awaiting human commit/PR.

Changes:
- New packages/incident/scribe/ports.py: IncidentDocumentStore, IncidentReportLinkLookup, TextGenerator moved verbatim (runtime_checkable).
- service.py / status_update.py: Protocols removed, imported from ports; top-level `from packages.incident.scribe import providers`; the 3 function-level imports replaced by providers.get_*() (attribute access keeps monkeypatch.setattr(providers, ...) tests unchanged).
- providers.py imports the Protocols from ports (no longer imports the services; cycle gone).
- 3 tests: Protocol imports repointed to ports only.
- scribe README: interface locations updated.
Note: importing service/status_update now eagerly loads providers + adapters (previously lazy on first default use).

Evidence (from app/ in worktree):
- ruff check: All checks passed; ruff format --check: 824 files already formatted
- ruff --select PLC0415 packages/incident/scribe: All checks passed
- lint-imports: 10 kept, 0 broken
- mypy: 57 errors in 20 files, identical error list to clean main (none in scribe)
- pytest tests --ignore=tests/smoke: 6 failed, 3920 passed; FAILED list identical to clean main (pre-existing: 3 tests/modules/webhooks/test_webhooks_aws_sns.py, 3 tests/unit/infrastructure/directory/test_google.py)
<!-- SECTION:NOTES:END -->
