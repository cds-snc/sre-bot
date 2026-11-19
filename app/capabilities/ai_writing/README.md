# AI writing

A language model writes text (a summary, a draft, a template filled section by section) from a
source and the caller's instructions, in feature-free vocabulary: the caller supplies the source
(a transcript, a draft), the instructions and any post-processing. `api.py` exposes the `AIWriter`
Protocol (`is_available()`, and async `write(source, *, instructions, max_output_tokens,
temperature=None)` returning an `OperationResult[str]`) and the provider `get_ai_writer()`.
Every caller states its own completion budget; a temperature is sent only when the call sets one,
since some models reject the parameter outright.

That is its only purpose. Any other AI use (classifying, extracting, searching) is a separate
capability named for its purpose, sharing the vendor integration; adding it to import-linter
contract (o)'s allowed importers makes that a reviewed change (decisions/plugin-architecture.md).

The capability is always present. With an `[openai.tenant]` entry and an `[ai_writing]` model the
writer is the OpenAI adapter; without either it answers `is_available()` false and
`AI_WRITING_UNAVAILABLE` on every call (logging `ai_writing_unconfigured` or
`ai_writing_model_unset` once, when the writer is built), so a consumer offering an optional action
asks `is_available()` first, and a consumer that requires it declares `Requirement("openai.tenant")`
and `Requirement("ai_writing.model")` (decisions/plugin-architecture.md).

`[ai_writing]` `model` (env `AI_WRITING__MODEL`) is the model the endpoint writes with. It is the
deploying organisation's value, so base.toml leaves it empty and the environment file sets it
(decisions/configuration.md); the OpenAI vendor slice holds only the connection.

`adapters/openai.py` is the only module that imports `integrations.openai`, besides the host's
settings reads in `server/` (import-linter contract (o)); a new model vendor is another adapter
here. `adapters/in_memory.py` is the fake, run through the same conformance suite.

The `ai_writing` enablement key switches only `plugin.py`, never `api.py`, which features import
whether it is on or off; it switches nothing yet, since the plugin module declares no requirement
and registers no surface (decisions/plugins.md).

## Classification

generic

## Feature consumers

- features.incident.scribe
- features.incident.comms
