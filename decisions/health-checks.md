---
status: Accepted
date: 2026-07-29
applies: target
scope: Layered health checking across the container image, ECS task definition, ALB, and Route53 for sre-bot.
---

# Health Checks

## Context

Four independent health-check mechanisms exist for the one running service, each answering a different question — surfaced while auditing ~35 req/min against `/version`:

- **Dockerfile `HEALTHCHECK`** (image-level) — local `docker run`/CI/compliance-scanner signal only. AWS ECS explicitly ignores an image-embedded `HEALTHCHECK` once a task-definition-level one exists; the two never double-execute.
- **ECS task-definition `healthCheck`** (`terraform/templates/sre-bot.json.tpl`) — the container-level status ECS itself reports (previously always `UNKNOWN`, since no task-definition-level check existed).
- **ALB target-group health check** (`terraform/alb.tf`) — routing/failover; `interval=10s`, `path=/version`, `healthy_threshold=2`/`unhealthy_threshold=2` (faster than AWS's defaults of 30s/5/2).
- **Route53 health check** (`terraform/route53.tf`, `aws_route53_health_check.sre_bot_healthcheck`) — DNS-level; `request_interval=30s`, `resource_path=/version`.

`/version`/`/health` (`app/api/routes/system.py`) are cheap liveness checks with no dependency calls, already rate-limited (50/min) with a code comment naming the ALB/Route53 cadence explicitly. The combined volume (≈3 ALB nodes × 2 tasks × 6/min, plus ≈15-18 Route53 checkers × 2/min) accounts for the observed ~35 req/min — expected, not a defect.

The Route53 health check is currently **unwired**: `aws_route53_record.sre_bot` is a plain ALIAS with `evaluate_target_health = false` and no failover/weighted routing policy, and no `aws_cloudwatch_metric_alarm` consumes its auto-published `AWS/Route53` `HealthCheckStatus` metric. As configured, it generates background `/version` traffic with no operational payoff today.

## Decision

Keep all four layers — each answers a genuinely different question (image-local, ECS-container, LB-routing, DNS-external) and none is redundant given ECS's override behavior. The Route53 health check must either (a) feed a `aws_cloudwatch_metric_alarm` with a notification action, giving it a real external-reachability signal distinct from the ALB's inside view, or (b) be removed if that signal isn't wanted — left unwired is not an acceptable end state. Do not loosen the ALB's check interval/thresholds to cut request volume: AWS does not bill per health-check request, and faster failure detection outweighs log-noise concerns (log noise is addressed separately, at the logging layer — [observability.md](observability.md)).

## Consequences

- ~35 req/min baseline on `/version` is expected and already budgeted for (rate limit, code comment) — not something to alarm on or "fix" by itself.
- Whichever Route53 option is chosen, `terraform/route53.tf` and this record's Checks must agree afterward.

## Checks

- `aws_route53_health_check.sre_bot_healthcheck` is consumed by exactly one `aws_cloudwatch_metric_alarm`, or the resource no longer exists.
- `terraform fmt -check` / `terraform validate` clean on `terraform/route53.tf`.

## Migration

Ticket: TASK-68 (wire or remove the unwired Route53 health check). Tolerated until closed: the health check exists with no alarm consumer.
