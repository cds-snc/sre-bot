---
id: TASK-140.3
title: >-
  Resolve a conversation to its incident id in packages/incident/core over the
  legacy incidents table
status: In Progress
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-07 13:44'
labels:
  - incident
dependencies:
  - TASK-140.1
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 322000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Core exposes find_incident_for_conversation (the name in decisions/incident-management.md) through core/api.py as a standalone lookup Protocol, returning the incident's existing UUID or a classified refusal. The interim adapter in core/adapters/ reads the legacy incidents table by channel id through the outbound DynamoDB client (integrations.aws), paging through the whole scan and refusing a channel that maps to more than one incident (the legacy lookup also pages, but takes the first match blindly). TASK-38.1's store later replaces the adapter behind the same interface. Packages never import modules/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 core/api.py exposes find_incident_for_conversation returning OperationResult with the incident UUID, or a classified not-an-incident refusal
- [x] #2 The adapter pages through the whole scan and is unit-tested with botocore Stubber across two pages
- [x] #3 lint-imports keeps packages from importing modules/; ruff, mypy (no new errors in touched files) and pytest pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Approach
core/api.py gains an `IncidentLookup` Protocol whose one method is `find_incident_for_conversation(conversation_id: str) -> OperationResult[str]`, a cached provider `get_incident_lookup()`, and a module-level `find_incident_for_conversation(conversation_id)` that delegates to the provider. Commands call the function. Tests and subdomains that inject collaborators pass a fake `IncidentLookup`. TASK-38.1's store later implements the same method and the provider switches to it.
The interim adapter lives in core/adapters/legacy_incidents.py. It builds a boto3 dynamodb client with integrations.aws.client.get_aws_client. It cannot reuse packages.aws_platform's DynamoDBAdapter because contract (f) feature-independence forbids packages.incident -> packages.aws_platform, and the record retires that adapter in TASK-38.5. The adapter scans the `incidents` table with the scan paginator, filters on channel_id, projects only `id`, and reads every page.

## Steps
1. app/contracts/operations/codes.py: register NOT_AN_INCIDENT and AMBIGUOUS_INCIDENT_CONVERSATION (one line each, alphabetical).
2. app/packages/incident/core/adapters/legacy_incidents.py (new, ~80 LOC):
   - LegacyIncidentTableLookup(client: DynamoDBClient) implements find_incident_for_conversation.
   - A blank conversation id returns NOT_FOUND/NOT_AN_INCIDENT without an SDK call.
   - get_paginator("scan").paginate(TableName="incidents", FilterExpression="channel_id = :channel_id", ExpressionAttributeValues={":channel_id": {"S": id}}, ProjectionExpression="#id", ExpressionAttributeNames={"#id": "id"}) collects ids from every page.
   - Results: 0 ids gives NOT_FOUND + NOT_AN_INCIDENT. 1 id gives SUCCESS(data=uuid). More than 1 gives PERMANENT_ERROR + AMBIGUOUS_INCIDENT_CONVERSATION, with a warning that logs the count.
   - ClientError/BotoCoreError go through classify_aws_error. A store-side NOT_FOUND (ResourceNotFoundException, a missing table) is remapped to PERMANENT_ERROR so that NOT_FOUND always means "not an incident". The botocore error_code is kept. Messages are generic. A warning `incident_lookup_failed` logs conversation_id, status and error_code. Unclassified exceptions propagate.
   - The table name is a module constant mirroring terraform/dynamodb.tf `incidents`, with a comment noting the adapter is interim until TASK-38.
   - build_legacy_incident_lookup() builds the client in-account (SERVICE_ROLE_MAP.get("dynamodb") or None, standard retries, since reads are replay-safe), at call time, never at import.
3. app/packages/incident/core/api.py (+~40 LOC): add the IncidentLookup Protocol (runtime_checkable), get_incident_lookup() (lru_cache), find_incident_for_conversation(), and extend __all__. Update the module docstring.
4. app/packages/incident/README.md: update the core/ row so it lists the new names and adapters/legacy_incidents.py.

## Tests (TDD, written first)
New file tests/unit/packages/incident/core/test_incident_core_incident_find.py uses a real boto3 dynamodb client with dummy credentials and botocore Stubber. It validates request params against the service model.
- happy, two pages: page 1 has no match and a LastEvaluatedKey; page 2 has the match. Asserts the UUID, that page 2's request carries ExclusiveStartKey, and that no responses are pending (AC2).
- not an incident, two pages: neither page matches. Asserts NOT_FOUND + NOT_AN_INCIDENT (AC1).
- ambiguous: one match on each page gives PERMANENT_ERROR + AMBIGUOUS_INCIDENT_CONVERSATION. This also proves that pagination continues after the first match.
- boundary: a blank or whitespace conversation id gives NOT_AN_INCIDENT and the Stubber shows no call.
- failure: ThrottlingException on page 2 gives TRANSIENT_ERROR with retry_after. ResourceNotFoundException gives PERMANENT_ERROR, not NOT_FOUND. AccessDeniedException gives UNAUTHORIZED. EndpointConnectionError gives TRANSIENT_ERROR. In every case the message has no provider text.
- builder: build_legacy_incident_lookup asks get_aws_client for "dynamodb" (monkeypatched) and the module builds nothing at import.
Update tests/unit/packages/incident/core/test_incident_core_api_surface.py:
- the __all__ list
- the Protocol signature carries only str -> OperationResult[str]
- the provider is cached and built on the legacy adapter
- find_incident_for_conversation delegates to the provider (fake lookup)

## AC traceability
- AC1: steps 1 to 3. Tests: happy, not-an-incident, ambiguous, boundary, and the surface tests.
- AC2: step 2. Tests: the two-page happy, not-found and ambiguous tests.
- AC3: steps 2 and 3 import only integrations from adapters/ (contract e) and nothing from modules/ (contract g). Gates: ruff, mypy on touched files, lint-imports, pytest tests --ignore=tests/smoke.

## Size
4 production files, ~130 production LOC, one subsystem (packages.incident.core) plus a 2-line registry entry. Under the gate.

## Assumptions and doubts
- The legacy channel_id attribute is stored as S and is the Slack channel id. Verified in db_operations.lookup_incident and terraform (hash key id S, no GSI).
- The task description says the legacy lookup "reads only the first page". On main, lookup_incident -> DynamoDBAdapter.scan already pages through get_paginator (since #1487). The real difference is that the legacy lookup returns the first match blindly, while this one detects duplicates. Description to be corrected through the CLI.
- A full scan costs read capacity on a 2-RCU table on every command. The table is small, and TASK-38's store replaces the scan. No GSI here, per the record.

## Blast radius and rollback
Additive. Nothing calls the lookup until TASK-140.5. One git revert removes it. There is no terraform or IAM change, because the bot already scans `incidents`.

## Decisions (2026-10-07, user)
- Data path: an interim direct adapter over integrations.aws in core/adapters/, deleted by TASK-38.1. Rejected alternatives:
  - Pulling TASK-27.2's capped whole-table list forward: it would need a new contract (b) exemption, the incidents table may outgrow the cap, and it would cross a second subsystem.
  - Waiting for TASK-27.1/27.2/108/109/38.1: it would block TASK-140.5 to 140.7 on the whole storage sequence.
  - Reusing the aws_platform adapter: it would need a new contract (f) exemption, which the shrink-only rule forbids.
- Interface: a standalone lookup Protocol (IncidentLookup.find_incident_for_conversation) plus a provider and a module-level function. This is the permanent part. TASK-38.1 serves it from the store.
- End-state resolution (index record, key read, or another option) is left to TASK-38.1 planning, which must avoid a scan. A note was added to TASK-38.1.
- TASK-140.4: a note was added about the contract (b) problem with the job_status_store pattern.
- Duplicates are refused with PERMANENT_ERROR + AMBIGUOUS_INCIDENT_CONVERSATION. A store-side NOT_FOUND is reported as PERMANENT_ERROR. The table name is a module constant in the adapter. The task description is corrected about legacy paging.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-07 implementation (TDD: tests failed at collection before the adapter existed, then green).
Files: app/packages/incident/core/adapters/legacy_incidents.py (new), app/packages/incident/core/api.py, app/contracts/operations/codes.py (NOT_AN_INCIDENT, AMBIGUOUS_INCIDENT_CONVERSATION), app/packages/incident/README.md; tests: app/tests/unit/packages/incident/core/test_incident_core_incident_find.py (new, Stubber across two pages), test_incident_core_api_surface.py.
Evidence (from app/):
- uv run ruff check . -> All checks passed!
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 57 errors in 20 files, 0 in touched files; uv run mypy packages/incident/core contracts/operations/codes.py -> Success: no issues found in 7 source files
- uv run lint-imports -> Contracts: 10 kept, 0 broken
- uv run pytest tests/unit/packages/incident/core -> 62 passed
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3756 passed; the 6 (tests/modules/webhooks/test_webhooks_aws_sns.py x3, tests/unit/infrastructure/directory/test_google.py x3) are pre-existing single-process order leaks (TASK-90) and pass in isolation (111 passed).
<!-- SECTION:NOTES:END -->
