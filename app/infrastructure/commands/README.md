# Infrastructure Commands Framework

## Overview

This package implements a small, framework-agnostic command system used by the SRE bot to parse, register, and dispatch text-based commands (for example: Slack slash-commands). The framework separates responsibilities into: registry, parser, context, providers, and response formatting.

## Components

- `registry`:
  - Holds namespaced `Command` objects and their handlers.
  - Commands are registered with a namespace (for example `groups`) so providers can mount the registry and dispatch commands scoped to that namespace.

- `parser`:
  - Parses raw command text into a command name, positional arguments, and flags/options.
  - Produces a representation used by the registry to validate and route to handlers.

- `context`:
  - `CommandContext` provides the handler with platform-agnostic utilities such as `respond()` and `translate()`.
  - Context instances are created by providers and contain request-scoped data (user, channel, locale, responder callback).

- `providers`:
  - Adapter layer between platform (Slack, CLI, HTTP) and the command framework.
  - Providers extract text from platform payloads, create a `CommandContext`, and call the registry/parser to dispatch the command.
  - The Slack provider implements Slack-specific behavior: acknowledges incoming requests, resolves locale, and formats responses for Slack.

- `responses`:
  - Response models and formatters encapsulate how handler results or errors are rendered for a platform.
  - Formatters convert logical response objects into platform payloads (e.g., Slack blocks or text).

## Usage

## Registering a command handler

1. Define a `Command` and handler and register it in a namespaced registry (example namespace: `groups`).
2. The handler receives a `CommandContext` and should use `ctx.respond()` to send results and `ctx.translate()` for localized strings.

Example (conceptual):

```python
from infrastructure.commands.registry import Command, registry

@registry.register("groups")
def my_handler(ctx, args):
    ctx.respond("Handled")
```

## Mounting a registry in a provider

Providers attach a `registry` attribute and expose a `handle()` method that accepts platform payloads. For Slack, the SRE router initializes a `SlackCommandProvider`, assigns `provider.registry = groups_registry`, then calls `provider.handle(...)` with the unpacked Slack payload.

## Provider responsibilities

- Extract the raw command text from the incoming payload.
- Create a `CommandContext` populated with responder callback and locale.
- Call the parser and registry to dispatch the command.
- Format and send responses using the configured response formatter.

## Testing

Integration tests simulate platform payloads by creating a provider instance, attaching a registry, and invoking `provider.handle(...)` with a mocked `ack`, `respond`, `client`, and `command` payload. Unit tests exercise handlers using a mocked `CommandContext`.

## Notes

- Registries are namespaced: providers or callers are expected to supply only the subcommand text for dispatch when a higher-level router already consumed the namespace token.
- Context `translate()` calls expect translation keys provided by the centralized i18n system; providers are responsible for creating/attaching translators or translation wrappers into the context.

## Files of interest

- `registry.py` — namespaced command registration and lookup
- `parser.py` — parsing command text into name/args/flags
- `context.py` — `CommandContext` model used by handlers
- `providers/base.py` — base provider contract
- `providers/slack.py` — Slack-specific provider implementation
- `responses/formatters.py` and `responses/slack_formatter.py` — response formatting for platforms

If you need examples, inspect the `modules/*/commands` registries and the Slack provider tests which show end-to-end usage patterns.
