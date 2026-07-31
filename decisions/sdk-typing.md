---
status: Accepted
date: 2026-07-31
applies: target
scope: How to obtain type/IDE resolution from rich vendor SDKs without building a wrapper tier — the companion to outbound-clients.md.
---

# Vendor SDK Typing

## Context

[outbound-clients.md](outbound-clients.md) decides the *boundary contract* (clients raise, adapters classify, SDK-native retry). It asserts that holding the SDK client directly "keeps the vendor's typed surface, IDE completion, and documentation examples intact." That is true for **boto3 only when stubs are installed**, and, absent stubs, **false for `google-api-python-client`**, whose discovery `Resource` is generated at runtime and has no type information out of the box. That unstated asymmetry is what actually produced the mess this record cleans up — see the revised finding below for how Google closes the gap too.

Reaching for IDE/type resolution over dynamic SDK handles, the codebase grew a **generic stringly-typed dispatcher** per vendor and then **hand-mirrored every SDK method on top of it**:

- `integrations/aws/client_next.py::execute_aws_api_call(service_name, method, **kwargs)` — dispatch by string, plus a hand-rolled `time.sleep` retry loop — with `dynamodb_next.py` / `identity_store_next.py` wrapping one passthrough function per method.
- `integrations/google_workspace/google_service.py::execute_google_api_call(service, version, resource_path, method, **kwargs)` — walks the discovery tree by `getattr`, and **scrapes the method's `__doc__` to discover valid parameters** (`get_google_api_command_parameters`) — with `google_directory.py` etc. wrapping each method again.
- `infrastructure/clients/aws/facade.py` — an `AWSClients` facade composing per-service classes whose every method is a passthrough returning `OperationResult`.

Each layer discards the SDK's real surface, rebuilds a *worse* dynamic dispatch, and commits the team to mirror-maintenance forever. 2026 reality: **boto3** has first-class stubs (`types-boto3`, the maintained successor to `boto3-stubs`, versioned in lockstep with boto3) giving full Pylance/pyright completion, `TypedDict` request/response shapes, and typed paginators with zero wrappers. **`google-api-python-client`** is officially "complete and in maintenance mode" (critical fixes only) and is untyped by design; Google recommends the typed `google-cloud-*` libraries (Cloud Client Libraries) for *new* surfaces — but those libraries cover **GCP resources** (Cloud Storage, Pub/Sub, BigQuery, etc.), not **Google Workspace resources** (Admin SDK Directory, Gmail, Groups Settings). There is no Cloud Client Library for the Admin/Directory API we use; it is discovery-only, full stop, regardless of which client family is chosen.

Revised finding: the SDK itself does not need to stay untyped. **[`google-api-python-client-stubs`](https://github.com/henribru/google-api-python-client-stubs)** is a community-maintained (not Google-authored) PyPI package that ships hand-generated-from-Discovery-Document type stubs for `googleapiclient` — a separate overload of `discovery.build()` per service+version, and `TypedDict`/class stubs for every request/response shape, covering every discovery API bundled in `google-api-python-client` (including `admin_directory_v1`, `gmail_v1`, etc.). It is dev-only (`TYPE_CHECKING`-only symbols living under `googleapiclient._apis`, invisible at runtime) — the same shape as `types-boto3` for boto3. This changes the answer for item 3 below: the discovery `Resource` can be typed at construction, not only translated after the fact at the adapter.

## Decision

**Do not wrap SDK methods to regain types. Type at the boundary the SDK gives you.**

1. **Retire the generic dispatcher and the per-method wrapper module.** `execute_aws_api_call` / `execute_google_api_call` and the `*_next` passthrough modules are anti-patterns and are deleted. No file in `integrations/` dispatches SDK calls by a `method`/`resource_path` string, and none discovers parameters by parsing an SDK docstring.

2. **boto3 → stubs, not wrappers.** Obtain typing from `types-boto3[<services>]` (dev-only, `TYPE_CHECKING`). The factory annotates the handle once (`client: DynamoDBClient = session.client("dynamodb")`) and the adapter calls `client.get_item(...)` directly with full completion and typed results. **No per-service client class, no facade.** Pure-data SDK model/`TypedDict` imports are permitted anywhere payloads are built ([outbound-clients.md](outbound-clients.md) already allows this).

3. **`google-api-python-client` → stubs at the SDK boundary, dataclasses at the domain boundary.** Obtain typing the same way as boto3: the dev-only, community-maintained `google-api-python-client-stubs` package types `discovery.build(...)`'s return per service+version. The factory builds the resource with `cache_discovery=False, static_discovery=True` and **annotates the return type explicitly** (e.g. `service: AdminDirectoryResource = build("admin", "directory_v1", credentials=creds, cache_discovery=False)`, importing `AdminDirectoryResource` only under `if TYPE_CHECKING:` from `googleapiclient._apis.admin_directory_v1` — explicit annotation is required, not optional, because the stub package overloads `build()` per service and un-annotated inference is both slow and untyped for chained calls). The adapter then calls `service.users().get(userKey=...).execute()` directly with real method/parameter/return-shape completion and checking, and still **immediately translates the returned `TypedDict`/`dict` into a typed domain `@dataclass`** (frozen internal entity, per the model-boundary rules) — the stub's `TypedDict`s do not exist at runtime and are never suitable as the internal entity type, so this translation step is unchanged from the original decision. Because the stub package is an unofficial, community-maintained project (unlike `types-boto3`), pin its version and treat gaps/lag against newly-added Google fields as expected — the adapter's translation step is the safety net when a field is missing or mistyped. Prefer a typed `google-cloud-*` library for any *new* Google surface that is GCP-resource-shaped (not applicable to Workspace/Directory resources today).

4. **One construction path per vendor** ([outbound-clients.md](outbound-clients.md)): factories + `classify_<vendor>_error` + settings. The client raises; the adapter classifies.

## Consequences

- The entire AWS per-service facade and both `*_next` dispatcher generations are deleted rather than renamed; adapters hold the SDK handle directly.
- boto3 call sites gain real completion and type-checking for free; the price is one dev dependency and one annotation at each factory.
- Google call sites now gain SDK-level completion/type-checking too (via the community stub package's typed `build()` overloads and per-method signatures), in addition to typed *domain* results at the adapter, which is where feature code reads them. The docstring-scraping param filter is deleted (it silently dropped unknown kwargs; the SDK now raises on them, which is correct).
- The Google stub package is a third-party dependency on an unofficial, single-maintainer project (`https://github.com/henribru/google-api-python-client-stubs`), the same risk class as `types-boto3`/`boto3-stubs` (`youtype`, also unofficial and single-maintainer) that this record already accepts for AWS — deliberately treated the same, not a double standard. Neither ships at runtime: [toolchain.md](toolchain.md)'s `uv sync --locked --no-dev` excludes the whole `[dependency-groups] dev` group, stub packages included, from the shipped image by construction. Both are ordinary pinned `dev` dependencies covered by [dependency-scanning.md](dependency-scanning.md)'s `pip-audit` CI gate and reviewed like any other Renovate version bump; a stale or missing stub release degrades to `Any` (today's status quo) rather than breaking anything at runtime or blocking a release. No separate vendoring/self-generation of stubs is adopted — the ongoing maintenance of a forked generator would cost more than the risk it removes.

## Checks

- grep: no `execute_aws_api_call` / `execute_google_api_call` (or any `getattr(resource, method)()` string-dispatch) in `integrations/`.
- grep: no `__doc__`-based parameter discovery in `integrations/` (`get_google_api_command_parameters` deleted).
- `find app/integrations -name "*_next.py"` returns zero.
- No per-vendor "client facade" class exposing an SDK handle; adapters call the SDK client directly.
- `types-boto3` present in dev dependencies; mypy/pyright resolve boto3 client method signatures.
- `google-api-python-client-stubs` present in dev dependencies (pinned); mypy/pyright resolve the Admin Directory (and any other in-use Workspace) discovery `Resource`'s method signatures at the factory's explicitly-annotated return type — not just at the adapter's translated dataclass.

## Migration

Tickets: TASK-70 (adopt `types-boto3` **and** `google-api-python-client-stubs` + wire these checks — both are dev-only stub adoptions of the same shape), TASK-22.2 / TASK-22.3 (AWS DynamoDB + Identity Store surfaces), TASK-22.4 (Google Directory surface — factory now annotates the discovery `Resource` with the stub-provided type instead of leaving it dynamic), TASK-23 (delete the residual `*_next` dispatcher generation), TASK-25 (remaining vendors + `AWSShield`/executor retirement + final sweep). Tolerated until those close: the `execute_*_api_call` dispatchers, the `*_next` twins, the docstring-param scraper, and the `AWSClients` facade — each named in its owning ticket.

**Change note (2026-07-31, post-acceptance):** the original version of this record accepted the Google discovery `Resource` as permanently untyped and typed only the adapter's translated dataclass. Research while planning TASK-22.2 found `google-api-python-client-stubs` (community-maintained, generated from Google's own Discovery Documents, dev-only), which types `build()`'s return per service+version the same way `types-boto3` types a boto3 client. Item 3 and the affected Checks/Consequences were revised accordingly; the adapter-side dataclass translation requirement is unchanged. TASK-70 and TASK-22.4's implementation plans should be re-reviewed against this revision before that work starts.
