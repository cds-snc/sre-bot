# AI writing

A language model writes text (a summary, a draft, a template filled section by section) from a
source and the caller's instructions, in feature-free vocabulary: the caller supplies the source
(a document, a draft, a message log), the instructions and any post-processing. `api.py` exposes
the `AIWriter` Protocol and the provider `get_ai_writer()`:

- `is_available()`;
- async `write(source, *, instructions, max_output_tokens, temperature=None)` returning an
  `OperationResult[str]`;
- async `fill_template(source, *, sections, instructions, max_output_tokens, temperature=None,
  fields=())` returning an `OperationResult[FilledTemplate]`: one `TemplateAnswer` per requested
  `TemplateSection` and `TemplateField` in order (`""` when unanswered), and `truncated` when the
  model's answer was cut off and only its complete pairs were kept. The caller's instructions ask
  for one JSON object keyed by heading; the capability renders the request (sections, fields, then
  the source last and verbatim) and reads the answer forgivingly (code fences, prose around it,
  list values, heading drift). Nothing usable is a permanent `AI_WRITING_UNPARSEABLE`.

Every caller states its own completion budget; a temperature is sent only when the call sets one,
since some models reject the parameter outright. `extract_json_object(raw)` is the strict first
stage alone (the first complete JSON object, never coerced or salvaged) for a caller that refuses
any partial answer. `service.py` holds the template fill; every adapter delegates to it, so writers
differ only in how `write` reaches a model.

Logs carry the answer's shape only (lengths, counts, whether an object was found): source text and
model output are content and are never logged (decisions/observability.md).

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
