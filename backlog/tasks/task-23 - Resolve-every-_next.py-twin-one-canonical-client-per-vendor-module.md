---
id: TASK-23
title: 'Resolve every _next.py twin: one canonical client per vendor module'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 21:29'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.5
references:
  - decisions/outbound-clients.md
  - 'https://github.com/cds-snc/sre-bot/issues/1277'
priority: high
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/outbound-clients.md (Migration: "_next.py twins resolve into this shape"). Today app/integrations/ contains a fourth client generation: _next.py twins beside originals (aws/client_next.py, aws/dynamodb_next.py, aws/identity_store_next.py, google_workspace/google_directory_next.py, google_workspace/gmail_next.py, google_workspace/google_service_next.py).

Steps:
1. For each twin pair, diff the original vs _next and pick the survivor per the decided contract (clients raise typed SDK exceptions, SDK-native retry configured at construction, no hand-rolled retry, no OperationResult in clients).
2. Rename the survivor to the canonical name (no _next suffix), migrate its consumers, delete the loser. One vendor per PR.
3. Where neither twin matches the contract, converge on the closer one and fix it in the same PR (contract enforcement itself completes in task-25).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 find app/integrations -name "*_next.py" returns zero files
- [ ] #2 Each vendor module has exactly one client construction path
- [ ] #3 All consumers import the canonical module; tests pass per vendor PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No behavior change observable from feature code (existing tests green)
- [ ] #2 PR series references decisions/outbound-clients.md
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PREREQUISITE: TASK-22.5 Done. All 6 production consumers already point at the integrations/ modules (including the _next twins); infrastructure/clients/ is deleted. This task is a mechanical de-duplication + rename pass. It is behavior-neutral and does NOT change return types (clients still return OperationResult until TASK-25).

TWIN INVENTORY (6, from find app/integrations -name "*_next.py"): aws/client_next.py, aws/dynamodb_next.py, aws/identity_store_next.py, google_workspace/google_service_next.py, google_workspace/gmail_next.py, google_workspace/google_directory_next.py.

AWS HAS THREE GENERATIONS, not two: original client.py, the executor-style _next trio (hand-rolled retry via client_next._calculate_retry_delay + time.sleep, returns OperationResult), and shield.py (AWSShield: SDK-native Config(retries=...) + classify). SURVIVOR PRINCIPLE per decisions/outbound-clients.md: prefer the generation whose retry is SDK-native over any hand-rolled loop. This task keeps ONE module per vendor concern and drops the _next suffix; it does NOT yet convert shape to factory+classify (that is TASK-25). Leave shield.py in place for TASK-25 to fold, but ensure the canonical modules expose a single construction path.

PR SLICES (one vendor per PR, each behavior-neutral):
PR A - AWS: git mv the modules the 22.x consumers were wired to (dynamodb_next -> dynamodb, identity_store_next -> identity_store) to canonical names; repoint infrastructure/storage/service.py and the access-sync provider/adapter imports; delete the losing duplicate (client.py residue and any dead twin). Confirm only one boto3 construction path is referenced by the canonical modules.
PR B - Google: git mv google_service_next -> google_service, gmail_next -> gmail, google_directory_next -> google_directory; repoint the directory factory/google adapter (migrated in 22.4). Modules with zero consumers per the usage matrix (e.g. gmail) may simply be deleted rather than renamed.

TEST MIGRATION (parent AC#5 rule continues): every touched vendor test relocates from tests/integrations/ or tests/modules/ into tests/unit/integrations/<vendor>; legacy trees only shrink.

VERIFY: find app/integrations -name "*_next.py" returns zero (AC#1); each vendor exposes exactly one client construction path (AC#2); consumers import the canonical module and each per-vendor PR is green (AC#3); import-linter (TASK-18) green.

SIZE GATE: mechanical import-path churn across ~2 vendors, no logic change -> each vendor PR is well under the ~400 LOC / ~10 file gate. No further decomposition required; ship as 2 sequential PRs under this task.

RISKS: pure rename/repoint - watch for lingering references in DI/providers, tests, and __init__ re-exports; ripgrep both the original and _next names after each PR. Non-goal: any contract/return-type change (deferred to TASK-25).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-29 21:12
---
Upstream dependency repointed from TASK-22 to its final subtask TASK-22.5 (the slice that actually deletes infrastructure/clients/). TASK-22's subtasks (22.1-22.5) wire consumers to the integrations/ modules AS THEY EXIST TODAY, including the _next.py twins. This task then renames those survivors to canonical names and re-migrates the same consumers — an intentional, conflict-free second touch in a later PR of the same sprint. Note the MaxMind handoff: TASK-22.1 leaves an OperationResult client coexisting beside the legacy tuple geolocate()/healthcheck() in integrations/maxmind; unifying those two shapes is TASK-25, not this task.
---
<!-- COMMENTS:END -->
