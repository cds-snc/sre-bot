---
id: TASK-50
title: Reconcile decisions/testing.md with moto for AWS SDK test substitution
status: To Do
assignee: []
created_date: '2026-07-24 18:30'
updated_date: '2026-07-24 18:32'
labels: []
dependencies:
  - TASK-5.1
references:
  - decisions/testing.md
  - docs/adr/testing-standards.md
  - ADR-REVIEW-AND-MIGRATION-PLAN.md
priority: medium
ordinal: 78000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Context: docs/adr/testing-standards.md (legacy corpus, 2026-05-08, still un-archived pending TASK-10) explicitly blesses moto ('moto for AWS service substitution where the SDK in question is boto3 and the operations require server-side semantics that pure stubs cannot reproduce') as the adapter-seam substitution tool for boto3, alongside respx/pytest-httpx for httpx. The newer decisions/testing.md (Accepted, 2026-07-06 - the intended sole-source-of-truth target of TASK-10) dropped this guidance: it only says 'DynamoDB-Local is permitted for store-semantics tests, marked slow', with no mention of moto, and neither DynamoDB-Local nor moto is actually wired into CI (.github/workflows/ci_code.yml has no DynamoDB-Local service container, no slow marker registered/excluded) or listed as a dependency in app/pyproject.toml. ADR-REVIEW-AND-MIGRATION-PLAN.md (section 5.8) independently flags this exact gap: 'reconcile the tool list (respx/moto recommended but absent)'.

Today every AWS-adjacent unit test (app/tests/unit/infrastructure/clients/aws/*, app/tests/unit/integrations/aws/*) substitutes by hand-monkeypatching the get_boto3_client factory seam with a fake client object returning canned dicts. That pattern works for shape assertions but cannot validate real server-side semantics (DynamoDB ConditionExpression correctness, GSI query behavior, TTL) - which is exactly the gap TASK-5.1's idempotency claim/complete/release conformance suite needs moto (or DynamoDB-Local) to close.

Scope of this task:
1. Decide, in decisions/testing.md, whether moto or DynamoDB-Local (or both, for different cases) is the sanctioned mechanism for tests needing real boto3 server-side semantics, and update the record's wording accordingly (this is an architecture-record edit - route through architecture/feature-architecture mode, not task-planner).
2. If moto is chosen: add moto (scoped to the AWS services actually exercised, e.g. moto[dynamodb]) as a dev-only dependency in app/pyproject.toml with no CI workflow changes required (moto runs in-process, no service container).
3. Register/confirm any pytest markers this decision implies (e.g. slow) in pyproject.toml's strict-markers list if DynamoDB-Local is kept as a parallel option.
4. Scope explicitly excludes migrating the existing passing get_boto3_client-monkeypatch tests wholesale - this task establishes the sanctioned tool and applies it prospectively (starting with TASK-5.1's conformance suite); a mass migration of already-passing tests is separate, unnecessary churn.

This task was discovered while planning TASK-5.1 (idempotency claim/complete/release), which needs this decision resolved before its DynamoDB-backed conformance suite can be implemented.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 decisions/testing.md explicitly names the sanctioned tool(s) for tests requiring real boto3/DynamoDB server-side semantics (ConditionExpression, GSI, TTL), reconciling the moto guidance currently only present in the legacy docs/adr/testing-standards.md
- [ ] #2 If moto is chosen, moto[dynamodb] (or the narrower scope actually needed) is added to app/pyproject.toml [project.optional-dependencies].dev with an exact pinned version resolved via uv add --dev, and uv.lock is refreshed
- [ ] #3 TASK-5.1's DynamoDB-backed conformance suite can cite this task's decision instead of carrying its own open moto-vs-DynamoDB-Local conflict comment
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 18:32
---
decisions/testing.md updated directly at user request to reconcile the moto/respx guidance (AC#1 wording now present in the Decision section's Integration bullet and Doubles line, plus a Migration-section tolerated-gap note). AC#1 not checked off here per task-planner discipline (checking ACs happens at verified-implementation time); human should confirm the wording and check it.
---
<!-- COMMENTS:END -->
