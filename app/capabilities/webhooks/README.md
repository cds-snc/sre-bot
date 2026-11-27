# Webhooks

Turns inbound webhook deliveries from senders that cannot hold an identity (AWS SNS, third-party services, legacy Slack-shaped callers) into typed events (`InboundEvent`) that features consume, and posts them to their destinations. Which delivery is which event, and how it reads, is provisioned content: sender kinds under `<content root>/webhooks/sender-kinds/` (decisions/webhooks.md).

- `domain/`: the events, sender kinds and instances, and the pure engines: matching (`kinds.py`), extraction with singular JSONPath (`extraction.py`), Liquid rendering with per-language bot wording (`rendering.py`), the interpret stage (`interpret.py`), the email finder (`mentions.py`) and value hygiene (`values.py`).
- `schemas.py`: the sender-kind file model, registered as the `webhooks/sender-kinds` content kind.
- `domain/extensions.py` and `hookspecs.py`: the extension point. A feature returns its `EventConsumer` values (by event type) from `register_webhook_consumers` and its `EventHandler` values (by id) from `register_webhook_handlers`; `service.py` validates them once at startup into `WebhookExtensions`. An action a consumer offers has an id starting with its plugin's entry-point name.
- `domain/messages.py` and `interfaces.py`: the platform-neutral message intents and the `ChannelPoster` port, one poster per workplace system.
- `adapters/slack.py`: the Slack poster: Block Kit layout, escaping, limits measured on escaped text, capped mention lookups. `providers.py` builds it; only entrypoints and jobs import `providers.py`.
- `locales/`: the bot's own wording (the fallback header), en-US and fr-FR, read through the `Translator` contract.
- `settings.py`: the `[webhooks]` limits and the per-attempt platform timeout.

## Classification

generic

## Feature consumers

- features.incident.response
