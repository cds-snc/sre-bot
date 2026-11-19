# Text generation

Text produced from a source and the caller's instructions, in feature-free vocabulary: the
caller supplies the source (a transcript, a draft), the instructions and any post-processing.
`api.py` exposes the `TextGenerator` Protocol (`is_available()`, and async
`generate(source, *, instructions, max_output_tokens=None)` returning an `OperationResult[str]`)
and the provider `get_text_generator()`.

The capability is always present. With an `[openai.tenant]` entry the generator is the OpenAI
adapter; without one it answers `is_available()` false and `TEXT_GENERATION_UNAVAILABLE` on every
call, so a consumer offering an optional action asks `is_available()` first, and a consumer that
requires it declares `Requirement("openai.tenant")` (decisions/plugin-architecture.md).

`adapters/openai.py` is the only module that imports `integrations.openai`, besides the host's
settings reads in `server/` (import-linter contract (o)); a new model vendor is another adapter
here. `adapters/in_memory.py` is the fake, run through the same conformance suite.

The `text_generation` enablement key switches only `plugin.py`, never `api.py`, which features
import whether it is on or off; it switches nothing yet, since the plugin module declares no
requirement and registers no surface (decisions/plugins.md).

## Classification

generic

## Feature consumers

- features.incident.scribe
- features.incident.comms
