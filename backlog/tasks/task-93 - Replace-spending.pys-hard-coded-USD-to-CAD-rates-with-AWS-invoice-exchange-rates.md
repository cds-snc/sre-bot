---
id: TASK-93
title: >-
  Replace spending.py's hard-coded USD to CAD rates with AWS invoice exchange
  rates
status: To Do
assignee: []
created_date: '2026-09-15 15:14'
labels: []
dependencies:
  - TASK-25.2.4.4
references:
  - app/modules/aws/spending.py
  - app/integrations/aws/client.py
  - app/integrations/aws/settings.py
  - decisions/sdk-typing.md
  - decisions/outbound-clients.md
priority: low
ordinal: 209000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
modules/aws/spending.py converts Cost Explorer costs (USD only) to CAD using a hard-coded `rates` table. Its last entry is 2025-03, so every month since uses the fallback rate. The table's `confirmed` flag is never read, and 1.3671 repeated for six months looks like a placeholder. CAD spending figures are therefore unreliable.

Source researched 2026-09-15:
- Cost Explorer, CUR, Data Exports and Billing have no currency or exchange-rate fields (checked in the installed botocore 1.42.54 service models).
- AWS Invoicing API ListInvoiceSummaries (invoicing 2024-12-01) filters by BillingPeriod {Month, Year}. Each invoice summary's PaymentCurrencyAmount.CurrencyExchangeDetails carries SourceCurrencyCode, TargetCurrencyCode and Rate: the rate AWS applied (Bloomberg daily rate, last day of the month for consolidated pay-as-you-go invoices). https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_invoicing_ListInvoiceSummaries.html
- The payer account is invoiced in CAD (human-confirmed 2026-09-15), so invoice rates are available.

Human decisions 2026-09-15:
- A month without an invoice yet (the current month) uses the latest invoiced rate, flagged provisional.
- The sheet gets a Rate Confirmed column so readers can see which CAD figures may still change.

Prerequisites and doubts (verify at planning):
- The role used for Cost Explorer (ORG_ROLE_ARN via SERVICE_ROLE_MAP) needs invoicing:ListInvoiceSummaries. IAM is managed outside this repo.
- Add the types-boto3 `invoicing` extra, a get_aws_client Literal overload and a SERVICE_ROLE_MAP entry (decisions/sdk-typing.md, decisions/outbound-clients.md).
- One billing period can have several invoices (for example AWS vs Marketplace entities, credit memos). Decide which invoice's rate is authoritative from a real response, and confirm the Rate direction (USD to CAD).

This may never be implemented: spending is a legacy modules/aws feature that may be stale, and it is reassessed or rearchitected when it moves to packages/aws_platform. Size-gate at planning (likely an Invoicing adapter slice plus a spending caller slice).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Converted Cost for an invoiced month uses that billing period's CurrencyExchangeDetails.Rate from ListInvoiceSummaries, read through an Invoicing adapter under packages/aws_platform/adapters that returns OperationResult and has Stubber tests
- [ ] #2 A month without an invoice uses the latest invoiced rate and is marked provisional; the spending sheet carries a Rate Confirmed column
- [ ] #3 The hard-coded rates table and get_rate_for_period's fallback rate are removed from modules/aws/spending.py
- [ ] #4 Error-path behaviour of the invoice lookup is consistent with the spending run's abort-on-failure policy from TASK-25.2.4.4 (no partial sheet write) and is recorded in the task notes
<!-- AC:END -->
