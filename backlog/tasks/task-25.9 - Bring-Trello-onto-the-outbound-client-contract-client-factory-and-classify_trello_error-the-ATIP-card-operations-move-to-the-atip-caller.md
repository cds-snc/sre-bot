---
id: TASK-25.9
title: >-
  Bring Trello onto the outbound-client contract: client factory and
  classify_trello_error; the ATIP card operations move to the atip caller
status: To Do
assignee: []
created_date: 2026-09-18 16:51
updated_date: '2026-10-23T17:32:00Z'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies: []
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/trello/client.py
  - app/modules/atip/atip.py
  - decisions/plugin-architecture.md
  - https://github.com/cds-snc/sre-bot/issues/1605
parent_task_id: TASK-25
priority: low
ordinal: 242000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every vendor in app/integrations/ conforms to decisions/outbound-clients.md.

TODAY. app/integrations/trello/client.py (28 lines) uses the untyped trello.TrelloApi (import marked type: ignore). It exposes get_trello_client plus two ATIP business functions, add_atip_card_to_trello and get_atip_inbox_list_id_in_board. It reads settings at import time (client.py:7), sets no explicit timeout or retry, and has no classify_trello_error. Settings live in integrations/trello/settings.py (TrelloSettings: trello_app_key, trello_token, trello_atip_board); TASK-111.12 moves that slice onto the configuration files.

CONSUMER (re-grep): modules/atip/atip.py:499 (add_atip_card_to_trello), the only one. TASK-39 rebuilds atip into app/features/atip/, and its adapters/ inherit the card operations, so keep the legacy module's change minimal.

DESIGN INPUT FOR THE PLANNER. The TrelloApi library is untyped and exposes no timeout or retry knob. Decide between keeping it (and recording how the timeout and retry rules are met, or where they are a tolerated divergence) and calling Trello's REST API through a typed HTTP client built by the factory. sdk-typing.md prefers typed surfaces but does not require one where none exists.

OUT OF SCOPE. trello_atip_board is an atip feature value, not a vendor setting: TASK-39 moves it into the atip slice.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/trello/ exports only a client factory and classify_trello_error; the ATIP card operations live with the atip caller, which calls the client inside try/except + classify
- [ ] #2 The client's timeout and retry policy are explicit at construction, or the gap is recorded as a named, owned divergence in decisions/outbound-clients.md
- [ ] #3 No import-time settings read remains in the vendor package; classification tests cover mapped failure families plus one unmapped exception propagating
- [ ] #4 ruff, mypy, pytest tests --ignore=tests/smoke and make check-vendor-package-contract pass, with output recorded in notes
<!-- AC:END -->
