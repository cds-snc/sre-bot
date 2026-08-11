# Rant

Shout a message to the current channel in **bold uppercase**. Handy for venting
about flaky deploys, loudly celebrating a win, or just adding emphasis.

## Usage

```
/rant <text>
```

The full text after the command is uppercased, wrapped in Slack bold markers,
and posted to the channel as a visible (non-ephemeral) message.

### Examples

| Input | Posted to channel |
| --- | --- |
| `/rant deploys keep failing` | **DEPLOYS KEEP FAILING** |
| `/rant 500 errors @ 3am!` | **500 ERRORS @ 3AM!** |

Running `/rant` with no text returns a private (ephemeral) usage hint and posts
nothing to the channel.

## How it works

- [`service.format_rant`](./service.py) holds the platform-agnostic transform:
  `text -> *TEXT.upper()*`.
- [`platforms/slack.py`](./platforms/slack.py) registers the command and maps the
  Slack `CommandPayload` to a `CommandResponse`.
- Registration happens at startup via the `register_slack_commands` hookimpl in
  [`__init__.py`](./__init__.py). The command is registered with **no parent**, so
  the Slack provider auto-registers it as a top-level slash command (`/rant`)
  rather than a `/sre` subcommand.

## Enabling the slash command in Slack

Because `/rant` is a top-level command, it must be declared in the Slack app
configuration before Slack will deliver it to the bot:

1. Open your Slack app settings → **Slash Commands** → **Create New Command**.
2. Set the command to `/rant` (matching the deployed `SLACK__COMMAND_PREFIX`).
3. Point it at the bot. In Socket Mode no request URL is required, but the
   command must still be declared.

> In local development the `dev-` prefix is applied, so the command is invoked as
> `/dev-rant` (see `make dev`).
