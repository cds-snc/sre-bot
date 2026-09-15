---
id: TASK-95
title: Log payload-shape diagnostics when a webhook post to Slack fails
status: To Do
assignee: []
created_date: '2026-09-15 19:39'
updated_date: '2026-09-15 19:39'
labels:
  - observability
  - webhooks
milestone: m-4
dependencies: []
references:
  - app/modules/webhooks/slack.py
  - decisions/observability.md
  - app/api/v1/routes/webhooks.py
priority: high
ordinal: 212000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Motivation (production incident 2026-09-15): webhook b65d3a4e-6dc9-4fc9-a748-e7ab7066ae2a received hourly WebhookPayload posts (user agents python-urllib3/1.26.19 and 2.7.0, X-Forwarded-For 15.223.30.255, unsigned). Each failed with Slack invalid_blocks, "must be less than 3001 characters [json-pointer:/blocks/11/text/text]", and the alert was lost (HTTP 500).
The logs could not answer the key question: was block 11 already over the limit when the sender sent it, or did our payload rewriting push it over? api/v1/routes/webhooks.py:145-150 logs only error=str(e). The route rewrites sender blocks before posting: map_emails_to_slack_users (modules/webhooks/slack.py:30-39) and hydrate_ip_addresses (:87-95), which replaces every IP with <BACKEND_URL/geolocate/ip|ip> and adds roughly 40-60 characters per IP.

Scope (diagnostics only, no behaviour change):
- Enrich webhook_posting_error with structured shape fields: slack_error and Slack's errors list (from SlackApiError.response), matched_payload_type, hook_type, block_count and attachment_count.
- For each json-pointer in Slack's errors, log the block index, block type and text length, measured both before email mapping and IP linking and after.
- Never log payload, block or attachment text. Free-text payloads can carry secrets or PII that key-based redaction cannot catch (decisions/observability.md "Redaction").
- Keep the existing 500 response and the webhook_invocation event unchanged.

Related: the block-limit bug fix is a separate task. The two can land in either order.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 On SlackApiError, webhook_posting_error carries slack_error, Slack's errors list, matched_payload_type, hook_type, block_count and attachment_count (test)
- [ ] #2 For each invalid_blocks json-pointer, the event carries the block index, block type and text length before and after email mapping and IP linking, verified by a test where IP linking pushes a section over the limit
- [ ] #3 No payload, block or attachment text appears in the logged event (test asserts absence)
- [ ] #4 Non-Slack exceptions still log webhook_posting_error with the existing fields, and the route still returns 500 (test)
<!-- AC:END -->
