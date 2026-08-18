# incident_summary

`/sre incident summarize` — an AI-generated catch-up summary of the current
channel, for someone jumping into an incident.

## What it does

Fetches recent channel history, resolves author display names, builds a plain
transcript, and asks the `Summarizer` port (OpenAI, see
`app/integrations/openai/`) to produce a concise, factual summary: what is
happening, current status, actions taken, and next steps. The summary is
returned **ephemerally** — only the person who ran
the command sees it, so it never adds noise to the incident channel.

## Usage

```
/sre incident summarize                      # since channel creation, up to 500 messages (defaults)
/sre incident summarize --since 30m           # last 30 minutes
/sre incident summarize --since 2h           # last 2 hours
/sre incident summarize --since 90m --limit 100
/sre incident summarize --since 1d --limit 300
```

- `--since` — how far back to summarize: `30m`, `2h`, `1d` (a bare number is
  treated as hours). Omitted → the incident channel's creation time (falling
  back to `INCIDENT_SUMMARY__DEFAULT_SINCE_HOURS`, 24h, if the channel start
  cannot be determined).
- `--limit` — maximum messages to include. Omitted/invalid → default (500);
  capped at `INCIDENT_SUMMARY__MAX_HISTORY_LIMIT` (1000).

## Settings

Feature-domain settings live in `settings.py` (`IncidentSummarySettings`); all
have safe defaults:

| Env var | Default | Meaning |
| --- | --- | --- |
| `INCIDENT_SUMMARY__DEFAULT_HISTORY_LIMIT` | `500` | Messages fetched when `--limit` is omitted |
| `INCIDENT_SUMMARY__MAX_HISTORY_LIMIT` | `1000` | Hard cap on `--limit` |
| `INCIDENT_SUMMARY__DEFAULT_SINCE_HOURS` | `24` | Fallback look-back window when `--since` is omitted and the channel start cannot be determined |

OpenAI credentials/model are **not** configured here — they belong to the
vendor client (`OPENAI_API_KEY`, `OPENAI_MODEL`, …) in
`app/integrations/openai/settings.py`.

## Required Slack scopes

The bot must be able to read channel history and look up users:

- `channels:history` (public channels) / `groups:history` (private channels)
- `users:read`

The bot must be a member of the channel (or have `channels:history` via an
appropriate install). After changing scopes, reinstall the app and restart the
bot so the Web API client picks up the new token.

## Architecture

- `platforms/slack.py` — Slack adapter: registers the command under
  `sre.incident`, parses `--since`/`--limit`, fetches history + names, calls the
  service, renders an ephemeral response. Follows the five-step handler
  discipline (parse → typed values → one service call → `OperationResult` →
  render). No runtime `slack_sdk` import (typing only).
- `service.py` — platform-agnostic: turns `TranscriptMessage` values into a
  transcript and delegates to the `Summarizer` port, returning
  `OperationResult`. No Slack/HTTP imports. Empty history →
  `OperationResult` with `error_code="EMPTY_HISTORY"`.
- `settings.py` — partitioned feature settings.
- `locales/` — EN/FR message catalogues (`register_i18n_resources`).

Registration is startup-driven via pluggy hookimpls in `__init__.py`
(`register_slack_commands`, `register_i18n_resources`); no import-time side
effects.
