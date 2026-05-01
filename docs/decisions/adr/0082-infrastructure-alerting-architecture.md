# ADR-0082: Infrastructure Alerting Architecture

---
adr_id: ADR-0082
title: "Infrastructure Alerting Architecture"
status: Accepted
decision_type: Integration Decision
tier: Tier-4
governance_domain: infrastructure
primary_domain: "Observability and Operations"
secondary_domains:

- "Delivery and Environment Parity"
owners:
- SRE Team
date_created: 2026-05-01
last_updated: 2026-05-01
last_reviewed: 2026-05-01
next_review_due: 2026-08-29
constrained_by:
- ADR-0044
- ADR-0080
- ADR-0054
- ADR-0081
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records:
- ADR-0052
- ADR-0067
related_packages: []

---

## Context

### Problem statement

The SRE Bot is the operational alerting hub for multiple products. External systems deliver events to the bot, which processes them and sends structured Slack notifications based on internal business logic. **When the SRE Bot itself is unavailable — due to a deployment failure, silent misconfiguration, or startup error — it cannot notify the team of its own failure.** The watchman cannot report that it is dead.

This creates a critical operational blind spot: if the bot successfully deploys but is silently broken (e.g., a configuration change breaks its ability to POST to Slack, a dependency is unreachable, or ECS replaces healthy tasks with broken ones that pass container health checks but cannot function), hours may pass before anyone notices. Since other products rely on the SRE Bot to alert them about their own incidents, a silent bot failure cascades into undetected incidents across the organization.

**There is currently no independent fallback mechanism.** The SRE Bot is the only system that sends actionable Slack notifications. If the bot is down, no other component exists to alert the team.

A fallback alerting mechanism is required that is **completely independent** of the SRE Bot application — a dead-man's-switch that operates without any dependency on the application's availability, codebase, or runtime.

#### Current state

When the SRE Bot is healthy, it functions as the alerting hub: it receives events from external systems, processes them through internal business logic, and posts formatted, actionable Slack notifications. The existing infrastructure monitoring works within this model — CloudWatch alarms fire, and the bot's operational context makes those signals meaningful.

The infrastructure has standard CloudWatch monitoring in place:

```
CloudWatch Alarm → SNS Topic → HTTPS Subscription → Slack Webhook URL
```

| Alarm | Signal Source | Trigger | Threshold |
|-------|--------------|---------|-----------|
| SRE Bot Errors | Log metric filter (`?ERROR ?Exception`) | Sum in 60s period, 1 eval period | ≥1 (configurable) |
| SRE Bot Warnings | Log metric filter (`WARNING`) | Sum in 60s period, 1 eval period | ≥10 (configurable) |
| SRE Bot High CPU | ECS `CPUUtilization` metric | Max in 60s period, 5 eval periods | ≥80% |
| SRE Bot High Memory | ECS `MemoryUtilization` metric | Max in 60s period, 5 eval periods | ≥80% |

All four alarms route to a single SNS topic (`sre-bot-cloudwatch-alarms-warning`) with one subscriber: an HTTPS endpoint posting to `var.slack_webhook_url`. The ECS service also has deployment alarms (`alarms` block) with rollback enabled for CPU and memory alarm breaches during deployment.

**ECS task failure detection gap:** The ECS task definition does not define a container-level health check (`healthCheck` block). Task health is determined solely by the ALB target group health check. There is no CloudWatch alarm that detects when the running task count drops below the desired count (2). A task that crash-loops, fails to start, or passes initial ALB health checks but fails minutes later will not trigger any of the existing alarms unless it also causes a CPU/memory spike. Container Insights is enabled on the cluster (`containerInsights = "enabled"`), which provides `ECS/ContainerInsights` namespace metrics including `RunningTaskCount` — but no alarm consumes this metric today. The deployment circuit breaker (`deployment_circuit_breaker`) is also not enabled; only the `alarms` block protects deployments.

This monitoring is adequate during normal operations. The problem arises specifically when the bot itself is down — and that is the one scenario where no independent mechanism exists to alert the team. **There is no fallback.** The bot is the only system that delivers actionable notifications. If it is unavailable, the CloudWatch → SNS → Webhook path still fires, but there is no system designed to ensure the team is reliably and clearly notified that the bot itself has failed.

The gap is not the quality of the existing monitoring — it is the complete absence of a dead-man's-switch.

### Business/operational drivers

- **Cascading failure risk:** Other products depend on the SRE Bot for incident alerting. A silent bot failure means not just bot alerts are missed — alerts from all dependent products are missed. The operational blast radius of an undetected bot failure is organization-wide.
- **Detection latency:** Without independent fallback alerting, the typical detection path is a human noticing that Slack is quiet — which can take minutes to hours depending on time of day and workload.
- **ADR-0054 compliance:** ADR-0054 establishes that the application emits logs and the platform routes and stores them. The fallback alerting path is a platform-domain responsibility — it must function even when the application cannot.
- **ADR-0080 boundary:** This ADR governs an infrastructure-domain component. The fallback alerting mechanism is independent of the SRE Bot application. ADR-0067 (Slack Transport Integration Decision) explicitly excludes infrastructure components deployed independently of the FastAPI process from its scope (2026-05-01 amendment).
- **ADR-0045 P7:** The managed service delegation hierarchy (managed cloud service > library > custom code) must be applied to the choice of alerting delivery mechanism.

### Constraints

- The fallback path must have **zero dependency on the SRE Bot application** — no shared code, no shared runtime, no shared Slack identity lifecycle.
- The fallback path should minimize internet-facing surface area. The ideal is a fully AWS-internal pipeline with only the necessary outbound Slack API call.
- For Option A (Q Developer), the Slack identity is the **AWS Chatbot Slack app** — a separate, AWS-managed application authorized during the one-time workspace setup. Notifications appear from "AWS Chatbot" in Slack, not from the SRE Bot. The SRE Bot's `SLACK_BOT_TOKEN` is not used.
- For Option B (Lambda escalation path, if activated), the SRE Bot's bot token (`SLACK_BOT_TOKEN`) is available as the app identity for posting messages via `chat.postMessage` (user-confirmed: same bot token as SRE Bot app).
- Channel routing must be configurable via environment variables or Terraform variables, not hardcoded.
- Failed notification delivery must have a dead-letter queue with a CloudWatch alarm on DLQ depth.
- The mechanism must be lightweight — not a second full application deployment.

### Non-goals

- Replacing the SRE Bot's primary alerting functionality. The bot remains the primary alerting hub for all products.
- Defining which specific CloudWatch alarms to create. The ADR defines alarm class taxonomy and delivery architecture; specific alarms are Terraform-level implementation.
- Application-level health check design. How the app exposes health status is an application-domain concern.
- Multi-channel Slack workspace support. Single workspace is sufficient for current operations.

## Decision

### Chosen approach: Option A — Amazon Q Developer (AWS Chatbot) with Lambda fallback path reserved

Adopt Amazon Q Developer in chat applications (AWS Chatbot) as the primary infrastructure fallback alerting mechanism. This is the managed cloud service approach per ADR-0045 P7 Tier 1.

**Architecture:**

```
CloudWatch Alarms ──→ SNS Topic(s) ──→ Amazon Q Developer ──→ Slack Channel(s)
                                              │
                                    [Managed formatting,
                                     delivery, retry]
```

**Implementation requirements:**

1. **Slack workspace authorization:** One-time manual authorization of the AWS account with the Slack workspace via the AWS Console. This creates the workspace binding that Terraform references via the `aws_chatbot_slack_workspace` data source.

2. **Alarm class taxonomy:** CloudWatch alarms are classified into severity tiers. Each tier routes to a dedicated SNS topic and Q Developer channel configuration.

   | Alarm Class | Description | Example Signals | Routing |
   |-------------|-------------|-----------------|---------|
   | **Critical** | App unable to serve or self-alert | Error log spike, running tasks below desired count, all tasks unhealthy, deployment failure, connectivity loss | Dedicated critical-ops channel |
   | **Warning** | Degraded but operational | High CPU/memory, elevated warning count, slow health check response | Standard ops channel |
   | **Informational** | State transitions, recovery | Alarm OK transitions, deployment success, scaling events | Same ops channel, lower urgency |

3. **SNS topic separation:** One SNS topic per alarm class to enable class-based channel routing through separate Q Developer configurations. The existing `sre-bot-cloudwatch-alarms-warning` topic may be repurposed or replaced.

4. **Q Developer channel configurations:** One `aws_chatbot_slack_channel_configuration` per target Slack channel, each mapped to the appropriate SNS topic ARN(s). Channel IDs are Terraform variables (configurable, not hardcoded).

5. **IAM role and guardrail policy (MANDATORY):** A dedicated IAM role for Q Developer with least-privilege permissions (CloudWatch read-only, no administrative access). **`guardrail_policy_arns` MUST be explicitly set** — the Terraform default is `AdministratorAccess`, which would grant every member of the connected Slack channel the ability to run arbitrary AWS CLI commands from Slack. The guardrail policy MUST be set to `arn:aws:iam::aws:policy/ReadOnlyAccess` or a more restrictive custom policy. For a notification-only use case, no interactive AWS CLI commands from Slack are needed.

6. **Logging:** Q Developer logging level set to `ERROR` to capture delivery failures in CloudWatch Logs.

7. **Remove webhook subscription:** The existing SNS → HTTPS (Slack webhook) subscription is retired. Q Developer replaces it as the sole subscriber for alarm notifications.

8. **ECS task failure alarm:** A new **Critical** class CloudWatch alarm on the `RunningTaskCount` metric (namespace `ECS/ContainerInsights`, dimensions `ClusterName` + `ServiceName`) must be created. The alarm fires when running tasks fall below the desired count for a sustained period (recommended: 3 evaluation periods × 60s = 3 minutes). This directly detects the dead-man-switch scenario — the bot's tasks are down. This alarm routes to the Critical SNS topic and Q Developer critical-ops channel.

### Governance hardening requirements

The AWS Chatbot Slack app requests workspace-wide OAuth scopes including `chat:write.public` (post to any public channel without membership), `users:read`, and `team:read`. These scopes are granted at the workspace level during authorization and cannot be narrowed per-channel. The following governance controls mitigate the risk:

1. **Restrictive guardrail policy (see item 5 above).** `guardrail_policy_arns` MUST be set to `ReadOnlyAccess` or a custom deny-all-interactive policy. This is a hard requirement, not a recommendation.

2. **Notification-only channel role.** Q Developer supports a "Notification permissions" channel role template. The channel configuration MUST use the notification-only role, which restricts the channel to receiving alarm notifications without enabling interactive AWS CLI commands from Slack.

3. **`user_authorization_required` enforcement.** The AWS Chatbot account-level setting `user_authorization_required` SHOULD be set to `true`. This forces individual IAM identity mapping before any workspace member can run interactive commands — a defense-in-depth control that applies even if the guardrail policy is misconfigured.

4. **Dedicated private Slack channel.** The ops channel receiving Q Developer notifications MUST be a **private** channel with controlled membership. Since the AWS Chatbot Slack app has `chat:write.public` scope, using a public channel would allow any workspace member to observe infrastructure alerts. A private channel limits visibility to authorized operators.

5. **Slack workspace admin app approval.** The AWS Chatbot Slack app installation SHOULD be approved through the Slack workspace admin's app management controls (not silently self-installed). This ensures organizational visibility into which AWS integrations are active.

### Why this approach

1. **ADR-0045 P7 compliance.** Managed cloud service (Tier 1) is preferred over custom code (Tier 3). Q Developer natively solves the core problems (raw JSON → formatted messages, managed delivery) without custom Lambda code.
2. **Zero operational burden.** No custom code to write, test, deploy, or maintain. No Lambda runtime updates, no dependency management, no CI/CD pipeline for alerting code.
3. **Terraform-native.** Full resource support via `aws_chatbot_slack_channel_configuration`. Infrastructure-as-code compliant per ADR-0081 S6.
4. **Sufficient for the fallback use case.** The fallback alerting path fires only when the SRE Bot is unable to self-alert. Message volume is low (at most a few alarms per incident). Q Developer's fixed format — alarm name, state, metric, threshold, region — provides sufficient context for an operator to begin investigation. Runbook links and custom enrichment, while desirable, are not essential for the initial "the bot is down, start investigating" signal.

### Accepted limitations and reserved fallback

Q Developer's fixed message format cannot include runbook links, custom severity tags, or organization-specific context. This is accepted because:

- The fallback path's purpose is to **break the silence** — alert the team that the bot is down. It does not need to replace the bot's rich notification capabilities.
- Alarm names and descriptions (set in Terraform) can encode actionable context (e.g., alarm description includes investigation steps).
- If operational experience demonstrates that the fixed format is insufficient, **Option B (SNS → Lambda → Slack Web API) is the designated escalation path.** The architecture (alarm class taxonomy, per-class SNS topics) is designed to support a Lambda subscriber as a drop-in replacement for a Q Developer configuration on any SNS topic.

### Option B reserved as escalation path

Option B (Lambda) is not implemented initially but is architecturally pre-approved as the escalation if:

- Challenge review identifies Q Developer as insufficient for the use case.
- Operational experience demonstrates that Q Developer's fixed format creates unacceptable response latency.
- Q Developer service reliability proves inadequate for this critical fallback function.

If Option B is activated, it must comply with:

- Same bot token as SRE Bot app (user-confirmed).
- Channel routing configurable via Lambda environment variables.
- SQS DLQ for failed Lambda invocations with CloudWatch alarm on DLQ depth.
- Exponential backoff on Slack HTTP 429 with `Retry-After` header.
- CloudWatch Alarms → SNS only (no EventBridge) as the trigger source.

### Alternatives evaluated

#### Option A — Amazon Q Developer in chat applications (managed service)

**Description:** Use the AWS-managed CloudWatch → SNS → Amazon Q Developer (formerly AWS Chatbot) → Slack integration. Amazon Q Developer natively renders CloudWatch alarms with formatted Slack messages, including alarm name, state, metric details, and account context. Zero custom code.

**How it works:**

1. Configure an Amazon Q Developer Slack channel configuration (Terraform `aws_chatbot_slack_channel_configuration` resource).
2. Map the existing SNS topic (`sre-bot-cloudwatch-alarms-warning`) — or a dedicated fallback topic — to the Q Developer configuration.
3. Q Developer subscribes to the SNS topic and formats alarm notifications automatically.

**Pros:**

- **ADR-0045 P7 Tier 1:** Managed cloud service — highest in the delegation hierarchy.
- Zero custom code to write, test, or maintain. No Lambda function, no deployment pipeline.
- Automatic message formatting — human-readable alarm state, metric name, threshold, account, region.
- AWS manages availability, scaling, and delivery reliability.
- Terraform-native: `aws_chatbot_slack_channel_configuration`, `aws_chatbot_teams_channel_configuration`.
- Supports composite alarms (displays up to 3 triggering children).
- CloudWatch Alarms are a natively supported service (no EventBridge intermediary needed).

**Cons:**

- **Limited message customization.** Cannot add runbook links, custom severity tags, or organization-specific context to notifications. Format is fixed by AWS.
- **No DLQ.** Q Developer does not expose a dead-letter queue for failed Slack deliveries. Delivery reliability is AWS-managed but opaque — if Slack is unreachable, the failure handling is internal to Q Developer.
- **Channel routing is per-configuration, not per-alarm.** To route different alarm types to different channels, you need separate SNS topics mapped to separate Q Developer configurations. You cannot route within a single topic by alarm type.
- **Dependency on AWS service availability.** If Amazon Q Developer has an outage, fallback alerting is lost. No secondary fallback path.
- **No programmatic rate-limit handling.** Cannot implement custom backoff for Slack API rate limits.
- **Custom notifications require EventBridge integration.** If the standard CloudWatch alarm format is insufficient, custom formatting requires EventBridge → SNS → Q Developer with InputTransformers — which approaches Lambda-level complexity.

**Assessment:** Solves formatted message rendering and webhook deprecation concerns. Partially addresses delivery reliability (AWS-managed delivery, but no DLQ visibility). Requires per-topic channel routing (one SNS topic per channel). Does not support custom enrichment (runbook links, severity tags). Slack identity lifecycle is AWS-internal (managed, not configurable).

#### Option B — SNS → Lambda → Slack Web API

**Description:** A lightweight Lambda function subscribed to the SNS topic transforms CloudWatch alarm JSON into rich Block Kit messages and posts them to Slack via `chat.postMessage` using the bot token.

**How it works:**

1. Lambda function (Python, minimal dependencies — `slack_sdk` or raw `urllib3` HTTPS POST).
2. SNS subscription (Lambda protocol, not HTTPS). SNS invokes Lambda asynchronously.
3. Lambda transforms the alarm payload into a Block Kit formatted Slack message with severity classification, alarm details, runbook links, and recommended actions.
4. Lambda posts to the configured Slack channel(s) using `chat.postMessage` with the bot token.
5. Lambda async invocation has a configured DLQ (SQS). CloudWatch alarm on DLQ depth.
6. Bot token stored in AWS Secrets Manager; channel IDs in Lambda environment variables.

**Pros:**

- Full control over message format, enrichment, and routing logic.
- `chat.postMessage` supports dynamic channel routing (different alarms → different channels), Block Kit formatting, message threading, and `Retry-After` handling.
- Lambda async invocation provides built-in retry (2 retries by default) and DLQ for failed invocations → full delivery failure visibility (P3).
- Small, focused function: ~100 lines of Python with no framework dependencies.
- AWS-internal pipeline — Lambda runs within AWS; only outbound call is to Slack API.
- Can suppress duplicate/flapping alarm transitions by tracking alarm state.
- Rate-limit handling: can implement exponential backoff on HTTP 429 with `Retry-After` header.

**Cons:**

- **ADR-0045 P7 Tier 3:** Custom code — lowest in the delegation hierarchy.
- Must write, test, and maintain the Lambda function code. (Though the function is small and stable once written.)
- Requires its own CI/CD pipeline for deployment (or inline Terraform `archive_file` for simple cases).
- Additional Terraform resources: Lambda function, IAM role, SQS DLQ, CloudWatch alarm, Secrets Manager secret reference.
- Operational burden: Lambda runtime updates, dependency updates, monitoring.

**Assessment:** Solves all identified problems — formatted messages, dynamic channel routing, delivery reliability with DLQ, custom enrichment, webhook replacement, and Slack identity governance. Higher implementation and maintenance cost than managed service.

#### Option C — SNS → SQS → Lambda → Slack Web API (buffered)

**Description:** Same as Option B, but with an SQS queue between SNS and Lambda for message buffering and delivery guarantees.

**Pros (over Option B):**

- SQS provides message persistence and built-in DLQ at the queue level (not just Lambda async DLQ).
- Message retention up to 14 days — survives Lambda outages.
- Visibility timeout and retry semantics are explicitly configurable.
- Decouples SNS delivery from Lambda processing — SNS confirms delivery to SQS immediately.

**Cons (over Option B):**

- Additional infrastructure component (SQS queue + DLQ queue + IAM permissions + subscriptions).
- Over-engineering for the volume — CloudWatch alarms fire at most every 60 seconds per alarm. SQS buffering adds complexity for a low-volume use case.
- Lambda is already invoked asynchronously by SNS with built-in retry and DLQ — the SQS layer duplicates this.

**Assessment:** Strictly more reliable than Option B, but the added complexity is not justified for a low-volume fallback alerting path.

#### Option D — Keep SNS → Slack Webhook (enhanced)

**Description:** Retain the current webhook path but add `DeliveryStatusLogging` to the SNS topic and replace the legacy webhook with an app-based webhook.

**Pros:**

- Minimal infrastructure change.
- Adds delivery visibility via CloudWatch Logs.

**Cons:**

- Does not solve P1 (raw JSON), P2 (single channel), P4 (no enrichment).
- Webhook integration remains a second-class Slack integration. `chat.postMessage` is Slack's recommended path.
- No DLQ — only logging of delivery failures.
- Does not address the core problem: raw, unactionable alert notifications.

**Assessment:** Insufficient. Partially addresses delivery visibility (via logging) and webhook deprecation (app-based webhook). Does not solve message formatting, channel routing, enrichment, or identity governance. The core problems remain.

## Consequences

### Positive impacts

- **Silent bot failure is now detectable.** CloudWatch alarms for error spikes, high CPU/memory, and ECS task failures (running tasks below desired count) will reach the team through Q Developer, independent of the SRE Bot application.
- **ECS task failure gap closed.** The new `RunningTaskCount` alarm directly detects the dead-man-switch scenario — tasks are down and the bot cannot self-alert. This fills a gap where no existing alarm detects task crash-loops, failed starts, or post-deployment task failures.
- **Human-readable notifications.** Q Developer formats CloudWatch alarm payloads into structured, readable Slack messages — replacing raw JSON.
- **No custom code to maintain.** Managed service eliminates Lambda code, CI/CD pipeline, runtime updates, and dependency management for the alerting path.
- **Governance-hardened Slack integration.** Mandatory guardrail policies, notification-only channel roles, and private channel requirements ensure the Q Developer Slack integration follows least-privilege principles despite the AWS Chatbot app's broad OAuth scopes.
- **Alarm class taxonomy enables future evolution.** Per-class SNS topics support upgrading any alarm class from Q Developer to Lambda (Option B) independently.

### Tradeoffs accepted

- **Fixed message format.** Cannot add runbook links, custom severity classification, or investigation playbook steps to Q Developer notifications. Accepted because the fallback path's purpose is silence-breaking, not full incident management.
- **No DLQ visibility.** Q Developer does not expose a dead-letter queue for failed Slack deliveries. Delivery reliability is AWS-managed but opaque. Mitigated by Q Developer logging (`ERROR` level) and the reserved Option B escalation path.
- **One-time manual setup.** Slack workspace authorization requires a manual step in the AWS Console. Not automatable via Terraform. This is a one-time action.
- **Per-class SNS topics add Terraform resources.** Alarm class routing requires separate SNS topics and Q Developer configurations (2–3 topic + config pairs). This is modest infrastructure overhead.

### Risks introduced

1. **Q Developer service outage.** If Amazon Q Developer is unavailable during a bot failure, the fallback path fails. Mitigation: Q Developer logging captures delivery failures; the reserved Option B (Lambda) escalation path provides an alternative if Q Developer reliability is insufficient.
2. **Alarm description quality.** Since Q Developer's format is fixed, the usefulness of notifications depends on the quality of `alarm_description` values set in Terraform. Poorly written descriptions will produce unhelpful notifications. Mitigation: establish a naming/description convention for alarm resources.
3. **Slack workspace authorization drift.** If the Slack workspace authorization is revoked or the workspace ID changes, Q Developer will fail to deliver. Mitigation: low risk — workspace authorization is stable and long-lived.

### Mitigations

- Q Developer logging level set to `ERROR` provides CloudWatch Logs visibility into delivery failures.
- Alarm names and descriptions encode actionable context (alarm resource naming convention).
- Option B (Lambda) is pre-approved as escalation — no ADR amendment required to activate it.

## Compliance and Boundaries

### ADR-0045 P7 — Managed Service Delegation Hierarchy

| Option | P7 Tier | Rationale |
|--------|---------|-----------|
| A (Q Developer) | Tier 1 — Managed cloud service | AWS-managed, zero custom code |
| B (Lambda) | Tier 3 — Custom code | Small custom function, full control |
| C (SQS+Lambda) | Tier 3 — Custom code | More infrastructure, same custom code |
| D (Webhook) | N/A — Status quo | No new decision |

Per P7, Option A should be preferred unless its limitations create unacceptable gaps. The key P7 evaluation: does the managed service's fixed message format and lack of DLQ visibility create operational risk that justifies dropping to custom code?

### ADR-0080 — Infrastructure Domain

This ADR governs an infrastructure-domain component. The fallback alerting mechanism is independently deployed, has no dependency on the SRE Bot application, and is not governed by application-domain ADRs (ADR-0067, ADR-0046, etc.).

### ADR-0081 S4 — Deployment Failure Notification

ADR-0081 Standard 4 requires deployment outcomes to be reported to the team's operational notification channel. The fallback alerting path governed by this ADR is the delivery mechanism for those notifications when they originate from CloudWatch alarm signals.

## Derivation from Higher-Tier ADRs

### Derivation Test Checklist

1. **Tier-bleed check:** ✅ Pass. Infrastructure alerting architecture is specific to the SRE Bot's operational monitoring integration. A different infrastructure component would have different alarm sources, different channel routing, and different enrichment needs.
2. **Constraint chain check:** ✅ Pass. Constrained by ADR-0044 (governance), ADR-0080 (infrastructure domain), ADR-0054 (observability ownership), ADR-0081 (deployment notification).
3. **Single-concern check:** ✅ Pass. One decision: how the infrastructure fallback alerting mechanism delivers notifications to Slack when the SRE Bot is unavailable.
4. **Domain-specificity check:** ✅ Pass. Domain entities: CloudWatch alarm classes, SNS alarm topic, Slack fallback channel, alarm severity taxonomy. These are specific to this integration path.

### Constraint Derivation Table

| Constraint | Source ADR | How This Integration Applies It |
|------------|-----------|--------------------------------|
| Managed service > library > custom code | ADR-0045 Principle 7 | Evaluate Amazon Q Developer (managed) before Lambda (custom). Accept custom code only if managed service gaps create operational risk. |
| App emits logs; platform routes them | ADR-0054 Standard (observability ownership) | Fallback alerting is a platform-domain responsibility. It consumes CloudWatch alarm signals, not application logs directly. |
| Infrastructure components are independently deployed | ADR-0080 Principle 1, 3 | Fallback alerting has zero dependency on SRE Bot runtime, codebase, or deployment pipeline. |
| Deployment outcomes reported to ops channel | ADR-0081 Standard 4 | CloudWatch alarms triggered by deployment-time health failures are delivered through this fallback path. |
| Infrastructure alerting excluded from ADR-0067 scope | ADR-0067 (amended 2026-05-01) | Lambda or managed service calling Slack Web API directly is explicitly permitted for independently deployed infrastructure. |

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- Validation summary: Initial draft.
- Follow-up actions: None.

## Source References

1. Slack Web API Rate Limits
   - URL: <https://docs.slack.dev/apis/web-api/rate-limits/>
   - Publisher/maintainer: Slack Technologies (Salesforce)
   - Accessed date: 2026-05-01
   - Relevance summary: Rate limit tiers for `chat.postMessage` (Special tier: 1 msg/sec/channel). Incoming webhooks also 1/sec. HTTP 429 returns `Retry-After` header. Informs rate-limit handling requirements for Option B/C.

2. Slack Legacy Custom Integrations — Incoming Webhooks (Deprecated)
   - URL: <https://docs.slack.dev/legacy/legacy-custom-integrations/legacy-custom-integrations-incoming-webhooks/>
   - Publisher/maintainer: Slack Technologies (Salesforce)
   - Accessed date: 2026-05-01
   - Relevance summary: Legacy custom integration webhooks are deprecated. Migration to app-based webhooks or `chat.postMessage` recommended. Runtime channel override not supported in current webhook model. Establishes the webhook deprecation concern.

3. Slack Incoming Webhooks (Current App-Based)
   - URL: <https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/>
   - Publisher/maintainer: Slack Technologies (Salesforce)
   - Accessed date: 2026-05-01
   - Relevance summary: App-based webhooks support Block Kit but cannot override default channel, username, or icon. Cannot delete messages. Informs single-channel routing limitation of webhooks.

4. AWS Lambda Asynchronous Invocation
   - URL: <https://docs.aws.amazon.com/lambda/latest/dg/invocation-async.html>
   - Publisher/maintainer: Amazon Web Services
   - Accessed date: 2026-05-01
   - Relevance summary: Async invocation queues events internally, retries twice on failure, supports DLQ (SQS) and event destinations. Informs Option B DLQ design.

5. Amazon SNS — Lambda as Subscriber
   - URL: <https://docs.aws.amazon.com/sns/latest/dg/sns-lambda-as-subscriber.html>
   - Publisher/maintainer: Amazon Web Services
   - Accessed date: 2026-05-01
   - Relevance summary: SNS invokes Lambda asynchronously with the alarm payload. Supports message delivery status attributes. Informs Option B integration pattern.

6. Amazon Q Developer in Chat Applications (AWS Chatbot) — Monitoring AWS Services
   - URL: <https://docs.aws.amazon.com/chatbot/latest/adminguide/related-services.html>
   - Publisher/maintainer: Amazon Web Services
   - Accessed date: 2026-05-01
   - Relevance summary: Native CloudWatch Alarm → SNS → Slack integration with automatic formatted messages. Zero custom code. Supports composite alarms. Custom notifications require EventBridge + InputTransformers. Informs Option A.

7. ADR-0045 Principle 7 — Managed Service Delegation Hierarchy
   - URL: Internal (docs/decisions/adr/0045-core-architectural-principles.md)
   - Publisher/maintainer: SRE Team
   - Accessed date: 2026-05-01
   - Relevance summary: Three-tier delegation model: managed cloud service > industry library > custom code. Option A (Q Developer) is Tier 1; Option B (Lambda) is Tier 3.

8. Slack Fallback Alerting Research Reference
   - URL: Internal (tmp/research-slack-fallback-alerting.md)
   - Publisher/maintainer: SRE Team
   - Accessed date: 2026-05-01
   - Relevance summary: Minimum secure posting model (bot token, least-privilege scopes, secret storage), reliability practices (retry with backoff, DLQ/fallback path, independence from monitored app).
