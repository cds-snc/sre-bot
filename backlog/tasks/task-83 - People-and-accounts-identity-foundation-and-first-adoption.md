---
id: TASK-83
title: 'People and accounts: identity foundation and first adoption'
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies: []
references:
  - decisions/people-and-accounts.md
  - decisions/capability-packages.md
  - decisions/workplace-systems.md
  - decisions/platform-entrypoints.md
priority: medium
ordinal: 167000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR: contains no implementation. Builds the identity model in decisions/people-and-accounts.md (Draft, Option A: app-owned person records in DynamoDB) for an organization that runs Google Workspace with Slack, and Microsoft 365 with Teams, side by side.

WHY: the bot coordinates people across both suites, but today it identifies humans by email:
- Slack profile emails for retro attendees;
- actor_email in access request decisions;
- a user_email index on the audit trail.
Google and Microsoft addresses differ for the same person, and Google addresses are not reliably first.last, so joining on email is wrong for a growing share of users.

CURRENT GAPS (2026-09-10):
- There is no people table and no person record. DynamoDB is provisioned (terraform/dynamodb.tf) and used through StorageService by access, idempotency and audit.
- StorageService has no atomic write across several items, which a unique account claim plus its link needs. Its query() still leaks DynamoDB syntax (TASK-27).
- The Slack runtime still lives in integrations/slack/. Resolving callers at the entry point needs the split in decisions/platform-entrypoints.md (Draft), through a re-scoped TASK-26.
- No Microsoft Graph client exists.
- people-and-accounts.md still has open questions: the first verified-link mechanism, and the contractor source.

SAFEST SEQUENCE. Each step is reversible, and nothing visible to users changes until shadow data supports it.
0. Decide: accept the Draft records and answer the open questions. In parallel, add the atomic multi-item write after TASK-27.
1. Foundation, no consumers: provision the table, then build the people capability package with its in-memory fake.
2. Populate, reading vendors only: import Google Directory employees; import Slack accounts unlinked; add SRE link administration with bulk review of suggestions. The Microsoft Graph client and Entra account import follow the same pattern.
3. Observe: resolve Slack callers at the entry point in shadow mode. Compute retro attendees from people alongside Slack emails, and log the differences.
4. Cut over with fallback: retro attendees come from people; unlinked attendees fall back to their Slack email with a warning.
5. Contract: inventory stored human references keyed by email or vendor id, and migrate each through expand, backfill, switch reads, contract.

RULES FOR EVERY CHILD:
- Never create a link from matching emails or names.
- Vendors are only read.
- New writes go to the people table only.
- Jobs and cutovers ship behind settings that default to off.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every child task is Done, completed in the dependency order recorded on the children
- [ ] #2 No consumer switches to person-based resolution before SRE has reviewed a shadow comparison
- [ ] #3 decisions/people-and-accounts.md is Accepted, and its Migration section lists only the gaps still tolerated
<!-- AC:END -->
