---
status: Accepted
date: 2026-07-06
applies: target
scope: The contracts that keep the app deployable on AWS today and Azure/OpenShift tomorrow.
---

# Cloud Portability

## Context

We run on AWS (ECS) today; a move to Azure or OpenShift is plausible. Portability is not "no AWS anywhere" — it is knowing exactly which seams a move would touch. The old record over-reached (banning secret-manager SDKs and boto3's default credential chain — both of which *help* portability) while the codebase under-delivered (the flagship `StorageService` Protocol leaks DynamoDB `KeyConditionExpression` strings).

## Decision

Four contracts:

1. **Config from the environment; secrets may come through a port.** Environment variables select behavior and providers (12-factor III). Secret *material* may additionally be resolved through a `SecretsService` Protocol whose backend (AWS Secrets Manager today) is itself env-selected. Application code never reads cloud metadata endpoints directly. Ambient credential chains (boto3 default chain, workload identity) are **allowed and preferred** inside `integrations/` — they are the portable way to authenticate per compute platform.
2. **Logs to stdout as JSONL.** No files, no direct shipping to a vendor log API ([observability.md](observability.md)).
3. **Stateless process.** Durable state lives in backing services behind Protocols; anything in process memory is a cache that can vanish ([lifecycle.md](lifecycle.md)).
4. **Every backing service is reached through a capability-shaped Protocol.** The test that the Protocol is honest: **each Path A Protocol has an in-memory fake used in the integration test suite.** The fake is the standing "second provider" that keeps the interface vendor-neutral without building Azure. A Protocol that can't be faithfully faked (because it leaks vendor query syntax) fails this contract — `StorageService.query(key_condition: str)` is the current counterexample and must be redesigned before any second backend.

Deployment machinery (ECS circuit breaker, CloudWatch) may be AWS-native, but the *contract* the pipeline validates must be provider-neutral: deploy success = readiness probe green, not a CloudWatch log-line tail.

## Consequences

- A cloud move is scoped: new implementations behind existing Protocols + new deploy bindings. Feature code untouched.
- In-memory fakes double as fast test doubles — the portability tax pays for itself in test speed.
- We accept that queue *semantics* differ per cloud (FIFO dedup, ordering); the durable guarantee therefore lives in consumer idempotency, not broker features ([reliability.md](reliability.md)).

## Checks

- Every `app/infrastructure/<service>/` Path A package contains a fake implementation exercised by tests.
- grep: no `boto3`/`botocore` imports outside `app/integrations/` and `app/infrastructure/` implementations.
- Readiness-probe-based deploy validation in the pipeline definition.

## Migration

Tickets: storage-protocol redesign; fakes for directory/idempotency/queue; pipeline validation switch. Tolerated: single (AWS) implementation per Protocol; CloudWatch-based deploy check.
