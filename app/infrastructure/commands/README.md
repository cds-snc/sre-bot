# Infrastructure Commands Framework

## Overview

This package implements a small, platform-agnostic command framework used by the SRE bot
to register, parse, validate, and dispatch text-based commands (e.g. Slack slash commands
or HTTP/API based invocations). The implementation is deliberately modular and split
into responsibilities: registration, parsing, execution context, platform adapters (providers),
and response formatting.

This README documents the current behavior and developer-facing integration points.

## Core Concepts

- Registry: `CommandRegistry` holds namespaced `Command` objects. Commands may have
  positional arguments, flags, examples and nested subcommands. A registry exposes
  `command`, `subcommand`, and `schema_command` decorators for registering handlers.

- Parser: `CommandParser` tokenizes input (POSIX/shlex semantics), supports quoted
  strings, flags (`--flag` and `--key=value`), type coercion and validation against
  `Argument` definitions. Parsing errors raise `CommandParseError` and are handled
  by providers/router.

- Context: `CommandContext` is a platform-agnostic container created by providers to
  give handlers access to the requestor (`user_id`, `user_email`), `locale`, a
  translator callable, and a response channel (`responder`) with methods like
  `send_message`, `send_ephemeral`, `send_card`, `send_error`, and `send_success`.

- Providers: Platform adapters subclass `CommandProvider` to map platform payloads
  into framework operations. Providers implement text extraction, preprocessing
  (e.g., resolving Slack mentions to emails), context creation (`create_context`),
  acknowledgement models (`acknowledge`) and platform-specific send helpers
  (`send_error`, `send_help`, `send_*`). The Slack adapter `SlackCommandProvider`
  includes helpers to resolve user/channel mentions and wraps Slack SDK clients into
  a `SlackResponseChannel` and `SlackResponseFormatter`.

- Router: `CommandRouter` is a higher-level router that registers named subcommands
  to platform providers or nested routers. It routes incoming payloads based on
  detected platform and command text tokens. Routers support arbitrary nesting depth
  (e.g., `/sre dev aws health check`), automatically propagate namespace context for
  help generation, and handle platform detection and router-level help text.

- Responses: Platform-agnostic response models (cards, success, error) are rendered
  by `ResponseFormatter` implementations. `SlackResponseFormatter` implements Block
  Kit formatting used by the Slack response channel.

## Developer Integration Guide

1. Initialize a `CommandRegistry` for your module and register commands:

```python
from infrastructure.commands.registry import CommandRegistry, Argument, ArgumentType

registry = CommandRegistry("groups")

@registry.command(
    name="list",
    description_key="groups.commands.list.description",
    args=[Argument("provider", type=ArgumentType.STRING, required=False)],
)
def list_groups(ctx, provider: str = None):
    ctx.respond("TODO: list groups")

@registry.subcommand("list", name="managed")
def list_managed(ctx):
    ctx.respond("TODO: list managed groups")

@registry.schema_command(
    name="add",
    schema=...,  # Pydantic model
)
def add_member(ctx, request):
    # request is a validated Pydantic model
    pass
```

Notes:
- Use `schema_command` when you want Pydantic validation and automatic argument
  generation from a schema. The framework injects `requestor` and `idempotency_key`.
- Keep providers platform-agnostic: platform-specific preprocessing (mention/channel
  resolution) should be implemented in the provider's `preprocess_command_text`.

2. Attach your registry to a provider instance and register it with a router:

```python
from infrastructure.commands.providers import get_provider
from infrastructure.commands.router import CommandRouter

# Create provider with registry
slack_provider = get_provider("slack")
slack_provider.registry = registry

# Register with router
groups_router = CommandRouter(namespace="groups")
groups_router.register_subcommand(
    name="manage",
    provider=slack_provider,
    platform="slack",
    description="Manage group memberships",
)
```

For nested command hierarchies, register routers with other routers:

```python
# Create nested structure: /sre dev aws <command>
aws_dev_router = CommandRouter(namespace="aws")
aws_dev_router.register_subcommand("health", health_provider, "slack")
aws_dev_router.register_subcommand("identitystore", identitystore_provider, "slack")

dev_router = CommandRouter(namespace="dev")
dev_router.register_subcommand("aws", aws_dev_router, "slack")  # Nested router

sre_router = CommandRouter(namespace="sre")
sre_router.register_subcommand("dev", dev_router, "slack")  # Another nested router
```

The router automatically:
- Propagates namespace context through nested routers for accurate help paths
- Strips consumed tokens and passes remaining text to the next router or provider
- Generates help text showing all available subcommands at each level

3. The router delegates to providers or nested routers when `handle(platform_payload)` 
   is called. For providers, the command flow is:
- acknowledge
- extract + preprocess text
- tokenize
- validate/parse arguments
- build `CommandContext`
- execute handler with parsed args (or validated Pydantic request)

For nested routers, the flow extracts the next subcommand token, updates the payload
with remaining text, and delegates to the nested router or provider.

4. Translation and locale:
- Providers may attach a translator callable to `CommandContext` (via
  `ctx.set_translator`). The registry and router use translation keys where provided
  and providers expose helper methods to translate or fall back to English.

5. Help text and errors:
- The provider and router generate help text from command metadata (descriptions,
  args, examples) and translation keys when a translator is available. Help text
  uses code formatting (backticks) for command names and examples, and shows full
  command paths including nested router prefixes (e.g., `/sre dev aws health check`).
  Parsing or validation errors are converted to user-facing messages by providers 
  using `_translate_error`.

## Testing

- Unit test handlers by creating a `CommandContext` with a mock responder and
  translator. Inject the registry into a `CommandProvider` and call `provider.handle`
  with a mocked platform payload (`ack`, `command`, `client`, `respond`) for Slack.
- Integration tests can simulate Slack payloads including a `client` that responds
  to `users_info`/`conversations_list` calls if mention/channel resolution is
  necessary to exercise preprocessing.

## Files of interest

- `registry.py` — registration decorators and Pydantic `schema_command` support
- `parser.py` — tokenization, flags, and type coercion
- `context.py` — `CommandContext` and `ResponseChannel` protocol
- `router.py` — command routing, nested router support, namespace propagation
- `providers/base.py` — provider contract and generic execution flow
- `providers/slack.py` — Slack adapter, mention/channel resolution, responder
- `responses/formatters.py` & `responses/slack_formatter.py` — response rendering

## Troubleshooting

- If you see `RuntimeError: <Provider> registry not attached` ensure the module
  initialization attaches its `CommandRegistry` to the provider before handlers
  are invoked.
- If translation keys are returned instead of user text, confirm a translator was
  attached to the provider and that the translator's `translate_message` supports
  the requested keys and locale.

## Contact

If behavior is unclear or you need an example wiring for your module, see other
modules under `app/modules/*/commands` for reference implementations or ask a
maintainer for an initialization example.
