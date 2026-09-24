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
4. **Every backing service is reached through a capability-shaped Protocol, and each such Protocol has an in-memory fake exercised by tests.** This is the driven-port ("secondary adapter") half of [ports-and-adapters](https://alistair.cockburn.us/hexagonal-architecture/): the in-memory adapter is the standing *second* adapter that proves the port is technology-neutral without building Azure, and it doubles as the fast test double every consumer's tests use. "Fake" is meant in the [Meszaros/Fowler sense](https://martinfowler.com/bliki/TestDouble.html) — a *working in-memory implementation the test seeds* (like an `InMemoryTestDatabase`), **not** production data baked into the repo, and preferred over `MagicMock` ([dependency-injection.md](dependency-injection.md)). A Protocol that can't be faithfully faked because it leaks vendor syntax fails this contract — `StorageService.query(key_condition: str)` is the counterexample and must be redesigned before any second backend.

   **Scope — and the anti-dead-code rule.** The fake contract applies to two kinds of Protocol ([plugin-architecture.md](plugin-architecture.md)): **hosting contracts** (Protocols in `contracts/` implemented in `infrastructure/`: storage, queue, coordination, secrets) and **capability `api.py` Protocols** that face an external system (people and directory lookups, workplace systems, the approval-workflow store per [approvals.md](approvals.md)). It does **not** apply to a feature's Path B adapter, which exists to act on one vendor and is not portable by design; nor to in-process mechanisms with no vendor to substitute (logging, the plugin manager), which *are* their own implementation and are exercised directly in tests. And a fake is required only where the Protocol has a real consumer (capabilities are never built speculatively). Where consumers exist their tests already hand-roll ad-hoc doubles — the Access Sync suite's inline `DirectoryProvider` stub, the audit `write_audit_event` monkeypatch — so the shared fake *removes* duplication rather than adding code.

Deployment machinery (ECS circuit breaker, CloudWatch) may be AWS-native, but the *contract* the pipeline validates must be provider-neutral: deploy success = readiness probe green, not a CloudWatch log-line tail.

## Consequences

- A cloud move is scoped: new implementations behind existing Protocols + new deploy bindings. Feature code untouched.
- In-memory fakes double as fast test doubles — the portability tax pays for itself in test speed.
- We accept that queue *semantics* differ per cloud (FIFO dedup, ordering); the durable guarantee therefore lives in consumer idempotency, not broker features ([reliability.md](reliability.md)).

## Checks

- **CI-enforced:** every hosting contract and every externally-facing capability `api.py` Protocol has an in-memory fake exercised by tests (a CI check fails the build on such a Protocol with no fake); feature Path B adapters and in-process mechanisms (logging, plugins) are out of scope. Current gaps: `infrastructure/directory/` (no shared `InMemoryDirectoryProvider` — tests hand-roll one) and `infrastructure/audit/` (rides `StorageService`, blocked on the `query()` redesign) — both closed by TASK-27.
- grep: no `boto3`/`botocore` imports outside `app/integrations/` and `app/infrastructure/` implementations.
- Readiness-probe-based deploy validation in the pipeline definition.

## Migration

Tickets: storage-protocol redesign + portable-Protocol fakes + the CI fake-coverage check (TASK-27); `QueueService` fake (TASK-34); pipeline validation switch. Tolerated until closed: single (AWS) implementation per Protocol; the `directory/` and `audit/` fake gaps named in Checks; CloudWatch-based deploy check.

**Changes:**
- 2026-09-24: the fake contract covers hosting contracts and capability `api.py` Protocols; feature Path B adapters are not portable.
