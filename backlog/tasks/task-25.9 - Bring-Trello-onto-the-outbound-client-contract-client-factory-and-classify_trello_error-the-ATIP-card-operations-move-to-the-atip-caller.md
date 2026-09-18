---
id: TASK-25.9
title: >-
  Bring Trello onto the outbound-client contract: client factory and
  classify_trello_error; the ATIP card operations move to the atip caller
status: To Do
assignee: []
created_date: '2026-09-18 16:51'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/layers.md
  - app/integrations/trello/client.py
  - app/modules/atip/atip.py
parent_task_id: TASK-25
priority: low
ordinal: 242000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Created 2026-09-18 (human decision: every vendor conforms to decisions/outbound-clients.md).

TODAY (verified 2026-09-18). app/integrations/trello/client.py (41 lines) uses the untyped trello.TrelloApi (import marked type: ignore). It exposes get_trello_client plus two ATIP business functions, add_atip_card_to_trello and get_atip_inbox_list_id_in_board. It reads settings at import time, sets no explicit timeout or retry, and has no classify_trello_error.

CONSUMER (re-grep): modules/atip/atip.py, the only one. TASK-39 (migrate role, secret, atip) later moves that module, so keep its change minimal.

DESIGN INPUT FOR THE PLANNER. The TrelloApi library is untyped and exposes no timeout or retry knob. Decide between keeping it (and recording how the timeout and retry rules are met, or where they are a tolerated divergence) and calling Trello's REST API through a typed HTTP client built by the factory. sdk-typing.md prefers typed surfaces but does not require one where none exists.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/trello/ exports only a client factory and classify_trello_error; the ATIP card operations live with the atip caller, which calls the client inside try/except + classify
- [ ] #2 The client's timeout and retry policy are explicit at construction, or the gap is recorded as a named, owned divergence in decisions/outbound-clients.md
- [ ] #3 No import-time settings read remains in the vendor package; classification tests cover mapped failure families plus one unmapped exception propagating
- [ ] #4 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->
