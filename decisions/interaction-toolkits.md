---
status: Draft
date: 2026-09-24
applies: target
scope: Whether each chat platform gets a host-owned interaction toolkit that feature entry points use for rich interactions, and the limits on such a toolkit.
---

# Interaction Toolkits

## Context

Features serve each chat platform with their own handlers in `entrypoints/<platform>.py` ([platform-transports.md](platform-transports.md)). A platform-neutral command model was tried and failed on rich dialogs and on concepts the platforms don't share.

Per-platform handlers then re-implement the same hard parts by hand, each slightly differently: acknowledgement deadlines, dialog state, updating a message a user acted on, replies through expiring response channels, platform limits, rate limits, duplicate deliveries, error rendering and translation. Today feature and legacy handlers call Bolt's `client`, `respond` and `ack` directly, 174 call sites across `packages/` and `modules/`.

No off-the-shelf library covers these conventions. Bolt and `slack_sdk.models` provide the runtime and Block Kit types; third-party builders (blockkit) add validation; bot frameworks (Slack Machine) compete with the plugin architecture instead of fitting inside it. Microsoft's Teams SDK for Python reached general availability in May 2026, with Pydantic Adaptive Card models (`microsoft-teams-cards`) and dialogs.

The app already paid for wrapping SDKs: the Google API client and boto3 wrappers had to replicate every SDK feature and were deleted ([outbound-clients.md](outbound-clients.md), [sdk-typing.md](sdk-typing.md)).

## Decision (proposed)

**Each chat platform may get an interaction toolkit**, with its contract in `app/contracts/<platform>/` and its implementation in `app/server/<platform>/`. Feature entry points use it for the conventions it covers and never re-implement those by hand. For anything else they use the SDK's documented objects handed to them by the runtime.

**A toolkit is not a wrapper around the platform SDK.** It adds only conventions the SDK does not have, composed on the SDK's documented calls, and receives the SDK's own objects (for Slack: Bolt's `ack`, `client` and `respond`). It never mirrors, re-exposes or patches the SDK's surface, and never re-implements what the SDK already does (verification, retry handlers, pagination, Block Kit or Adaptive Card models, lazy listeners). It does not grow a method to forward an SDK call a handler needs; a method that only passes arguments through to one SDK call is deleted.

**A platform contract may use that platform SDK's pure-data model types** (Block Kit models, Adaptive Card models), never anything that does I/O. This does not need an exception if [plugin-architecture.md](plugin-architecture.md)'s `contracts/` rule is stated by the properties it protects rather than as a list of allowed packages. On acceptance of this record, that rule would read:

> `contracts/` holds no implementation, does no I/O and imports nothing else from the app. It may depend on third-party pure-data or type-only packages only in the subpackage whose subject they are: `pluggy` for hookspecs, a platform SDK's model types for that platform's contract.

The `pluggy` allowance and a platform's model types are then the same kind of dependency, and platform types stay out of the platform-neutral contracts.

**A toolkit is built when the first feature needs it, from that feature's real needs.** Its API speaks the platform's own concepts and does not pretend platforms are alike.

**The Slack toolkit would cover only:**
- acknowledgement within Slack's 3-second deadline, with the handler's work run afterwards;
- modals: open, update and push; typed state in `private_metadata`; field-level validation errors; stale updates rejected using the view hash;
- messages: `chat.update` of the message a user acted on (so a double click is idempotent), ephemeral versus public replies, threads;
- replies: `response_url` handling that knows it expires after 30 minutes and 5 uses, with a direct-message fallback, and one rendering of an `OperationResult` error;
- limits and resilience: Block Kit limits checked before sending, rate limits classified through `classify_slack_error`, Slack's retry headers used to drop duplicate deliveries;
- translation through the translator contract in the user's locale.

## Open before acceptance

- **Toolkit, shared helpers or conventions only.** Is a host-owned toolkit worth its cost, or do a few documented conventions plus lint checks (no manual `ack()` after work, no raw `response_url` posts) give most of the benefit?
- **Proof on real features.** Build the Slack conventions for one or two rebuilt features first (for example `incident_draft` and `user_rotations`, the feature packages that call Bolt's client directly today), and decide from what they actually needed.
- **Staying thin over time.** How the no-wrapper rule is enforced in review once the toolkit has several consumers.
- **Teams.** Whether a Teams toolkit is needed at all, decided when the first Teams feature exists.

## Consequences

- If accepted: rich interactions behave the same in every feature, and platform limits and failure modes are handled once.
- Cost: host code to maintain per platform, and one more contract features must learn.
- Risk: the toolkit drifts into a wrapper. The no-wrapper rule, and deleting pass-through methods, are the mitigation.

## Checks

- Review: every toolkit method adds a convention; a method that only forwards its arguments to one SDK call is rejected.
- grep: feature Slack entry points never call `ack()` after doing work, and never post to a `response_url` directly.

## Migration

Tickets are created on acceptance. Tolerated until then: handlers calling Bolt's `client`, `respond` and `ack` directly.
