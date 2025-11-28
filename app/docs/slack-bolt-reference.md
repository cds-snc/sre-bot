# Slack Bolt Argument Injection Reference

## Overview

Slack Bolt's kwargs-injection system automatically provides listener functions with access to request data, utilities, and SDK objects based on parameter names. Understanding which parameters refer to the same underlying data prevents redundant argument passing and improves code clarity.

## Argument Categories

### 1. Request Body & Payload Aliases

These parameters represent request data. For slash commands, several of them refer to the same object.

| Parameter | Type | Content | Slash Command |
|-----------|------|---------|---|
| `body` | dict | Parsed HTTP request body | same as `command` |
| `command` | dict | Extracted slash command data (via `to_command()`) | same as `body` |
| `payload` | dict | First truthy alias or fallback to `body` | same as `body` and `command` |
| `action` | dict | Extracted action data (via `to_action()`) | `None` for slash commands |
| `view` | dict | Extracted view data (via `to_view()`) | `None` for slash commands |
| `event` | dict | Extracted event data (via `to_event()`) | `None` for slash commands |
| `message`, `options`, `shortcut`, `step` | dict | Payload-specific aliases | `None` for slash commands |

**Key insight:** For slash commands, `body`, `command`, and `payload` refer to the same dict object (identical identity, not copies).

### 2. Context Objects & Utilities (non-payload)

These are constructed by Bolt and placed on the request context. They are never the same object as `body`/`command`/`payload`.

| Parameter | Type | Purpose |
|-----------|------|---------|
| `ack` | callable | Acknowledge the request to Slack immediately |
| `respond` | callable | Send a response via `response_url` (slash commands only) |
| `say` | callable | Post a message to the channel via `chat.postMessage` |
| `client` | WebClient | Slack SDK client for making API calls |
| `context` | BoltContext | Request metadata (channel_id, user_id, etc.) and context references |
| `logger` | Logger | Configured logger for this app |
| `req` / `request` | BoltRequest | Wrapper containing `body`, headers, and context |
| `resp` / `response` | BoltResponse | Response representation |

### 3. Workflow/Assistant Utilities

| Parameter | Type | Purpose |
|-----------|------|---------|
| `complete` | callable | Signal successful completion of a custom function |
| `fail` | callable | Signal failure of a custom function |
| `set_status`, `set_title`, `set_suggested_prompts` | callable | AI assistant utilities |
| `get_thread_context`, `save_thread_context` | callable | Assistant thread context management |
| `next`, `next_` | callable | Middleware chain progression (middleware only) |

## Why body, command, and payload are identical for slash commands

Slack Bolt's kwargs-injection builds a map from parameter names to values. For slash commands:

1. `to_command(body)` is called, which returns the entire `body` dict (source: `slack_bolt/request/payload_utils.py`)
2. The `payload` parameter is computed as the first truthy value among aliases (`options`, `shortcut`, `action`, `view`, `command`, `event`, `message`, `step`) or falls back to `body`
3. For slash commands, only `command` is truthy (the others are `None`), so `payload` resolves to `command`
4. Since `to_command(body)` returns `body`, Bolt injects the same object reference for all three: `body is command is payload`

For other event types, aliases may be sub-objects. For example, `to_action(body)` extracts `body["actions"][0]`, so `action` would differ from `body`.

## Why ack, respond, client are never the same as body/command

- **`ack` and `respond`** are callables bound to `request.context` at initialization; they represent request handlers, not data payloads
- **`client`** is a `WebClient` instance separate from request data, used for making API calls
- These are fundamentally different types and objects from dict payloads

## Best Practices

### Principle: Accept one canonical payload object per handler type

Avoid passing multiple payload parameters that refer to the same data. Choose the most semantically appropriate parameter for the listener type.

### By listener type:

#### Slash Commands

**Antipattern (redundant):** passing both `body` and `command`

```python
# ❌ AVOID: body and command are the same object for slash commands
def sre_command(ack, command, body, respond, client):
    ack()
    action, *args = command["text"].split()  # command is body
    # Passing both command and body to helpers is redundant
    handle_sre_action(action, args, command, body, client, respond)

def handle_sre_action(action, args, command, body, client, respond):
    # handler receives duplicate data under different names
    if command["text"] == body["text"]:  # True: they're identical
        respond("Processing...")
```

**Better practice:**

```python
# ✅ PREFER: accept only command (or body), not both
def sre_command(ack, command, respond, client):
    ack()
    action, *args = command["text"].split()
    handle_sre_action(action, args, command, client, respond)

def handle_sre_action(action, args, command, client, respond):
    # handler has clear, single source of command data
    respond(f"Processing {action}...")
```

#### Block Actions

**Antipattern:** passing both `body` and `action`

```python
# ❌ AVOID: action is a sub-object of body, not the same
def handle_button_click(ack, body, action, client):
    ack()
    # body contains the full envelope; action is body["actions"][0]
    button_value = action["value"]
    # Passing both is unclear and potentially confusing
    process_button(body, action, client)

def process_button(body, action, client):
    # Handler doesn't know which one to trust
    pass
```

**Better practice:**

```python
# ✅ PREFER: use action directly; use body only if you need envelope data
def handle_button_click(ack, action, body, client):
    ack()
    button_value = action["value"]
    # Only pass what you need; action for the button, body for full context if needed
    process_button(action, client)

def process_button(action, client):
    # Clear intent: we're processing the action, not the full body
    button_value = action["value"]
    client.chat_postMessage(
        channel=action["channel"]["id"],
        text=f"Processed {button_value}"
    )
```

#### View Submissions

**Antipattern:** passing both `body` and `view`

```python
# ❌ AVOID: view is a sub-object of body
def handle_view_submission(ack, body, view, client):
    ack()
    # body["view"] is the same as view
    form_data = view["state"]["values"]
    save_data(body, view, client)  # Redundant

def save_data(body, view, client):
    pass
```

**Better practice:**

```python
# ✅ PREFER: use view; optional body for envelope metadata
def handle_view_submission(ack, view, client):
    ack()
    form_data = view["state"]["values"]
    save_data(view, client)

def save_data(view, client):
    form_data = view["state"]["values"]
    client.views_update(
        view_id=view["id"],
        view={...}
    )
```

## Nested Handler Chains: Slash Commands with Subcommands

Many handlers in this application follow a pattern where a slash command (e.g., `/sre`) dispatches to nested subcommand handlers (e.g., `groups`, `incident`, `webhooks`, `geolocate`). This section explains how to apply best practices across the handler chain.

### Pattern Overview

The typical flow is:
1. Slack fires `/sre` command → Bolt injects parameters into `sre_command`
2. `sre_command` matches the subcommand and dispatches to handler(s)
3. Handlers (e.g., `handle_incident_command`, `handle_webhook_command`) receive command context and perform actions

The challenge: what parameters should flow through the chain?

### Current Pattern in sre_command (status quo)

```python
# Current: passes body, command, payload to subcommand helpers
def sre_command(ack, command, respond, client, body, payload):
    ack()
    action, *args = slack_commands.parse_command(command["text"])
    match action:
        case "incident":
            incident_helper.handle_incident_command(args, client, body, respond, ack)
        case "webhooks":
            webhook_helper.handle_webhook_command(args, client, body, respond)
        case "groups":
            # ... passes both body and command
            adapter.handle({
                "ack": ack,
                "command": cmd_copy,
                "client": client,
                "respond": respond,
                "body": body,  # Redundant: body is command for slash commands
            })
```

**Issues:**
- Passes both `body` and `command` (identical for slash commands)
- `payload` is declared but never used
- Inconsistent: some handlers receive `body`, others receive reconstructed command

### Best Practice Pattern: Nested Handlers

**Key principle:** Pass the _minimum_ data needed at each level, use canonical names.

#### Level 1: Slash Command Handler (sre_command)

```python
# ✅ IMPROVED: slash command handler
def sre_command(ack: Ack, command: dict, respond: Respond, client: WebClient):
    """Dispatch /sre subcommands to appropriate handlers."""
    ack()
    
    action, *args = slack_commands.parse_command(command["text"])
    
    match action:
        case "help" | "aide":
            respond(help_text)
        case "geolocate":
            if not args:
                respond("Please provide an IP address.")
                return
            geolocate_helper.geolocate(args, respond)
        
        case "incident":
            # Pass: command (for channel, user, etc.), utilities, subcommand args
            incident_helper.handle_incident_command(
                args=args,
                command=command,
                client=client,
                respond=respond,
                ack=ack
            )
        
        case "webhooks":
            # Pass: command, utilities, subcommand args
            webhook_helper.handle_webhook_command(
                args=args,
                command=command,
                client=client,
                respond=respond,
            )
        
        case "groups":
            # Pass: command, utilities, subcommand args
            adapter = get_groups_adapter()
            adapter.handle(
                ack=ack,
                command=command,
                client=client,
                respond=respond,
                args=args
            )
        
        case _:
            respond(f"Unknown command: `{action}`")
```

**Changes from current:**
- Remove `body` and `payload` (redundant with `command`)
- Pass `command` explicitly (semantically clear)
- Pass `args` (remaining subcommand tokens)
- Only pass utilities actually needed

#### Level 2: Subcommand Handler Signature

```python
# ✅ IMPROVED: incident subcommand handler
def handle_incident_command(
    args: list[str],
    command: dict,
    client: WebClient,
    respond: Respond,
    ack: Ack,
) -> None:
    """Handle /sre incident subcommand.
    
    Args:
        args: remaining command tokens after 'incident'
        command: the slash command dict (contains channel_id, user_id, etc.)
        client: WebClient for API calls
        respond: utility to send response
        ack: utility to acknowledge
    """
    ack()
    logger.info("incident_subcommand_received", subcommand=args)
    
    # Extract what you need from command
    channel_id = command["channel_id"]
    user_id = command["user_id"]
    
    # ... rest of logic
```

**vs. current (redundant):**
```python
# ❌ CURRENT: incident subcommand handler passes both body and command
def handle_incident_command(
    args: list[str],
    client: WebClient,
    body: dict,  # Redundant: body is command for slash commands
    respond: Respond,
    ack: Ack,
) -> None:
    # Now handler has two ways to access the same data
    # Which one should I use? body["channel_id"] or command["channel_id"]?
    channel_id = body["channel_id"]
```

#### Level 3: Deep Handler (if needed)

If subcommand handlers dispatch further:

```python
# ✅ IMPROVED: nested handler within incident module
def handle_incident_status(
    status: str,
    command: dict,
    client: WebClient,
    respond: Respond,
) -> None:
    """Handle /sre incident status <status> subcommand."""
    channel_id = command["channel_id"]
    user_id = command["user_id"]
    
    # Use client for API calls, respond for replies
    client.chat_postMessage(
        channel=channel_id,
        text=f"Status set to {status} by <@{user_id}>"
    )
    respond(f"Incident status updated to {status}")
```

### Applying to webhook_helper

**Current pattern (redundant `body`):**

```python
# ❌ CURRENT
def handle_webhook_command(args, client, body, respond):
    if len(args) == 0:
        hooks = webhooks.lookup_webhooks("channel", body["channel_id"])
        webhooks_list.list_all_webhooks(
            client,
            body,  # Passed to deeper handler
            0,
            MAX_BLOCK_SIZE,
            "all",
            hooks,
            channel=body["channel_id"],
        )
```

**Improved pattern (pass `command`, extract what's needed):**

```python
# ✅ IMPROVED
def handle_webhook_command(args, command, client, respond):
    """Handle /sre webhooks subcommand."""
    channel_id = command["channel_id"]
    
    if not args:
        hooks = webhooks.lookup_webhooks("channel", channel_id)
        if hooks:
            webhooks_list.list_all_webhooks(
                client=client,
                channel_id=channel_id,  # Pass extracted value, not full body
                offset=0,
                limit=MAX_BLOCK_SIZE,
                filter_type="all",
                hooks=hooks,
            )
        else:
            respond("No webhooks found for this channel.")
        return
    
    # ... rest of match logic
```

**Then update `list_all_webhooks` signature:**

```python
# ❌ OLD: accepts full body
def list_all_webhooks(client, body, offset, limit, filter_type, hooks):
    channel_id = body.get("channel_id")
    # ...

# ✅ NEW: accepts specific parameters
def list_all_webhooks(
    client: WebClient,
    channel_id: str,
    offset: int,
    limit: int,
    filter_type: str,
    hooks: list,
) -> None:
    """List webhooks in a paginated view."""
    # Clearer intent: channel_id is a specific field, not hidden in body
    # ...
```

### Applying to geolocate_helper

This one is already close to best practice:

```python
# ✅ ALREADY GOOD: minimal parameters
def geolocate(args, respond):
    """Geolocate an IP address and respond with results."""
    ip = args[0]
    response = maxmind.geolocate(ip)
    respond(...)  # Uses respond utility correctly
```

**If it needed client access:**

```python
# ✅ IMPROVED: add only what's needed
def geolocate(ip: str, client: WebClient, respond: Respond) -> None:
    """Geolocate IP and optionally log to channel."""
    response = maxmind.geolocate(ip)
    # Use client for API calls if needed
    # Use respond for user feedback
```

### Summary: Nested Handler Best Practices

1. **Top-level handler (sre_command):**
   - Accept `command` (not both `body` and `command`)
   - Accept utilities (`ack`, `respond`, `client`)
   - Extract subcommand args and pass to nested handlers

2. **Subcommand handlers (incident_helper, webhook_helper):**
   - Accept `command` and extract specific fields (e.g., `channel_id = command["channel_id"]`)
   - Pass extracted fields to deeper handlers, not full `body` or `command`
   - Accept only utilities needed for this level

3. **Deep handlers:**
   - Accept specific, well-named parameters (e.g., `channel_id`, `status`, `offset`)
   - Accept utilities needed (often just `client`, `respond`)
   - Avoid passing dict wrappers; extract and name fields explicitly

4. **Benefits:**
   - Clear data flow: each handler knows exactly what data it receives
   - No redundancy: `body`/`command`/`payload` never passed together
   - Testable: handlers accept specific types, not generic dicts
   - Self-documenting: function signature shows what context is available

#### Event Listeners

**Pattern:** `event` is the relevant data

```python
# ✅ CORRECT: use event for the payload, body for full envelope if needed
@app.event("reaction_added")
def handle_reaction(ack, event, client):
    ack()
    emoji = event["reaction"]
    user = event["user"]
    # event contains the relevant fields from body["event"]
    client.reactions_add(
        name=emoji,
        channel=event["item"]["channel"],
        timestamp=event["item"]["ts"]
    )
```

### Utilities: Always use the appropriate utility, never the body

**Antipattern:** extracting response_url from body instead of using respond

```python
# ❌ AVOID: manually extracting response_url
def handle_command(ack, body, client):
    ack()
    response_url = body.get("response_url")  # Don't do this
    import requests
    requests.post(response_url, json={"text": "Response"})
```

**Better practice:**

```python
# ✅ PREFER: use the respond utility
def handle_command(ack, command, respond, client):
    ack()
    respond("Response via response_url")  # Bolt handles the details
```

**Antipattern:** extracting client from body or context manually

```python
# ❌ AVOID: manually constructing WebClient
def handle_action(ack, body, context):
    ack()
    from slack_sdk import WebClient
    token = context.get("bot_token")
    client = WebClient(token=token)
    client.chat_postMessage(channel="...", text="...")
```

**Better practice:**

```python
# ✅ PREFER: use the injected client
def handle_action(ack, action, client):
    ack()
    client.chat_postMessage(channel=action["channel"]["id"], text="...")
```

## Verification Snippet

Paste this into any listener to inspect parameter identities at runtime:

```python
logger.info("injection_inspect",
    body_type=type(body).__name__ if 'body' in locals() else None,
    payload_type=type(payload).__name__ if 'payload' in locals() else None,
    command_type=type(command).__name__ if 'command' in locals() else None,
    body_id=id(body) if 'body' in locals() else None,
    payload_id=id(payload) if 'payload' in locals() else None,
    command_id=id(command) if 'command' in locals() else None,
    client_type=type(client).__name__ if 'client' in locals() else None,
    ack_type=type(ack).__name__ if 'ack' in locals() else None,
    respond_type=type(respond).__name__ if 'respond' in locals() else None,
)
```

**Expected output for slash commands:**
- `body_id == payload_id == command_id` (all point to the same dict object)
- `client_type` is `WebClient`, `ack_type` and `respond_type` are callables or wrapper types (not dicts)

## Repository Listener Registration Map

This application uses four primary Slack Bolt listener types: `command`, `view`, `action`, and `event`.

### Registration by module

- **`app/main.py`** — entry point that calls each module's `register(bot)` function
- **`app/modules/sre/sre.py`** — `bot.command(f"/{PREFIX}sre")`
- **`app/modules/aws/aws.py`** — `bot.command`, `bot.view`
- **`app/modules/atip/atip.py`** — `bot.command`, `bot.action`, `bot.view`
- **`app/modules/role/role.py`** — `bot.command`, `bot.action`, `bot.view`
- **`app/modules/secret/secret.py`** — `bot.command`, `bot.action`, `bot.view`
- **`app/modules/incident/incident.py`** — `bot.command`, `bot.view`, `bot.action`
- **`app/modules/incident/incident_helper.py`** — `bot.action`, `bot.view`, `bot.event` (multiple reaction handlers)
- **`app/modules/sre/webhook_helper.py`** — `bot.view`, `bot.action`
- **`app/infrastructure/commands/providers/slack.py`** — `bot.command`

## Summary

When defining listener or helper functions:
1. Choose one canonical payload parameter for the event type (command → `command`, action → `action`, view → `view`, event → `event`)
2. Never pass multiple payload parameters that refer to the same data
3. Use utility parameters (`ack`, `respond`, `say`, `client`) directly from injection; never reconstruct them
4. If you need full envelope context, pass `body` alongside a specific alias (e.g., both `body` and `action`), not redundant aliases

---

# Centralized Commands Feature: Architecture & Integration

## Overview

The app is transitioning from ad-hoc Slack Bolt command handlers (sre.py, incident_helper.py, etc.) to a **centralized command infrastructure** that:

- Separates **platform-agnostic command logic** (CommandRegistry, CommandParser, command handlers) from **platform-specific integration** (SlackCommandProvider, Slack Bolt adaptation)
- Provides **consistent i18n support** across all commands via CommandContext
- Enables **command reuse** across platforms (Slack, Teams, CLI, etc.) without handler duplication
- Standardizes **argument preprocessing** and **validation** through the provider layer

## Key Components

### CommandProvider (Base Class)

**Location:** `infrastructure/commands/providers/base.py`

**Responsibility:** Implements the **generic command handling flow** that all platform providers inherit:

1. **Acknowledge** command receipt (platform-specific)
2. **Extract & tokenize** command text
3. **Handle help** requests
4. **Parse** command name and arguments
5. **Create CommandContext** (platform-specific)
6. **Preprocess arguments** (platform-specific transformations)
7. **Execute handler** with preprocessed arguments
8. **Handle errors** with proper translation/formatting

**Critical method: `handle(platform_payload)`**

```python
def handle(self, platform_payload: Any) -> None:
    """Handle command execution (generic flow)."""
    self.acknowledge(platform_payload)
    try:
        # 1. Extract and tokenize
        text = self.extract_command_text(platform_payload)
        tokens = self._tokenize(text)
        
        # 2. Handle help
        if not tokens or tokens[0] in ("help", "aide", "--help"):
            help_text = self._generate_help(framework_locale)
            self.send_help(platform_payload, help_text)
            return
        
        # 3. Parse command
        cmd = self.registry.get_command(tokens[0])
        
        # 4. Create context
        ctx = self.create_context(platform_payload)
        
        # 5. Parse arguments
        parsed = self.parser.parse(cmd, tokens[1:])
        
        # 6. Preprocess arguments (CRITICAL STEP)
        preprocessed = self._preprocess_arguments(ctx, parsed.args)
        if preprocessed is None:
            return  # Error already sent by provider
        
        # 7. Execute handler
        cmd.handler(ctx, **preprocessed)
        
    except CommandParseError as e:
        # Error handling with i18n
```

**Provider responsibilities (abstract methods that subclasses must implement):**

| Method | Purpose | Slack Example |
|--------|---------|---|
| `extract_command_text(payload)` | Extract command text from platform payload | Extract from `payload["command"]["text"]` |
| `create_context(payload)` | Build CommandContext with user/channel/locale/responder | Resolve Slack user_id, email, locale from payload |
| `acknowledge(payload)` | Acknowledge command receipt (time-sensitive on Slack) | Call Slack's `ack()` function |
| `send_error(payload, msg)` | Send error to user (platform-specific format) | Use Slack's `respond()` function |
| `send_help(payload, text)` | Send help text (platform-specific format) | Use Slack's `respond()` function |
| `_resolve_framework_locale(payload)` | Quick locale resolution for framework operations | Query Slack user profile |

**Optional provider methods (override for platform-specific behavior):**

| Method | Purpose | Default |
|--------|---------|---------|
| `_preprocess_arguments(ctx, parsed_kwargs)` | Transform arguments before handler execution | Returns unchanged |

### SlackCommandProvider

**Location:** `infrastructure/commands/providers/slack.py`

**Responsibility:** Adapt Slack Bolt to the centralized command framework

**Current state:**
- Validates SlackPayload structure
- Calls `super().handle(platform_payload)` → delegates to base class

**Issue:** SlackCommandProvider.handle() does **no Slack-specific work**; all orchestration happens in base class

**Slack-specific implementation:**

| Component | Current Status | Slack Specifics |
|-----------|---|---|
| `extract_command_text()` | ✅ Implemented | Extracts from `payload["command"]["text"]` |
| `create_context()` | ✅ Implemented | Resolves user email from Slack, gets user locale from Slack profile, creates SlackResponseChannel |
| `acknowledge()` | ✅ Implemented | Calls Slack's `ack()` function |
| `send_error()`, `send_help()` | ✅ Implemented | Uses Slack's `respond()` function |
| `_resolve_framework_locale()` | ✅ Implemented | Queries Slack user locale (fallback to config) |
| `_preprocess_arguments()` | ✅ Implemented but **never called** | Resolves @mentions to emails; returns None + sends error on failure |
| `SlackResponseChannel` | ✅ Implemented | Wraps `respond`, `client`, `channel_id`, `user_id` for send_message, send_ephemeral, send_card, send_error, send_success |

### Slack Bolt Payload Passed to SlackCommandProvider.handle()

From `modules/sre/sre.py` (example nested handler dispatch):

```python
# Slack Bolt injects these 5 parameters into sre_command listener
def sre_command(ack: Ack, command, respond: Respond, client: WebClient, body):
    # ...
    case "groups":
        adapter = get_groups_adapter()
        payload = {
            "ack": ack,
            "command": command,  # Same object as body for slash commands
            "client": client,
            "respond": respond,
            "body": body,  # Same object as command for slash commands
        }
        adapter.handle(payload)  # SlackCommandProvider.handle() receives this
```

**Note:** The reference document clearly shows this passes redundant data (body == command for slash commands). Slack Bolt design forces this redundancy; the centralized framework should normalize it.

## Current Data Flow (From Slack to Handler)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Slack Bolt fires /sre command                            │
│    Injects: ack, command, respond, client, body             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ 2. sre_command listener (modules/sre/sre.py)               │
│    Parses action/args from command["text"]                 │
│    Dispatches: case "groups" → adapter.handle(payload)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ 3. SlackCommandProvider.handle(payload)                     │
│    Validates SlackPayload structure                         │
│    Calls super().handle(platform_payload)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ 4. CommandProvider.handle(platform_payload)                │
│    a. acknowledge(payload) → calls ack()                   │
│    b. extract_command_text() → payload["command"]["text"]  │
│    c. tokenize() → ["groups", "list"]                      │
│    d. get_command("groups") from registry                  │
│    e. create_context(payload)                              │
│       - user_id, user_email from Slack                     │
│       - locale from Slack profile                          │
│       - SlackResponseChannel created                       │
│    f. parser.parse(cmd, ["list"])                          │
│       - Returns ParseResult with args dict                 │
│    g. _preprocess_arguments(ctx, args)                     │
│       ⚠️  STEP G IS WHERE THE GAP IS                       │
│       Current: SlackCommandProvider._preprocess_arguments  │
│                 is implemented (resolve @mentions)         │
│       Problem: IT IS NEVER CALLED                          │
│       Should: Transform @alice → alice@example.com         │
│    h. cmd.handler(ctx, **args)                             │
│       - Calls groups_command handler from registry         │
└─────────────────────────────────────────────────────────────┘
```

## Why Current Design Creates Redundancy in sre.py

**Problem:** Slack Bolt's kwargs injection and the need to dispatch subcommands create awkward patterns.

**Current sre_command signature:**

```python
def sre_command(ack, command, respond, client, body):
    # These three are identical for slash commands:
    # - body is the HTTP request body
    # - command is to_command(body)
    # - payload falls back to command
    
    # But we pass all 5 parameters to nested handlers/adapters
```

**Why this happens:**

1. Slack Bolt injects all three to sre_command (can't avoid it)
2. sre.py dispatches to nested handlers (incident_helper, webhook_helper, adapter.handle)
3. Each handler needs client and respond (so must pass payload somehow)
4. Easiest: pass entire payload dict to adapter.handle()

**The fix:** SlackCommandProvider already extracts what's needed into CommandContext; sre.py should normalize the payload before passing.

## What Changes Are Required to Slack-Specific Classes

### Change 1: SlackCommandProvider.handle() Should NOT Call super().handle()

**Current code:**

```python
def handle(self, platform_payload: Any) -> None:
    # Validate payload
    if not isinstance(platform_payload, dict):
        raise ValueError(...)
    
    required_fields = {"ack", "command", "client", "respond", "body"}
    missing = required_fields - set(platform_payload.keys())
    if missing:
        raise ValueError(...)
    
    # Just delegates to base class
    super().handle(platform_payload)
```

**Why this is problematic:**

- Base class CommandProvider.handle() calls abstract methods that SlackCommandProvider implements
- But SlackCommandProvider overrides some methods (send_error, send_help) that base class also calls
- Control flow is indirect: SlackCommandProvider → CommandProvider → back to SlackCommandProvider implementations
- Harder to reason about; harder to inject Slack-specific logic at right time

**What should happen instead:**

SlackCommandProvider should **own the orchestration** and call base class methods only as needed:

```python
def handle(self, platform_payload: Any) -> None:
    """Handle Slack command (provider owns the flow)."""
    # Validate payload
    if not isinstance(platform_payload, dict):
        raise ValueError(...)
    required_fields = {"ack", "command", "client", "respond", "body"}
    missing = required_fields - set(platform_payload.keys())
    if missing:
        raise ValueError(...)
    
    # Slack-specific orchestration:
    try:
        # 1. Acknowledge (Slack-specific: must happen within 3 seconds)
        self.acknowledge(platform_payload)
        
        # 2. Extract and tokenize (generic, but delegated to subclass)
        text = self.extract_command_text(platform_payload)
        tokens = self._tokenize(text) if text else []
        
        # 3. Framework locale for help/errors
        framework_locale = self._resolve_framework_locale(platform_payload)
        
        # 4. Handle help
        if not tokens or tokens[0] in ("help", "aide", "--help", "-h"):
            help_text = self._generate_help(framework_locale)
            self.send_help(platform_payload, help_text)
            return
        
        # 5. Ensure registry exists
        registry = self._ensure_registry()
        
        # 6. Get command
        cmd_name = tokens[0]
        cmd = registry.get_command(cmd_name)
        if cmd is None:
            error_msg = self._translate_error(
                "commands.errors.unknown_command",
                framework_locale,
                f"Unknown command: `{cmd_name}`",
                command=cmd_name,
            )
            self.send_error(platform_payload, error_msg)
            return
        
        # 7. Create context (Slack-specific: resolve user, locale, responder)
        ctx = self.create_context(platform_payload)
        
        # 8. Parse arguments
        arg_tokens = tokens[1:]
        parsed = self.parser.parse(cmd, arg_tokens)
        
        # 9. CRITICAL: Preprocess arguments (Slack: resolve @mentions)
        preprocessed = self._preprocess_arguments(ctx, parsed.args)
        if preprocessed is None:
            return  # Error already sent to user by preprocessing
        
        # 10. Execute handler
        cmd.handler(ctx, **preprocessed)
        
    except CommandParseError as e:
        framework_locale = self._resolve_framework_locale(platform_payload)
        error_msg = str(e)
        self.send_error(platform_payload, error_msg)
        logger.warning("command_parse_error", error=str(e))
    except Exception as e:  # pylint: disable=broad-except
        framework_locale = self._resolve_framework_locale(platform_payload)
        error_msg = self._translate_error(
            "commands.errors.internal_error",
            framework_locale,
            "An error occurred processing your command.",
        )
        self.send_error(platform_payload, error_msg)
        logger.exception("unhandled_command_error", error=str(e))
```

**Benefits:**

- SlackCommandProvider explicitly controls the flow
- All Slack-specific concerns in one place (ack within 3s, respond utility handling)
- Preprocessing step is clearly visible and called
- Error handling and framework locale resolved within Slack context
- Base class is simplified to be truly generic (other platforms can inherit or not)

### Change 2: Make _preprocess_arguments a Required Invocation Point

**Current state:**

- Base class defines `_preprocess_arguments()` as optional hook
- SlackCommandProvider implements it to resolve @mentions
- But base class `handle()` calls it; SlackCommandProvider delegation to base class means... it should be called

**Issue:** Looking at base class code again (lines 326-337 in base.py), I see preprocessing IS called:

```python
# Step 6.5: Provider-specific preprocessing
if parsed.subcommand:
    preprocessed_kwargs = self._preprocess_arguments(ctx, parsed.subcommand.args)
    if preprocessed_kwargs is None:
        return
    final_args = preprocessed_kwargs
else:
    preprocessed_kwargs = self._preprocess_arguments(ctx, parsed.args)
    if preprocessed_kwargs is None:
        return
    final_args = preprocessed_kwargs

# Step 7: Execute handler
if parsed.subcommand:
    parsed.subcommand.command.handler(ctx, **final_args)
else:
    cmd.handler(ctx, **final_args)
```

**This means:** If SlackCommandProvider calls `super().handle()`, preprocessing SHOULD happen.

**But:** SlackCommandProvider.handle() has no logic to validate preprocessing was invoked correctly. If SlackProvider were refactored to own orchestration, it must explicitly call preprocessing and handle None.

### Change 3: Update _preprocess_arguments Signature for Schema Awareness

**Current SlackCommandProvider implementation (lines 331-356):**

```python
def _preprocess_arguments(
    self,
    ctx: CommandContext,
    parsed_kwargs: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Resolve Slack @mentions to email addresses."""
    slack_client = ctx.metadata.get("slack_client")
    if not slack_client:
        return parsed_kwargs
    
    for key, value in list(parsed_kwargs.items()):
        if isinstance(value, str) and value.startswith("@"):
            resolved_email = slack_users.get_user_email_from_handle(
                slack_client, value
            )
            if not resolved_email:
                error_msg = ctx.translate(
                    "groups.errors.slack_handle_not_found",
                    handle=value,
                )
                ctx.respond(error_msg)
                return None
            parsed_kwargs[key] = resolved_email
    
    return parsed_kwargs
```

**Issue:** Preprocessing resolves ALL @mentions in all fields, not just email-type fields. Works but not explicit.

**Improvement:** Could accept schema for preprocessing to know which fields should be EmailStr:

```python
def _preprocess_arguments(
    self,
    ctx: CommandContext,
    schema: Optional[type],  # Pydantic schema, if available
    parsed_kwargs: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """Resolve Slack @mentions to email addresses, only for email fields."""
    slack_client = ctx.metadata.get("slack_client")
    if not slack_client or not schema:
        return parsed_kwargs
    
    # Get schema field info
    for field_name, field_info in schema.model_fields.items():
        if field_name not in parsed_kwargs:
            continue
        
        value = parsed_kwargs[field_name]
        # Check if field is expected to be email
        # Only resolve @mentions for email fields
        if isinstance(value, str) and value.startswith("@"):
            resolved_email = slack_users.get_user_email_from_handle(
                slack_client, value
            )
            if not resolved_email:
                error_msg = ctx.translate(
                    "groups.errors.slack_handle_not_found",
                    handle=value,
                )
                ctx.respond(error_msg)
                return None
            parsed_kwargs[field_name] = resolved_email
    
    return parsed_kwargs
```

**Changes needed:**

1. Base class `_preprocess_arguments()` signature: add optional `schema` parameter
2. Base class `handle()` calls preprocessing: pass schema to preprocessing method
3. SlackCommandProvider implements: use schema to determine which fields to preprocess

**But note:** This is an enhancement, not critical. Current implementation (resolve all @mentions) works fine if preprocessing is actually called.

### Change 4: Ensure SlackPayload Passed to handle() Is Normalized

**Current issue in sre.py:**

```python
case "groups":
    adapter = get_groups_adapter()
    cmd_copy = dict(command)
    cmd_copy["text"] = " ".join(args) if args else ""
    payload = {
        "ack": ack,
        "command": cmd_copy,      # Mutated copy of command
        "client": client,
        "respond": respond,
        "body": body,             # Still original body
    }
    adapter.handle(payload)
```

**Issue:** `body` and `command` are no longer identical after mutation. SlackCommandProvider expects them to be aligned.

**What should happen:** Normalize the payload before dispatch:

```python
case "groups":
    adapter = get_groups_adapter()
    # Update command text with remaining args
    cmd_copy = dict(command)
    cmd_copy["text"] = " ".join(args) if args else ""
    # Update body to match (since body == command for Slack)
    body_copy = dict(body)
    body_copy["text"] = " ".join(args) if args else ""
    
    payload = {
        "ack": ack,
        "command": cmd_copy,
        "client": client,
        "respond": respond,
        "body": body_copy,  # Keep aligned
    }
    adapter.handle(payload)
```

Or simpler: only pass what's needed, let SlackCommandProvider reconstruct payload:

```python
case "groups":
    adapter = get_groups_adapter()
    # Let adapter handle the Slack Bolt payload directly
    adapter.handle(
        ack=ack,
        command=command,
        client=client,
        respond=respond,
        body=body,
        args=args,  # Remaining subcommand args
    )
```

Then SlackCommandProvider reconstructs command["text"]:

```python
def handle(self, **kwargs) -> None:
    """Handle Slack command."""
    ack = kwargs.get("ack")
    command = kwargs.get("command")
    args = kwargs.get("args", [])
    
    # Reconstruct command text with subcommand args
    if args:
        command["text"] = " ".join(args)
    
    payload = {
        "ack": ack,
        "command": command,
        "client": kwargs.get("client"),
        "respond": kwargs.get("respond"),
        "body": kwargs.get("body"),
    }
    # Continue with orchestration...
```

## Summary of Required Changes

| Change | Impact | Priority | Location |
|--------|--------|----------|----------|
| SlackCommandProvider owns orchestration (don't call super.handle) | Clearer control flow, explicit preprocessing call | High | `slack.py` handle() method |
| Ensure _preprocess_arguments is called after parsing, before execution | Resolves @mentions before schema validation | High | Base class integration + slack.py |
| Add schema parameter to _preprocess_arguments signature | Explicit field-type awareness for preprocessing | Medium | Base class + slack.py |
| Normalize SlackPayload passed from sre_command dispatch | Ensures body/command stay aligned | Medium | `sre.py` dispatch logic |
| Update nested handler signatures to pass command instead of body | Eliminates redundant data passing | Low | sre.py, incident_helper.py, webhook_helper.py |

## How Slack Bolt Findings Validate This Architecture

**From the reference document:**
- Slack Bolt passes `body`, `command`, `payload` as identical objects for slash commands
- Utilities (`ack`, `respond`, `client`) are separate objects, never the same as payloads
- Best practice: use one canonical payload parameter, not redundant aliases

**Applied to centralized commands framework:**
- SlackCommandProvider should extract the single canonical command object and build CommandContext from it
- Preprocessing should happen early (after parsing, before execution) so downstream handlers receive clean, resolved values
- Nested handlers should pass specific fields (user_id, channel_id) not full payload objects
- Utilities (ack, respond, client) should be wrapped into CommandContext.responder and utilities, not passed around separately

This architecture is **consistent with Slack Bolt's own design philosophy**: resolve utilities early, use canonical data objects, avoid redundancy.
