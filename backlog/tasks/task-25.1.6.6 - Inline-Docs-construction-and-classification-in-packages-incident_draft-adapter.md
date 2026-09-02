---
id: TASK-25.1.6.6
title: Inline Docs construction and classification in packages incident_draft adapter
status: To Do
assignee: []
created_date: '2026-09-02 15:01'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.5.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 137000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Docs counterpart of TASK-25.1.5.1 (which does the same for that adapter's two Drive call sites). Together they make app/packages/incident_draft/adapters/google_docs.py the first fully compliant Google boundary in the repo.

app/packages/incident_draft/adapters/google_docs.py is a real packages/<feature>/adapters/ file per decisions/feature-packages.md - i.e. it is exactly where decisions/outbound-clients.md says the boundary belongs ("the adapter is the boundary"). Today it calls integrations.google_workspace.google_docs.get_document / batch_update - module-level passthroughs that add nothing over the SDK - and performs ZERO try/except of its own, relying on the vendor package's execute_google_api_request to classify. That is the deviation TASK-25.1.6 exists to remove.

SCOPE: repoint those Docs call sites onto integrations.google_workspace.client.get_docs_service(scopes=..., delegated_user_email=...), call service.documents().get(...) / .batchUpdate(...) directly against the stub-typed DocsResource, and give the adapter its own try/except + classify_google_error. Translate responses into the adapter's own typed shapes rather than passing raw dicts inward (decisions/sdk-typing.md item 3).

REAL DESIGN WORK, NOT A MECHANICAL REWIRE (flagged on TASK-25.1.6, 2026-09-01): the adapter's read_sections / write_draft_document currently express failure as None / [] returns. Deciding how classify_google_error's OperationStatus maps onto those - or whether they should return OperationResult instead - is new business logic and is the substance of this task.

SIZE WARNING: app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py is 1704 lines with 44 patch(...) sites keyed to the current google_docs module boundary. TASK-25.1.5.1 already splits that boundary once for Drive and is expected to leave a shared Resource-fake helper behind; reuse it rather than reinventing the chain per test. Expect the test rework, not the production change, to dominate this PR.

AFTER THIS TASK: integrations/google_workspace/google_docs.py::get_document and batch_update have one remaining consumer group - the legacy modules/incident/* files owned by the incident Docs adapter task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 packages/incident_draft/adapters/google_docs.py builds its Docs calls from integrations.google_workspace.client.get_docs_service and calls documents().get / documents().batchUpdate directly on the stub-typed DocsResource; it no longer imports integrations.google_workspace.google_docs
- [ ] #2 The adapter wraps those calls in its own try/except + classify_google_error and no longer depends on execute_google_api_request for any call site
- [ ] #3 The mapping from classify_google_error's OperationStatus onto the adapter's existing None/[] failure contract (read_sections, write_draft_document) is decided explicitly, documented in the notes, and covered by tests for each mapped status
- [ ] #4 Raw Docs response dicts do not cross out of the adapter; responses are translated into the adapter's own typed shapes
- [ ] #5 test_incident_draft_adapter.py is reworked onto the split mock boundary reusing TASK-25.1.5.1's shared Resource fake; every existing behavioural assertion is preserved or has a documented equivalent
- [ ] #6 TASK-25.1.6's call-site inventory is updated to record these Docs sites as discharged, and integrations/google_workspace/google_docs.py's remaining consumers are re-stated
<!-- AC:END -->
