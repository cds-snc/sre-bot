---
title: "Slack Command Parser"
status: Draft
type: Standard
tier: Tier-3
governance_domain: [application]
concerns: [architecture, api]
constrained_by: [transport-slack.md, type-boundaries.md, operation-result-pattern.md]
date: 2026-05-13
decision_makers:
  - SRE Team
---

# Slack Command Parser

## Context and Problem Statement

Slack delivers slash command arguments as a single unstructured text blob — the raw text typed after the command name (e.g., `/sre incident status update Ready to be Reviewed`). The application needs to extract structured, validated arguments from this blob before any business logic runs.

This is not a transport concern. The parsing problem — tokenizing a string, extracting flags and named options, validating required fields, applying defaults — is a generic structured-input problem. It happens to arise at the Slack command boundary, but the parser itself has no dependency on the Slack SDK, `AsyncWebClient`, or Bolt.

**Constraints:**

- Feature code must not reimplement tokenization or validation per-command. The parser is shared infrastructure.
- Argument schemas are feature-owned. The parser must accept an arbitrary schema definition from each feature.
- Parse failures must surface as a `PERMANENT_ERROR` `OperationResult` with a user-displayable message, not as a raised exception that the handler must catch.
- The schema definition serves double duty: validation input and help-text source. See [slack-help-text.md](slack-help-text.md).

**Non-goals:** routing of parsed commands to handlers (that is the responsibility of [transport-slack.md](transport-slack.md) and the pluggy hookspec); rendering of parse errors into Block Kit (that is [transport-slack.md](transport-slack.md) §Help text and `OperationResult` rendering); MS Teams or any other platform (command parsing for other platforms is out of scope for this record).

## Considered Options

1. **Pydantic-model-driven parser with quote-aware tokenization (chosen).** Each feature declares its argument schema as a `BaseModel`. The shared parser tokenizes the raw text, matches tokens to fields, validates, and returns the populated model or a typed failure.
2. **argparse / click per-command.** Standard library tooling for CLI argument parsing. Rejected — argparse exits the process on parse failure (incompatible with an async web server), and click requires structuring commands as click groups rather than Pydantic models, adding a dependency and diverging from the corpus's `BaseModel`-at-trust-boundaries rule.
3. **Free-form string passed directly to handlers.** No parsing layer. Rejected — each feature would reimplement tokenization and validation, and Slack command UX would be inconsistent across features.

## Decision Outcome

**Chosen: Option 1 — Pydantic-model-driven parser.**

### Schema definition

Each feature declares its command's argument schema as a Pydantic `BaseModel` per [type-boundaries.md](type-boundaries.md). Fields map directly to the arguments the command accepts:

```python
# app/packages/incident/adapters/slack/schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class IncidentStatusArgs(BaseModel):
    action: str                                      # positional: "update" or "show"
    status: Optional[str] = None                     # positional: the new status value
    verbose: bool = Field(default=False)             # flag: --verbose
```

Pydantic handles field types, defaults, and validation constraints. The parser does not duplicate these rules.

### Tokenization rules

The parser in `app/infrastructure/slack/parsing.py` applies the following tokenization rules to the raw command text:

| Input form | Behaviour |
| --- | --- |
| `--flag` | Boolean flag; sets the corresponding `bool` field to `True`. |
| `--key value` | Named option; binds `value` to the `key` field. |
| `--key v1,v2,v3` | Multi-value option; binds a list to the `key` field. |
| `"quoted string"` | Treated as a single token; quotes are stripped. |
| Remaining tokens | Assigned positionally to fields in schema declaration order. |

Tokenization is quote-aware: a quoted string containing spaces is a single token. This is necessary for natural command invocation (e.g., `/sre incident products create "my product name"`).

### Parse result

The parser returns either the populated `BaseModel` instance or a typed `ParseFailure` containing a human-readable message suitable for display. The `SlackService` boundary maps `ParseFailure` to `OperationResult.permanent_error(message=..., error_code="parse_error")`. Handlers receive an `OperationResult` and never deal with parse exceptions directly.

### Help text derivation

The parser derives a usage string from the schema's field names, types, and descriptions. This is the source for the help text rendered by [slack-help-text.md](slack-help-text.md). The parser does not render Block Kit; it produces a plain-text usage string.

### Placement

The parser lives at `app/infrastructure/slack/parsing.py`. It imports only `pydantic` and standard library modules — no `slack_sdk`, no `slack_bolt`, no transport dependencies. It can be unit-tested entirely without Slack credentials or a Bolt app.

## Consequences

**Positive:**

- Consistent argument parsing across all Slack commands. Features declare schemas; the parser handles all tokenization, validation, and default substitution.
- Feature schemas are Pydantic `BaseModel` instances — the same trust-boundary type used everywhere else in the corpus.
- Parse failures surface as `OperationResult` before reaching the feature service layer. The feature service never sees a raw string or a raised parse exception.
- The parser is independently testable with no Slack dependency.

**Tradeoffs accepted:**

- Features must declare explicit schemas for their commands. There is no "pass the raw string to the handler" escape hatch. This is intentional; structured schemas are the point.
- The tokenization rules are simpler than full shell quoting (`shlex`). Edge cases (nested quotes, escape sequences) are not supported. Slack command UIs are typically simple; full shell quoting is not needed.

**Risks:**

- A feature schema uses a field type the parser does not support (e.g., `datetime`, `UUID`). Mitigation: the parser supports `str`, `int`, `float`, `bool`, `Optional[T]`, and `list[T]`; unsupported types raise a `SchemaError` at parser construction time, not at parse time.
- The tokenization rules produce an ambiguous parse for a specific command shape. Mitigation: each schema is tested against a representative set of raw command strings in the feature's own test suite.

## Confirmation

- `app/infrastructure/slack/parsing.py` imports only `pydantic` and stdlib. No `slack_sdk` or `slack_bolt` imports.
- Parser unit tests cover: flag setting, named option binding, multi-value option, quoted strings, positional assignment, missing required field, type coercion failure, default substitution.
- Each feature that uses the parser has at least one test asserting the schema parses a representative command string to the expected `BaseModel` instance.

## Source References

1. Pydantic — Models
   - URL: <https://docs.pydantic.dev/latest/concepts/models/>
   - Accessed: 2026-05-08
   - Relevance: `BaseModel` as the trust-boundary type for structured input; field-level validation and defaults. Grounds the schema-as-BaseModel rule.

2. Slack — Slash Commands
   - URL: <https://docs.slack.dev/interactivity/slash-commands>
   - Accessed: 2026-05-13
   - Relevance: Documents that slash command arguments are delivered as a single `text` field (raw string blob). Grounds the need for a shared tokenization layer.

## Change Log

- 2026-05-13: Created by splitting slash-command-argument-parsing content out of [transport-slack.md](transport-slack.md). This concern is not a transport concern — the parser has no dependency on Slack's SDK or delivery mechanism.
