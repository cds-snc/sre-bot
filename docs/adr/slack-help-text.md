---
title: "Slack Help Text"
status: Draft
type: Standard
tier: Tier-3
governance_domain: [application]
concerns: [architecture, api]
constrained_by: [transport-slack-delivery-mode.md, slack-command-parser.md, infrastructure-i18n.md, type-boundaries.md]
date: 2026-05-13
decision_makers:
  - SRE Team
---

# Slack Help Text

## Context and Problem Statement

Slack slash commands benefit from consistent, discoverable help text. Without a shared standard, each feature reinvents its own help format, embeds hardcoded strings, and diverges from the rest of the application's UX.

Help text generation is not a transport concern and not a parsing concern. It is a developer-tooling and UX concern: given that a feature has already declared a Pydantic argument schema (per [slack-command-parser.md](slack-command-parser.md)), the help text should be derivable from that schema automatically, rendered in Slack's Block Kit format, and localized through the I18nService.

**Constraints:**

- Help text must be derived from the same Pydantic `BaseModel` schema used for parsing — no separate help definition maintained in parallel.
- Output format is Block Kit — the only interactive text format Slack renders in command responses.
- User-facing strings are localized via the I18nService Protocol per [infrastructure-i18n.md](infrastructure-i18n.md).
- The help renderer must not depend on `slack_sdk`, `slack_bolt`, or any transport mechanism. It is testable without Slack credentials.

**Non-goals:** OperationResult rendering; slash command routing; argument parsing (that is [slack-command-parser.md](slack-command-parser.md)).

## Considered Options

1. **Schema-driven Block Kit renderer, I18nService-localized (chosen).** `help.py` accepts a Pydantic `BaseModel` class and a `Locale` and returns a Block Kit structure. Field names, types, descriptions, and defaults come from the schema; display strings are resolved through I18nService.
2. **Hardcoded help strings per feature.** Each feature defines its own help text as a string constant. Rejected — duplicates effort, produces inconsistent formatting, cannot be easily localized, and drifts from the schema when arguments change.
3. **Bolt's built-in help handling.** Bolt does not provide help text generation for slash commands. Not applicable.

## Decision Outcome

**Chosen: Option 1 — schema-driven Block Kit renderer.**

### Renderer

`app/infrastructure/slack/help.py` exposes a single function:

```python
def render_command_help(
    schema: type[BaseModel],
    locale: Locale,
    i18n: I18nService,
    command_name: str,
) -> list[dict]:
    """Return a Block Kit blocks list rendering the command's help."""
```

Input: a Pydantic `BaseModel` class (the command's argument schema), the resolved locale, the I18nService, and the command name string. Output: a `list[dict]` of Block Kit blocks ready to pass to `chat_postMessage` or `views_open`.

The renderer constructs:
- A **header block** with the command name.
- A **section block** with the usage string derived from the schema (from [slack-command-parser.md](slack-command-parser.md)'s plain-text usage output).
- One **section block per field** showing the field name, type, whether it is required or optional, its default (if any), and the field's `description` from the Pydantic `Field(description=...)` annotation.

All displayed strings (labels like "Required", "Optional", "Default:") are resolved through I18nService so that help text respects the requesting user's locale.

### Schema annotations for help

Features that want richer help text annotate their schema fields with `Field(description=...)`:

```python
class IncidentStatusArgs(BaseModel):
    action: str = Field(description="Action to perform: 'update' or 'show'")
    status: Optional[str] = Field(
        default=None,
        description="New status value. Valid: In Progress, Open, Closed, …"
    )
    verbose: bool = Field(default=False, description="Show extended output")
```

Fields without a `description` are rendered with only their name and type. The renderer never raises for a missing description; it degrades gracefully.

### Locale resolution

The requesting user's locale is resolved from `BoltContext` (Slack provides a `locale` hint on most payload types) or from a `users.info` lookup. The resolved `Locale` is passed to the renderer; the renderer does not access `BoltContext` directly.

### Placement

`app/infrastructure/slack/help.py` imports only `pydantic`, `slack_sdk.models.blocks` (pure-data model classes, permitted by the import carve-out in [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md)), and the I18nService Protocol. No transport imports. Independently testable.

## Consequences

**Positive:**

- Help text is always in sync with the argument schema — no separate maintenance.
- Consistent Block Kit format across all Slack commands.
- Localized without per-feature i18n work; features only supply `description` strings.
- The renderer is independently testable; no Slack credentials or Bolt app required.

**Tradeoffs accepted:**

- Features that want highly customized help layouts (custom sections, examples, links) must supplement the schema-derived output with additional blocks. The renderer produces a baseline; features can extend it.
- The renderer uses `Field(description=...)` for per-field descriptions — fields without this annotation get minimal help. This is an opt-in improvement, not a mandatory requirement.

**Risks:**

- A schema field's `description` is written in a non-localizable hardcoded string. Mitigation: I18nService accepts translation keys; features that localize descriptions should use keys. Features that don't localize get English-only field descriptions, which is acceptable at this stage.

## Confirmation

- `app/infrastructure/slack/help.py` imports only `pydantic`, `slack_sdk.models.*`, and the I18nService Protocol. No `slack_sdk.web.*`, `slack_bolt.*`, or transport imports.
- Unit tests cover: command with all field types; required vs optional fields; default values; missing descriptions; locale switching produces different label strings.
- Integration test asserts that `render_command_help(IncidentStatusArgs, locale="fr-FR", ...)` returns valid Block Kit that Slack accepts (no `SlackObjectFormationError`).

## Source References

1. Slack — Block Kit: Blocks reference
   - URL: <https://docs.slack.dev/reference/block-kit/blocks>
   - Accessed: 2026-05-13
   - Relevance: Block types used in the help renderer output (header, section, divider, context).

2. Slack Python SDK — `slack_sdk.models` (Block Kit classes)
   - URL: <https://docs.slack.dev/tools/python-slack-sdk/reference/models/blocks/>
   - Accessed: 2026-05-13
   - Relevance: Typed Block Kit classes used by the renderer; pure-data, no transport dependency.

3. Pydantic — Field
   - URL: <https://docs.pydantic.dev/latest/concepts/fields/>
   - Accessed: 2026-05-13
   - Relevance: `Field(description=...)` annotation used for per-field help text; grounds the schema-annotation convention.

## Change Log

- 2026-05-13: Created by splitting help-text content out of [transport-slack.md](transport-slack.md). Help text generation is not a transport concern — it has no dependency on Slack's SDK delivery mechanism or `AsyncWebClient`.
