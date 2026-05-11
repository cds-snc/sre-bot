---
title: "Teams Transport"
status: Draft
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [api, architecture, plugins]
constrained_by: [layered-architecture.md, dependency-injection.md, configuration-ownership.md, application-lifecycle.md, plugin-registration-discovery.md, feature-package-structure.md, cross-channel-correlation.md, multi-transport-architecture.md, operation-result-pattern.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Teams Transport

## Context and Problem Statement

This record will specify how Microsoft Teams is integrated as a first-class platform: the SDK choice, the connection and channel lifecycle, the hookspec catalogue features ship handlers against, the verification and authentication contract for inbound deliveries, and the shape of the platform's infrastructure service that the host owns at the composition root.

Teams is **one of several platforms** the application supports; this record makes Teams-specific decisions and does not generalize. The transport-agnostic pattern is owned by `multi-transport-architecture.md`.

**Anticipated scope:**

- **SDK choice.** The Microsoft Bot Framework SDK for Python is archived (legacy lifecycle ended). The successor is the Microsoft 365 Agents SDK (`microsoft-agents-hosting-fastapi` and adjacent packages). This record selects the supported SDK, pins the minimum version, and documents the migration posture if any legacy integration is being replaced.
- **Hookspec catalogue.** Teams' native method categories — bot messages (text, attachments), card actions (Adaptive Card `Action.Submit` and other action types), invoke activities (e.g., task module fetch/submit, message extension query/submit), installation-update activities. Each category gets a dedicated hookspec. Anticipated names: `register_teams_message`, `register_teams_card_action`, `register_teams_invoke`, `register_teams_installation_update`. Other categories added as needed.
- **Authentication and verification.** JWT validation on inbound activities; the role of the bot's app-id and signing keys; rotation policy; failure mode.
- **`TeamsAgent` infrastructure-service shape.** What the service exposes (a Protocol with the outbound operations the application uses — sending messages, updating cards, opening task modules); how its providers wire it; whether reused across features (Path B per cloud-portability) or split per feature.
- **Adaptive Cards as the primary interaction surface.** How card payloads are constructed (centralized templates vs. per-feature); how `Action.Submit` data is shaped to carry feature-domain identifiers (per the cross-channel-correlation distinction between observability `request_id` and durable domain identifiers); rendering versus parsing rules.
- **Conversation state.** Bot Framework conversation-state semantics (last-write-wins, archived in newer SDKs) and the rule that the application does not rely on it as a correlation carrier — durable domain identifiers travel via Adaptive Card action data, not conversation state.

**Explicit non-goals:**

- This record does not generalize to other platforms.
- This record does not specify per-handler implementation discipline.
- This record does not redefine plugin discovery or feature-package layout.
- This record does not specify which Microsoft tenants, app IDs, or bot resources the application is deployed against — that is configuration.

## Considered Options

TODO

## Decision Outcome

TODO

## Consequences

TODO

## Confirmation

TODO

## Source References

1. TODO. Anticipated:
   - Microsoft 365 Agents SDK for Python (the supported successor to the archived Bot Framework SDK)
   - Microsoft — Authentication for Teams bots
   - Microsoft — Adaptive Cards reference

## Change Log

- 2026-05-08: Created as placeholder. Teams is treated as a first-class platform with its own SDK choice (the Bot Framework SDK for Python being archived motivates an explicit selection), hookspec catalogue, authentication contract, and infrastructure-service shape. Conversation-state-as-correlation-carrier is rejected; durable domain identifiers travel via Adaptive Card `Action.Submit` data per `cross-channel-correlation.md`.
