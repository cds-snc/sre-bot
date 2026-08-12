# Rant

Shout a message to the current channel in **bold uppercase**. Handy for venting
about flaky deploys, loudly celebrating a win, or just adding emphasis.

## Usage

```
/rant <text>
```

The full text after the command is uppercased, wrapped in Slack bold markers,
and posted to the channel as a visible (non-ephemeral) message. The message is
posted with the invoking user's **display name and avatar** (via Slack's
`chat:write.customize`), so it visually appears to come from that user. The bot
remains the technical author, shown by a small **APP** badge next to the name.

If the user's profile can't be resolved or the customized post fails (for
example, the `chat:write.customize` scope is missing), the command gracefully
falls back to posting as the bot with a mention prefix (`@you ranted: ...`).

### Examples

| Input | Posted to channel |
| --- | --- |
| `/rant deploys keep failing` | (as you) **DEPLOYS KEEP FAILING** |
| `/rant 500 errors @ 3am!` | (as you) **500 ERRORS @ 3AM!** |

Running `/rant` with no text returns a private (ephemeral) usage hint and posts
nothing to the channel.

## How it works

- [`service.format_rant`](./service.py) holds the platform-agnostic transform:
  `text -> *TEXT.upper()*`.
- [`platforms/slack.py`](./platforms/slack.py) registers the command, looks up the
  invoking user's profile (`users.info`), and posts the message with that user's
  name and avatar via `chat.postMessage` (`chat:write.customize`). On any failure
  it falls back to a mention-prefixed bot message.
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

## Required Slack scopes

To post as the invoking user (name + avatar), the bot token needs the
`chat:write.customize` OAuth scope (in addition to `chat:write`) and
`users:read` for the profile lookup. Add them under **OAuth & Permissions →
Bot Token Scopes** and reinstall the app. Without `chat:write.customize`, the
command still works but posts as the bot with a mention prefix.

> After changing scopes and reinstalling, **restart the bot process** — the
> Slack Web API client is created once at startup and won't pick up new
> authorization until then.

## Where it works

Posting as the user uses `chat.postMessage`, which has stricter requirements
than the slash command itself:

- **Public channels:** the bot must be a member (`/invite @bot`), or the app
  must hold the `chat:write.public` scope to post without being invited.
- **Private channels:** the bot must be invited; `chat:write.public` does not
  apply.
- **Direct messages:** posting as the user is not supported (Slack returns
  `channel_not_found`), so `/rant` falls back to the mention-prefix message.

In every unsupported case the command still responds via the mention-prefix
fallback, so it never fails outright.
