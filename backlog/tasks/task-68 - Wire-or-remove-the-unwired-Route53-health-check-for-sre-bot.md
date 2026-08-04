---
id: TASK-68
title: Wire or remove the unwired Route53 health check for sre-bot
status: To Do
assignee: []
created_date: '2026-07-29 20:03'
labels:
  - infrastructure
  - phase-4
  - observability
milestone: m-4
dependencies: []
references:
  - decisions/health-checks.md
  - terraform/route53.tf
  - terraform/alb.tf
priority: medium
ordinal: 103000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/health-checks.md documents four independent health-check layers (Dockerfile HEALTHCHECK, ECS task-definition healthCheck, ALB target-group health check, Route53 health check). The Route53 health check (terraform/route53.tf aws_route53_health_check.sre_bot_healthcheck) is currently unwired: aws_route53_record.sre_bot is a plain ALIAS with evaluate_target_health=false and no failover/weighted routing policy, and no aws_cloudwatch_metric_alarm consumes its auto-published AWS/Route53 HealthCheckStatus metric. As configured it only generates background /version request volume with no operational payoff. Decide and implement one of: (a) wire the HealthCheckStatus metric to a CloudWatch alarm + notification action, giving genuine external-reachability signal distinct from the ALB's inside view, or (b) remove the health check and its background traffic entirely.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Either an aws_cloudwatch_metric_alarm consumes aws_route53_health_check.sre_bot_healthcheck's HealthCheckStatus metric with a real notification action, or the health check resource is deleted from terraform/route53.tf
- [ ] #2 terraform fmt -check and terraform validate are clean on terraform/route53.tf (and alarms.tf if an alarm is added)
- [ ] #3 decisions/health-checks.md Checks section reflects the final chosen state (alarm-wired vs removed) and applies flips to now
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Human confirms which option (wire vs remove) before merge; PR references decisions/health-checks.md
<!-- DOD:END -->
