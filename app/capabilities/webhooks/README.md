# Webhooks

Turns inbound webhook deliveries from senders that cannot hold an identity (AWS SNS, third-party services, legacy Slack-shaped callers) into typed events (`InboundEvent`) that features consume, and posts them to their destinations. Which delivery is which event, and how it reads, is provisioned content: sender kinds under `<content root>/webhooks/sender-kinds/` (decisions/webhooks.md).

- `domain/`: the events, sender kinds and instances, and the pure engines: matching (`kinds.py`), extraction with singular JSONPath (`extraction.py`), Liquid rendering with per-language bot wording (`rendering.py`), the interpret stage (`interpret.py`), the email finder (`mentions.py`) and value hygiene (`values.py`).
- `schemas.py`: the sender-kind file model, registered as the `webhooks/sender-kinds` content kind.
- `domain/extensions.py` and `hookspecs.py`: the extension point. A feature returns its `EventConsumer` values (by event type) from `register_webhook_consumers` and its `EventHandler` values (by id) from `register_webhook_handlers`; `service.py` validates them once at startup into `WebhookExtensions`. An action a consumer offers has an id starting with its plugin's entry-point name.
- `domain/messages.py` and `interfaces.py`: the platform-neutral message intents and the `ChannelPoster` port, one poster per workplace system.
- `adapters/slack.py`: the Slack poster: Block Kit layout, escaping, limits measured on escaped text, capped mention lookups. `providers.py` builds it; only entrypoints and jobs import `providers.py`.
- `locales/`: the bot's own wording (the fallback header), en-US and fr-FR, read through the `Translator` contract.
- `entrypoints/http.py`: `POST /hook/{webhook_id}` (built, not mounted yet): instance lookup, media type, a body cap per protocol, verify and decode, persist, inline processing, and the responses table. `entrypoints/http_aws_sns.py` and `http_legacy_slack_json.py` are the wire protocols; `domain/strict_json.py` parses every body strictly (RFC 7493).
- `adapters/aws_sns.py`: SNS certificate fetches and subscription confirmations on async httpx (SNS hosts only, no redirects), with a bounded certificate cache.
- `domain/inbox.py`, `store.py` and `service.py`: the durable inbox on the records contract. The item's conditional insert is the delivery dedupe; transitions are guarded on state and owner; each finished target is recorded so a retry repeats none; `WebhookProcessor` persists, processes inline within the deadline and sweeps due items.
- `entrypoints/jobs.py`: the leased sweeper job (built, not registered yet).
- `settings.py`: the `[webhooks]` limits, the per-attempt platform timeout, and the ingest bounds (body caps, deadlines, leases, inbox retention, retries, SNS replay bound and fetches).

## Classification

generic

## Feature consumers

- features.incident.response
