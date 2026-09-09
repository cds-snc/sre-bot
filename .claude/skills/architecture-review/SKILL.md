---
name: architecture-review
description: App-level architecture review producing options, source-cited decision-record updates, and backlog tasks for the resulting work.
argument-hint: "[question or proposed change]"
disable-model-invocation: true
---

# App-Level Architecture Review

Review at app level: `$ARGUMENTS`.

**Run as**: `architecture` agent · Tier M (Claude Sonnet 5).

Set and maintain long-horizon architecture decisions so feature work can rely on
local `decisions/` records instead of repeated web research. Produce no
implementation details and no code changes.

## Steps

1. Clarify app-level goals, constraints and non-goals with targeted questions.
2. Read the relevant records under `decisions/` **before** any web research,
   noting each record's last-updated date.
3. Run web research for any applicable record older than **30 days**, plus any
   missing or outdated standards (FastAPI, Python typing, Pydantic, settings,
   validation, startup patterns). Batch the research; do not trickle queries.
4. Propose 2-3 options with tradeoffs and lifecycle impact.
5. Recommend one, with adoption criteria.
6. Update or create decision records with date, status, rationale, alternatives,
   consequences and **cited sources**.
7. Capture the resulting implementation work as backlog tasks via the CLI
   (`backlog task create ... --ref decisions/<record>.md --dep --parent`) — never
   as a chat-only to-do list.
8. Hand off to `/feature-architecture` with concrete constraints and references.

## Hard Constraints

- `decisions/` is the first source of truth; web research fills gaps and refreshes
  stale guidance, it does not override a current ADR.
- A record older than 30 days is stale for standards alignment and needs a
  web-validated freshness check before reuse.
- Any newly added or revised guidance must carry source references.
- Ignore legacy signals from `app/modules`.
- Mutate backlog tasks only through the CLI.

## Output

Context and scope boundaries · records reviewed and their current relevance ·
standards gaps and external references consulted · freshness audit (checked,
refreshed, deferred-with-reason) · 2-3 options with tradeoffs · chosen approach and
why · risks and mitigations · decision-record update plan · backlog tasks created ·
feature-architecture handoff packet.
