---
id: TASK-22.5
title: >-
  Delete deprecated infrastructure/clients + empty app/clients; close the
  layers.md divergence
status: To Do
assignee: []
created_date: '2026-07-29 21:11'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.4
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - app/tests/unit/infrastructure/services/test_narrow_slice_providers.py
parent_task_id: TASK-22
priority: high
ordinal: 108000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (final) of TASK-22 (parent). After slices 22.1-22.4 have migrated all six production consumers, remove the deprecated trees and close the tolerated divergence.

Steps:
1. Verify zero production consumers remain: grep -rn 'infrastructure.clients' app --include='*.py' returns only deleted-in-this-PR test files. Run make audit-client-usage-matrix and confirm zero infrastructure/clients consumers.
2. Delete app/infrastructure/clients/ entirely (aws, google_workspace, maxmind = 72 files) and the empty app/clients/ directory.
3. Delete the deprecated-tree tests under app/tests/unit/infrastructure/clients/ (already unit-located).
4. Repoint app/tests/unit/infrastructure/services/test_narrow_slice_providers.py:13 (currently imports infrastructure.clients.maxmind.client.MaxMindClient) onto the ported integrations/maxmind client from slice 22.1, or delete that specific narrow-slice assertion if it no longer applies.
5. If TASK-19's freeze-check baseline exists by now, empty the deprecated-import baseline; if TASK-19 has not landed, note it (baseline is a no-op until then).
6. Update decisions/layers.md Migration section: remove 'infrastructure/clients/ consumers' from the tolerated-divergences list; confirm the Checks item 'No directory named clients/ exists under app/' now passes.

Do NOT resolve _next twins (TASK-23) or apply the raise/classify contract (TASK-25) here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/clients/ and app/clients/ no longer exist; decisions/layers.md check 'no directory named clients/ under app/' passes
- [ ] #2 make audit-client-usage-matrix reports zero consumers of infrastructure/clients/
- [ ] #3 test_narrow_slice_providers.py no longer imports the deleted infrastructure.clients.maxmind; deprecated-tree tests under tests/unit/infrastructure/clients/ removed
- [ ] #4 decisions/layers.md Migration section no longer lists infrastructure/clients/ consumers as a tolerated divergence; full test suite green
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Behavior-neutral overall; deprecated-import baseline emptied if TASK-19 landed; PR references decisions/layers.md
<!-- DOD:END -->
