# Webhooks

Turns inbound webhook deliveries from senders that cannot hold an identity (AWS SNS, third-party services, legacy Slack-shaped callers) into typed events (`InboundEvent`) that features consume, and posts them to their destinations. Which delivery is which event, and how it reads, is provisioned content: sender kinds under `<content root>/webhooks/sender-kinds/` (decisions/webhooks.md).

- `domain/`: the events, sender kinds and instances, and the pure engines: matching (`kinds.py`), extraction with singular JSONPath (`extraction.py`), Liquid rendering with per-language bot wording (`rendering.py`), the interpret stage (`interpret.py`), the email finder (`mentions.py`) and value hygiene (`values.py`).
- `schemas.py`: the sender-kind file model, registered as the `webhooks/sender-kinds` content kind.
- `settings.py`: the `[webhooks]` limits.

## Classification

generic

## Feature consumers

- features.incident.response
