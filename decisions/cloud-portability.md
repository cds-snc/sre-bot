---
status: Accepted
date: 2026-10-15
applies: target
scope: The contracts that keep the app deployable on AWS today and Azure/OpenShift tomorrow.
---

# Cloud Portability

## Context

We run on AWS (ECS) today; a move to Azure or OpenShift is plausible. Portability is not "no AWS anywhere" — it is knowing exactly which seams a move would touch. The old record over-reached (banning secret-manager SDKs and boto3's default credential chain — both of which *help* portability) while the codebase under-delivered (the flagship `RecordStore` Protocol leaks DynamoDB `KeyConditionExpression` strings).

## Decision

Four contracts:

1. **Config from the environment; secrets may come through a port.** Environment variables select behavior and providers (12-factor III). Secret *material* may additionally be resolved through a `SecretsService` Protocol whose backend (AWS Secrets Manager today) is itself env-selected. Application code never reads cloud metadata endpoints directly. Ambient credential chains (boto3 default chain, workload identity) are **allowed and preferred** inside `integrations/` — they are the portable way to authenticate per compute platform.
2. **Logs to stdout as JSONL.** No files, no direct shipping to a vendor log API ([observability.md](observability.md)).
3. **Stateless process.** Durable state lives in backing services behind Protocols; anything in process memory is a cache that can vanish ([lifecycle.md](lifecycle.md)).
4. **Every backing service is reached through a capability-shaped Protocol, and each such Protocol has an in-memory fake exercised by tests.** This is the driven-port ("secondary adapter") half of [ports-and-adapters](https://alistair.cockburn.us/hexagonal-architecture/): the in-memory adapter is the standing *second* adapter that proves the port is technology-neutral without building Azure, and it doubles as the fast test double every consumer's tests use. "Fake" is meant in the [Meszaros/Fowler sense](https://martinfowler.com/bliki/TestDouble.html) — a *working in-memory implementation the test seeds* (like an `InMemoryTestDatabase`), **not** production data baked into the repo, and preferred over `MagicMock` ([dependency-injection.md](dependency-injection.md)). A Protocol that can't be faithfully faked because it leaks vendor syntax fails this contract. `RecordStore` is the worked example: its read takes a typed `RecordQuery` against a `RecordTable` that declares the key layout once, instead of a DynamoDB key-condition string, and `InMemoryRecordStore` runs the same conformance suite as the DynamoDB store.

   **Scope — and the anti-dead-code rule.** The fake contract applies to two kinds of Protocol ([plugin-architecture.md](plugin-architecture.md)): **hosting contracts** (Protocols in `contracts/` implemented in `infrastructure/`: records, queue, coordination, secrets) and **capability `api.py` Protocols** that face an external system (people and directory lookups, workplace systems, the approval-workflow store per [approvals.md](approvals.md)). It does **not** apply to a feature's Path B adapter, which exists to act on one vendor and is not portable by design; nor to in-process mechanisms with no vendor to substitute (logging, the plugin manager), which *are* their own implementation and are exercised directly in tests. And a fake is required only where the Protocol has a real consumer (capabilities are never built speculatively). Where consumers exist their tests already hand-roll ad-hoc doubles — the Access Sync suite's inline `DirectoryProvider` stub, the audit `write_audit_event` monkeypatch — so the shared fake *removes* duplication rather than adding code.

   **Persisted enum values.** A value stored through the records contract and drawn from a settings enum (such as `WorkplaceSystem` on a reference) is a closed enum, validated strictly where it is chosen (settings, record construction) and read tolerantly: a stored value outside the enum is left in place and logged, never a crash, and never replaced by a guessed member; the reader drops what it cannot map (an optional reference) or returns the record as unreadable (a required field). A new member ships in readers one deploy before any writer. Sources, read on 2026-10-15: [AIP-126](https://google.aip.dev/126), [protobuf enum guide](https://protobuf.dev/programming-guides/enum/).

   **Whole-table reads.** `RecordStore.read_all(table, *, max_items)` serves batch jobs and configuration-sized tables only. It is never a lookup, which goes through a declared index, and never a user-facing listing, which pages on an index query. It returns every item, or an error result when the table holds more than `max_items`, never a truncated success: a list cut short by a default page size is the backward-incompatible failure [AIP-158](https://google.aip.dev/158) warns about, and a lookup that silently misses a row is a correctness and security bug. `max_items` is the caller's expectation of the table's size and comes from the owning package's settings (`<SLICE>__<FIELD>`, with a default), like table names. The read is strongly consistent as of its start (DynamoDB `ConsistentRead`, which "ensures that all of the write operations that completed before the Scan began are included") and its order is unspecified. A batch that outgrows its cap gets a paged read as a new operation, added with that consumer; `read_all` is never changed into one. Sources, read on 2026-10-20: [AIP-158](https://google.aip.dev/158), [DynamoDB Scan](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Scan.html), [DynamoDB query and scan practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/QueryAndScanGuidelines.html).

Deployment machinery (ECS circuit breaker, CloudWatch) may be AWS-native, but the *contract* the pipeline validates must be provider-neutral: deploy success = readiness probe green, not a CloudWatch log-line tail. The readiness probe is the static endpoint in [health-checks.md](health-checks.md), which answers only after lifespan startup completes.

## Consequences

- A cloud move is scoped: new implementations behind existing Protocols + new deploy bindings. Feature code untouched.
- In-memory fakes double as fast test doubles — the portability tax pays for itself in test speed.
- We accept that queue *semantics* differ per cloud (FIFO dedup, ordering); the durable guarantee therefore lives in consumer idempotency, not broker features ([reliability.md](reliability.md)).

## Checks

- **CI-enforced** (`make check-fake-coverage`, `app/bin/check_fake_coverage.py`): every hosting contract and every externally-facing capability `api.py` Protocol has an in-memory fake exercised by tests. Coverage follows the driven-port line by rule, not by list: a `contracts/` Protocol is covered when an `infrastructure/` class explicitly subclasses it, a capability `api.py` Protocol when its own `adapters/` explicitly subclass it, and a Protocol still defined in `infrastructure/` until it moves. Registrars and extension points the host implements, feature Path B adapters and in-process mechanisms (logging, plugins) fall outside it. Real adapters and fakes **explicitly subclass** their Protocol, so mypy proves conformance and the check can see them; the fake is a class in an `in_memory.py` module, and each Protocol's conformance suite has an enrollment test that fails when a concrete subclass is missing from its fixture. Current gaps live in `app/bin/baselines/fake_coverage.txt`, each with the task that closes it.
- grep: no `boto3`/`botocore` imports outside `app/integrations/` and `app/infrastructure/` implementations.
- Readiness-probe-based deploy validation in the pipeline definition.

## Migration

Tickets: records-Protocol redesign + portable-Protocol fakes + the CI fake-coverage check (TASK-27); `QueueService` fake (TASK-34); pipeline validation switch. Tolerated until closed: single (AWS) implementation per Protocol; the fake gaps in the Checks baseline; CloudWatch-based deploy check.

**Changes:**
- 2026-09-24: the fake contract covers hosting contracts and capability `api.py` Protocols; feature Path B adapters are not portable.
- 2026-09-25: the readiness probe is the static health endpoint, answering after lifespan startup.
- 2026-10-13: the storage contract is the records contract (`RecordStore`, TASK-27.4).
- 2026-10-13: `RecordStore` reads take a typed `RecordQuery` over a declared `RecordTable`; the key-condition string is gone (TASK-27.1).
- 2026-10-14: the fake-coverage check enforces contract 4 by the driven-port rule; adapters and fakes explicitly subclass their Protocol (TASK-27.3).
- 2026-10-15: persisted enum values are strict where chosen, tolerant on read, and new members reach readers one deploy before writers (TASK-153).
- 2026-10-15: a tolerant read leaves an unmapped stored value in place and never guesses a member; it drops an optional reference or returns the record as unreadable (TASK-145.5.4).
- 2026-10-20: whole-table reads are `read_all`, all items or an error past the caller's cap from its settings, strongly consistent and unordered, for batch jobs and configuration-sized tables, never a lookup or listing (TASK-27.5).
