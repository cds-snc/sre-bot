---
id: TASK-96
title: >-
  Keep webhook Slack block text within Block Kit limits after email mapping and
  IP linking
status: To Do
assignee: []
created_date: '2026-09-15 19:39'
labels:
  - webhooks
  - slack
  - bug
dependencies: []
references:
  - app/api/v1/routes/webhooks.py
  - app/modules/webhooks/slack.py
  - app/models/webhooks.py
  - app/integrations/slack/blocks.py
priority: high
ordinal: 213000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Production bug 2026-09-15: webhook b65d3a4e-6dc9-4fc9-a748-e7ab7066ae2a posts fail hourly with Slack invalid_blocks, "must be less than 3001 characters [json-pointer:/blocks/11/text/text]". The route returns 500 and the alert never reaches the channel.

The payload is sender-built (matched_payload_type=WebhookPayload), but POST /hook/{webhook_id} rewrites it before posting (api/v1/routes/webhooks.py:121-128):
- map_emails_to_slack_users (modules/webhooks/slack.py:30-39) swaps emails for <@U...> mentions.
- hydrate_ip_addresses (:87-95, link_ip_addresses_in_dict :75-84) replaces every valid IP in every string with <{BACKEND_URL}/geolocate/{ip}|{ip}>.
Nothing enforces Block Kit length limits afterwards. integrations/slack/blocks.py validate_blocks is structural only. A section just under 3000 characters with a few IPs therefore goes over. Whether this sender was already over the limit is unknown; the diagnostics task will tell. The fix has to cover both cases.

Planning must:
- Source the Block Kit text limits (section text, section fields, header, context elements, attachments) from current Slack docs, not memory.
- Get a human decision per case:
  (a) Linking would push a string over its limit: skip linking for that string, or truncate.
  (b) The sender's text is already over the limit: truncate with a visible marker, or fall back to posting the message text or a plain notice so the alert is not lost.
- Keep truncation from cutting inside Slack <...|...> link, mention or mrkdwn entity syntax.
- Leave payloads that are within limits untouched.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A section whose text is within the limit before IP linking but over it after is posted with text within the limit and no broken Slack link syntax (test)
- [ ] #2 A sender block already over the limit is handled per the recorded human decision, and the alert still reaches Slack (test with a stubbed client)
- [ ] #3 Payloads within all limits are posted unchanged (regression test)
- [ ] #4 The limit values cite current Slack Block Kit documentation in the plan
<!-- AC:END -->
