---
title: "Data Redaction Policy"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application, operations]
concerns: [security, observability]
constrained_by: [type-boundaries.md, configuration-ownership.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Data Redaction Policy

## Context and Problem Statement

The application emits structured records to several outbound destinations: log records to `stdout`, exception tracebacks bundled into log entries, and (in time) metrics labels, audit events, and distributed-tracing attributes. Each of those records is a dictionary — a set of key/value pairs that leaves the application's trust boundary and is stored, indexed, and searched downstream. Some of those values are sensitive — credentials, secrets, session tokens, authorization headers, cookies — and must not appear verbatim in the stored records, regardless of which egress channel they flow through.

The problem this record addresses: **what is the application's canonical rule for redacting sensitive values from any structured record before it leaves the process, and how is that rule applied uniformly across every egress channel that emits such records?** The answer determines:

1. Whether a developer adding a new sensitive field name has to remember to redact it at every call site (error-prone, fails open) or whether redaction happens at the egress boundary (defense in depth, fails safe).
2. Whether the catalogue of "what counts as sensitive" lives in one place that authors and reviewers can read, or is scattered across logging code, metrics emitters, and audit hooks.
3. Whether a future egress channel (metrics labels, audit-event sinks, distributed-trace attributes) automatically inherits the redaction rule, or has to re-implement it.
4. Whether the redaction algorithm itself (what "redaction" means in concrete terms — replacement value, recursion, key-name vs. value matching) is consistent across channels, so a redacted record looks the same in any storage backend.

**Constraints:**

- Sensitive data appears in structured records *because* developers bind it for legitimate reasons (e.g., binding the inbound request payload for diagnostics) — it cannot be eliminated at the source. Redaction at the egress boundary is the load-bearing control.
- Configuration is read from environment variables at startup. The redaction catalogue extends through configuration; runtime mutation is not used.
- The application is asynchronous; the redaction algorithm must be safe under concurrent execution and must not introduce contention.
- Compliance frameworks (GC privacy guidance, OWASP logging guidance, the CWE-532 weakness pattern) require defense in depth: developer convention alone is insufficient; an enforcement boundary must exist.

**Non-goals:**

- This record does not define **error-body content disclosure** for HTTP responses. The rule that `5xx` problem-details bodies expose generic information and `4xx` bodies may carry client-actionable context is owned by the API design and error-mapping decision and operates on a different egress channel (the response body) with a different threat model (untrusted external callers).
- This record does not specify the structured-logging library, log format, or processor pipeline. Those are owned by the logging-and-observability decision; this record specifies the redaction *content* and *algorithm* that the logging pipeline (and other egress pipelines later) applies.
- This record does not specify retention, encryption-at-rest, access control, or downstream redaction at the storage layer. Those are owned by the execution environment per the cloud-portability contract; the application's responsibility ends when the redacted record leaves the process.
- This record does not enumerate the application's full sensitive-data inventory by feature. Each feature is responsible for ensuring values it binds into structured records pass through the egress boundary cleanly; the central catalogue covers cross-cutting categories.

## Considered Options

**Option 1 — Redaction at every call site.** Each developer, before logging or emitting a record, removes or hashes sensitive values manually. No central enforcement. Convention-only.

**Option 2 — Allow-list approach: only listed fields may be emitted.** Every field that appears in a structured record must be on a project-wide allow-list; everything else is dropped. Strong protection by construction; very high friction (every new field requires a list update); incompatible with diagnostic logging that captures arbitrary context.

**Option 3 — Deny-list at the egress boundary, value pattern-matching.** A redaction step at the egress boundary scans every value in the record looking for patterns that *resemble* secrets (e.g., regex for JWT shape, hex strings of credential length, etc.). Catches some leakage that key-name matching misses; high false-positive rate; expensive on every record.

**Option 4 — Deny-list at the egress boundary, key-name matching.** A redaction step at the egress boundary inspects each field's *key name* against a catalogue of sensitive identifiers (case-insensitive substring match) and replaces matching values with a fixed redaction marker. Recursive into nested dicts and lists. Centralized catalogue; one boundary; predictable cost; complemented by a code-review rule that secrets are never embedded in free-text values.

## Decision Outcome

**Chosen: Option 4 — deny-list at the egress boundary, key-name matching, applied uniformly across every structured-record egress channel.**

The redaction rule is centralized: one catalogue of sensitive key names, one redaction value, one algorithm. Each egress channel (the logging pipeline today; metrics emission, audit-event sinks, distributed-trace exporters in the future) installs the same redaction step at the boundary where structured records leave the process. A developer cannot bypass redaction by forgetting to call it at a call site, because the boundary is the egress channel, not the call.

Key-name matching is chosen over value pattern-matching because it is cheap, predictable, and false-positive-free for the categories that matter (credentials, tokens, session IDs — fields that consistently use those names). Value pattern-matching is rejected for its false-positive rate; allow-list is rejected for its friction with diagnostic context.

### Sensitive-key catalogue

The default deny list (case-insensitive substring match against a field's key name):

| Key pattern | Covers |
| --- | --- |
| `password`, `passwd`, `pwd` | Authentication credentials |
| `secret` | Generic shared secrets, signing keys |
| `token` | Bearer tokens, refresh tokens, API tokens |
| `api_key`, `apikey` | API keys |
| `authorization` | `Authorization` header values |
| `credential`, `credentials` | Generic credentials structures |
| `private_key` | Asymmetric private keys |
| `access_token`, `refresh_token`, `id_token` | OAuth/OIDC tokens |
| `session_id`, `sessionid`, `session` | Session identifiers |
| `cookie` | HTTP cookie values |
| `jwt`, `bearer` | JWT bodies, Bearer-scheme values |
| `signature`, `sig` | Request signatures (e.g., webhook HMACs) |
| `passphrase` | Phrase-based credentials |

A field whose key name *contains* any of these substrings (case-insensitive) is redacted. The match is on the key, not on the value. The catalogue is a project constant defined once in the redaction module.

### Redaction algorithm

- **Replacement value.** A field whose key matches the catalogue has its value replaced with the literal string `"***REDACTED***"`. The marker is constant — operators querying logs can grep for it and find every redaction site.
- **Recursion.** The algorithm walks nested `dict` and `list` structures recursively. A sensitive key at any depth is redacted; structure is preserved (the redacted field still exists, with its key intact and `"***REDACTED***"` as the value).
- **Type preservation for non-sensitive paths.** Non-sensitive values pass through unmodified; the algorithm does not coerce types or reformat values.
- **Key-name only.** Free-text values that *contain* sensitive substrings under non-sensitive keys (e.g., `event="user_invalid_password_attempt"`, `message="Authentication failed for token=…"`) are **not** redacted by the algorithm. The complementary rule is convention: code does not embed secrets in free-text messages, and code review enforces it.
- **Idempotent.** Applying the algorithm to an already-redacted record yields the same output; the marker `"***REDACTED***"` is stable across invocations.

### Extension hook

A feature whose data model includes additional sensitive field names that are not covered by the default catalogue contributes those names through configuration at boot:

- The application's settings expose a `redaction_extra_keys: tuple[str, ...]` field (per the configuration-ownership contract). Each entry is a substring matched the same way as the default catalogue.
- Extensions are **additive** — the defaults always apply; an extension never removes a default key.
- The settings validator rejects entries that overlap with the default catalogue (no duplicates) and entries that are zero-length or whitespace-only.

A feature that needs to opt *out* of redaction for a specific field must rename the field — there is no allow-list override. This keeps the egress boundary simple and uniform; deliberate opt-outs at one egress would create asymmetry across egress channels.

### Application across egress channels

Every channel that emits structured records from the process applies the redaction algorithm at the boundary, immediately before the record is serialized to its wire form:

- **Structured logs (stdout).** The redaction step is a processor in the logging pipeline, placed after every field-injecting processor and immediately before the renderer. The logging-and-observability decision pins the processor's position in the pipeline; the *algorithm and catalogue* are defined here.
- **Metrics labels** (when adopted). Labels attached to metric series are subject to the same redaction. A label whose key matches the catalogue is dropped or replaced (at metric emission, replacement preserves the series; dropping is acceptable when the label value would otherwise create high cardinality from sensitive data).
- **Audit events** (when adopted). Audit-event sinks apply the same redaction at their boundary unless the audit event's threat model deliberately requires unredacted values (in which case the audit channel is treated as a separate, restricted destination outside this policy's scope).
- **Distributed-trace attributes** (when adopted). Span attributes use the same catalogue and algorithm at the exporter boundary.

Each of those egress channels owns the *placement* of the redaction step in its own pipeline; this record owns the *algorithm and catalogue* they apply.

### Out-of-scope egress channels

Two specific egress channels are **explicitly outside** this record's scope; their disclosure rules are owned elsewhere:

- **HTTP error response bodies.** The `5xx`-generic / `4xx`-client-actionable rule for problem-details responses is a content-classification policy operating on a different threat model (untrusted external callers, body-content semantics, not key-pattern). It is owned by the API design and error-mapping decision.
- **Outbound HTTP request bodies.** The application sends payloads to vendor APIs that often *require* sensitive values (credentials, tokens) by construction. Outbound HTTP bodies are not redacted; that would break the integration. Outbound *headers* are not the egress this policy governs either — the HTTP-client wrapper transmits the headers required by the vendor.

### Application boundary

The redaction is the **last** transformation a record undergoes before serialization. Any subsequent step (the renderer, the exporter, the wire encoder) sees only redacted data. This places the enforcement boundary at the latest possible moment, after all field-injecting and field-deriving processors have run, so that no field can be injected after redaction has already passed.

## Consequences

**Positive:**

- One catalogue governs every egress channel. Adding a new sensitive key name extends the deny list once; every channel inherits the change automatically.
- Redaction is mechanical, not conventional. A developer cannot leak a field by forgetting to redact at the call site.
- The redaction marker is a fixed, greppable string. Operators auditing for sensitive-data exposure can search for `"***REDACTED***"` and find every redaction site; the absence of the marker in stored records means the catalogue did not match (an actionable signal).
- Future egress channels (metrics, audit, traces) inherit the policy. Adopting a new channel is "install the redaction processor at the boundary"; the catalogue does not need to be re-derived.
- Compliance posture — defense in depth required by OWASP guidance, GC privacy guidance, and the CWE-532 weakness pattern — is operationalized in code, not in convention.

**Tradeoffs accepted:**

- Key-name matching does not catch sensitive values stored under non-sensitive keys (e.g., a field `notes` that contains a token in free text). The mitigation is convention plus code review; the redaction policy is a layer of defense, not the only layer.
- The redaction step runs on every record. The cost is bounded — a recursive walk over a small dictionary — but is not zero. Acceptable given the diagnostic value and the legal/compliance posture.
- Extending the catalogue requires a configuration change at boot, not a runtime override. A new sensitive-key category that arrives mid-incident requires a deploy. Acceptable because the default catalogue covers the categories that matter and incidents-introducing-new-secret-types are rare.

**Risks:**

- A developer constructs a free-text message containing a secret (e.g., `f"Failed to authenticate with {token}"`). The message field is not redacted by key matching. Mitigation: code review; static analysis where feasible (e.g., a check that flags `f"..."` strings interpolating fields named like sensitive keys).
- A nested structure carries the secret under an obfuscated key name (e.g., `config.value` where `value` is an API key). The key `value` does not match the catalogue. Mitigation: features that bind nested configuration into log records use explicit, descriptive field names; the type-boundary rule (Pydantic models at egress) makes the field schema explicit.
- The catalogue grows so large that key-name matching becomes a per-record cost concern. Mitigation: the catalogue is short by design; substring matching is `O(n × m)` where `n` is field count and `m` is catalogue size, both bounded.
- A new egress channel is added and the redaction processor is forgotten. Mitigation: code review; the boundary review checklist names the redaction processor as a required step for any new structured-record egress.

## Confirmation

Compliance is verified by:

- **Repository contents.** A single module (e.g., `app/server/redaction.py` or equivalent infrastructure path) defines `mask_sensitive_data(record, extra_keys)` and the default catalogue as a named constant. No second implementation of the redaction algorithm exists.
- **Pipeline placement.** The logging-pipeline configuration (per the logging decision) installs the redaction processor immediately before the renderer. Future egress channels (metrics, audit, traces) install the same processor at their respective boundaries.
- **Configuration.** The application's settings expose `redaction_extra_keys` as a tuple of strings. The validator rejects duplicates with the default catalogue and zero-length entries.
- **Tests.** A unit test asserts that an event dict containing each default catalogue key, at every nesting depth (top-level, inside a dict, inside a list, inside a list of dicts), is redacted to `"***REDACTED***"`. A second test asserts that the algorithm is idempotent (applying it twice yields the same output). A third test asserts that an `redaction_extra_keys` value extends the deny list correctly without modifying the defaults.
- **Code review.** A PR adding a new structured-record egress channel includes the redaction processor at its boundary. A PR introducing a new sensitive field type adds it to the default catalogue or to feature-specific `redaction_extra_keys`. A PR that constructs a free-text log message interpolating a sensitive field name is rejected.

## Source References

1. OWASP — Logging Cheat Sheet
   - URL: <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes the categories of data that must never appear in logs (authentication credentials, encryption keys and primary secrets, access tokens, session identification values, payment card data, sensitive PII). Recommends sanitization at the collection point as defense in depth, not solely at the call site. Grounds the default catalogue contents and the rule that redaction lives at the egress boundary.

2. CWE-532 — Insertion of Sensitive Information into Log File
   - URL: <https://cwe.mitre.org/data/definitions/532.html>
   - Accessed: 2026-05-08
   - Relevance: The canonical weakness identifier for sensitive-data leakage into logs. Documents historical CVEs (admin credentials, SSH passwords, credit-card numbers, location data) where the leak occurred at the application's log-write boundary. Recommends "do not write secrets into the log files" as the primary mitigation. Grounds the boundary placement of the redaction step and the framing of the policy as a defense-in-depth control.

3. OWASP Top 10 — A09:2021 Security Logging and Monitoring Failures
   - URL: <https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/>
   - Accessed: 2026-05-08
   - Relevance: Frames inadequate logging policy (including failure to redact sensitive data before write) as a top-tier security risk. Establishes that defense-in-depth controls (sanitization at the boundary, complementing developer convention) are part of a mature security posture. Grounds the policy-level decision to enforce redaction mechanically rather than by convention alone.

4. Government of Canada — Digital Standards
   - URL: <https://www.canada.ca/en/government/system/digital-government/government-canada-digital-standards.html>
   - Accessed: 2026-05-01
   - Relevance: Establishes GC requirements for defensible technology decisions, including security-by-design and protection of sensitive personal information that informs the categories in the default catalogue. The redaction policy is one of the technical controls that operationalizes these requirements at the egress boundary.

## Change Log

- 2026-05-08: Created. Establishes a single deny-list catalogue (case-insensitive substring match on field key names) and a single redaction algorithm (recursive replacement with the literal string `"***REDACTED***"`) applied at every structured-record egress boundary in the application. Default catalogue covers credentials, secrets, tokens, session identifiers, cookies, JWTs, and signatures; the catalogue is extended per feature through `redaction_extra_keys` settings additively. The policy is the load-bearing redaction control for structured records emitted to logs (today) and to metrics labels, audit events, and distributed-trace attributes (when those channels are adopted). HTTP error-response bodies and outbound HTTP request bodies are explicitly out of scope: the former is owned by the API design and error-mapping decision; the latter is required-by-construction for vendor integrations. Extensions are additive; deliberate opt-outs at one egress are not provided — fields that must not be redacted are renamed instead.
