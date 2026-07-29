---
id: TASK-9
title: Validate the Slack signing secret at boot (both delivery modes)
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-07 19:56'
updated_date: '2026-07-29 13:18'
labels:
  - security
  - phase-0
  - slack
milestone: m-0
dependencies: []
references:
  - decisions/transport-slack.md
  - decisions/configuration.md
  - decisions/security.md
  - 'https://docs.slack.dev/apis/events-api/comparing-http-socket-mode/'
  - 'https://docs.slack.dev/authentication/verifying-requests-from-slack'
priority: medium
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scope (post-split): validate the Slack signing secret at application boot. The HTTP-mode per-request HMAC verification that previously shared this task is now tracked separately as a deferred follow-up (see the split-out Slack HTTP-mode HMAC verification task) because the app runs Socket Mode today and HTTP Events mode is future work.

Aligns with decisions/transport-slack.md (Verification) and decisions/configuration.md (fail fast at boot on missing required config). Today the signing secret is defined and validated only when Socket Mode is off; in Socket Mode request authenticity is carried by the connection handshake, but the secret should still be present so a later switch to HTTP mode is safe.

Steps:
1. At boot, if HTTP Events mode is selected (SLACK__SOCKET_MODE=false), fail fast when no signing secret is configured (decisions/configuration.md).
2. In Socket Mode, still check whether the signing secret is present at boot so operators have visibility before a later mode switch; surface this via a clear, informational log entry (not a warning/error) since Socket Mode does not require the secret to function and is today's default, expected configuration.
3. Document in the Slack transport module docstring that Socket Mode relies on the connection handshake for request authenticity, and that HTTP-mode per-request HMAC verification is a separate, deferred task and is not yet implemented.

Out of scope (moved to the deferred HTTP-mode task): computing/verifying the v0= HMAC-SHA256 over timestamp+body, constant-time compare, and the 5-minute replay window. That work only matters once HTTP Events mode is actually enabled.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Boot fails fast when HTTP Events mode is selected (SLACK__SOCKET_MODE=false) and no signing secret is configured
- [ ] #2 In Socket Mode, a missing signing secret is detected at boot and surfaced via a clear, informational log entry (not a warning/error, since Socket Mode does not require it to function) so operators have visibility before a later switch to HTTP mode
- [ ] #3 The Slack transport module docstring documents that Socket Mode relies on the connection handshake and that HTTP-mode per-request HMAC verification is deferred to a separate task and not yet implemented
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Boot-validation tests pass: HTTP mode without a secret fails fast; Socket Mode without a secret is flagged; with a secret the app boots in both modes
- [ ] #2 PR references decisions/transport-slack.md and decisions/configuration.md and links the deferred HTTP-mode HMAC verification follow-up task
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
## Implementation Plan (TASK-9)

### Official Slack documentation confirmation (2026-07-29)
Confirmed the design against Slack's own docs before finalizing:
- [Comparing HTTP & Socket Mode](https://docs.slack.dev/apis/events-api/comparing-http-socket-mode/):
  a Slack app receives events via **either** HTTP request URLs **or** Socket Mode
  (WebSocket) — these are alternative, mutually exclusive delivery mechanisms
  chosen in the app's settings, never both at once. This matches
  `SlackSettings.SOCKET_MODE: bool` as a single either/or switch — no code change
  needed, existing shape is already correct.
- [Verifying requests from Slack](https://docs.slack.dev/authentication/verifying-requests-from-slack):
  the signing-secret/`X-Slack-Signature` HMAC scheme exists **specifically to
  verify inbound HTTP requests** (Events API, slash commands, shortcuts/interactivity
  delivered over HTTP). Socket Mode does not receive inbound HTTP requests from
  Slack at all (events arrive over the WebSocket the app itself opened, authenticated
  by the app-level token in the handshake) — there is no `X-Slack-Signature` to
  verify in Socket Mode because there is no inbound HTTP request to verify.
- **Conclusion**: the signing secret is architecturally mandatory only for HTTP
  Events mode; a missing secret in Socket Mode is not a functional problem, and
  Socket Mode + no signing secret is today's *default, expected* configuration
  (`SOCKET_MODE` defaults `True`, `SIGNING_SECRET` defaults `None`).
- Also reconfirmed: Slack connectivity is legitimately optional
  (`SlackSettings.ENABLED` defaults `False`, validator short-circuits entirely
  when disabled) — no change needed, already correct.

### Log severity for AC#2, reconsidered and confirmed with human reviewer (2026-07-29)
Initial plan used `logger.warning(...)` for Socket Mode + missing signing secret,
reusing the `_initialize_security_services`/`ISSUER_CONFIG` "missing config ->
warn" precedent. On review this precedent doesn't actually transfer: a missing
`ISSUER_CONFIG` breaks authenticated endpoints *right now* (a real, current
problem worth a WARNING), whereas a missing `SIGNING_SECRET` in Socket Mode has
**zero current functional impact** and is the **default out-of-the-box state** —
logging a `WARNING` on every boot of the common/happy path is exactly the
"warn on expected behavior" anti-pattern flagged during review (trains operators
to ignore warnings). **Human confirmed (2026-07-29): downgrade to an INFO-level
log entry, not a WARNING.** AC#2 is reworded accordingly (see Acceptance
Criteria) from "surfaced as a clear, actionable error or warning" to "surfaced
via a clear, informational log entry" — this is a visibility/readiness signal
for a *future* mode switch, not a report of a current defect; AC#1's hard fail
at the moment someone actually flips to HTTP mode remains the real safety net.

### Scope confirmed against current code
- `app/integrations/slack/settings.py::SlackSettings._validate_transport_credentials`
  (a `model_validator(mode="after")`, fires at `SlackSettings()` construction inside
  `get_slack_settings()`, which is `@lru_cache`d and first invoked from
  `get_slack_provider()` at `app/server/lifespan.py` boot) **already implements AC#1**:
  when `ENABLED=True` and `SOCKET_MODE=False` (HTTP Events mode) and `SIGNING_SECRET`
  is falsy, it raises `ValueError("SLACK_SIGNING_SECRET is required when
  SLACK_SOCKET_MODE=false and SLACK_ENABLED=true")` — a hard boot failure naming the
  variable, matching decisions/configuration.md's fail-fast contract, and matching
  Slack's own documented requirement that HTTP mode cannot verify requests without
  a signing secret. Covered today by `app/tests/unit/integrations/slack/
  test_slack_settings.py::TestSlackSettingsFailFast::
  test_http_events_enabled_without_signing_secret_raises`. No code change needed
  for AC#1; only confirm the existing test still passes.
- **Gap is AC#2 only**: when `ENABLED=True` and `SOCKET_MODE=True`, the validator
  currently checks `APP_TOKEN` but never looks at `SIGNING_SECRET` at all — nothing
  gives an operator early visibility that the secret isn't set yet, before they
  attempt a future mode switch.
- AC#3 (module docstring) is not yet documented anywhere: `app/integrations/slack/
  bootstrap.py` (`SlackBootstrap`/`LegacySlackBootstrap.create_app`) is the exact
  wiring point — `request_verification_enabled = not self.settings.SOCKET_MODE` is
  passed straight to Bolt's `App`/`AsyncApp` constructor, i.e. Bolt's own built-in
  request-signature verifier is what gets toggled by delivery mode. Its module
  docstring today only says "Contains Slack integration bootstrap code, including
  Bolt app factories and setup helpers." — no mention of the verification split.

### Steps
1. `app/integrations/slack/settings.py`:
   - Add `import structlog` and a module-level `logger = structlog.get_logger(__name__)`.
   - Extend `_validate_transport_credentials` with a third, independent check after
     the two existing `raise` branches (still gated by the existing top `if not
     self.ENABLED: return self`):
     ```python
     if self.SOCKET_MODE and not self.SIGNING_SECRET:
         logger.info(
             "slack_signing_secret_not_set_in_socket_mode",
             detail=(
                 "SLACK_SIGNING_SECRET is not set. Socket Mode does not need it "
                 "for request authenticity (the connection handshake carries "
                 "that), but it must be configured before switching to HTTP "
                 "Events mode (SLACK__SOCKET_MODE=false), which fails boot "
                 "without it."
             ),
         )
     ```
   - Update the module docstring to state both behaviors (HTTP mode fails boot;
     Socket Mode logs an informational notice, not a warning) in one place, so the
     settings module is the single source of truth for the validation contract.
   - Satisfies AC#2 (and re-confirms AC#1, unchanged).
2. `app/integrations/slack/bootstrap.py`:
   - Extend the module docstring only (no behavior change) to document, in
     behavior-only terms (no task IDs, no dates — matches this repo's docstring
     convention): `request_verification_enabled` mirrors delivery mode; Socket Mode
     relies on the connection handshake for request authenticity and Bolt's
     per-request verifier is disabled; HTTP Events mode enables Bolt's built-in
     `v0=` HMAC-SHA256-with-timestamp request verification; per-request HMAC
     verification beyond Bolt's own HTTP-mode check is not implemented in this
     module.
   - Satisfies AC#3.
3. `app/tests/unit/integrations/slack/test_slack_settings.py`:
   - New test class `TestSlackSettingsSocketModeSigningSecretNotice`:
     - Socket Mode + `ENABLED=True` + no `SIGNING_SECRET` -> construction succeeds
       (no raise) AND a `slack_signing_secret_not_set_in_socket_mode` **info-level**
       event is captured (`structlog.testing.capture_logs()`, precedent:
       `app/tests/integrations/aws/test_client_next.py`; assert
       `entry["log_level"] == "info"` alongside the event name, so a future
       regression to `warning`/`error` fails the test).
     - Socket Mode + `ENABLED=True` + `SIGNING_SECRET` set -> no such event
       captured.
     - Socket Mode + `ENABLED=False` + no `SIGNING_SECRET` -> no event captured
       (disabled short-circuits all validation, existing contract — confirms
       Slack stays an optional, opt-in configuration).
   - No changes needed to the existing `TestSlackSettingsFailFast` class (AC#1
     already covered); keep as regression coverage.

### AC-to-step-to-test traceability
- AC#1 (HTTP mode fails fast without secret): already implemented; step 3 keeps
  `test_http_events_enabled_without_signing_secret_raises` as regression coverage;
  no new test required.
- AC#2 (Socket Mode missing secret surfaced via an informational log entry): step 1
  (info log) + step 3 (new `TestSlackSettingsSocketModeSigningSecretNotice` tests,
  including an explicit assertion on log level to prevent silent severity drift).
- AC#3 (transport module docstring): step 2 (docstring only; no automated test —
  docstring content isn't asserted in this repo's test suite, matching how the
  existing docstrings aren't tested either).

### Test matrix
| Mode        | ENABLED | SIGNING_SECRET | Expected                                        |
|-------------|---------|-----------------|--------------------------------------------------|
| Socket      | False   | absent          | boots, no log entry (existing, unchanged)          |
| Socket      | True    | absent          | boots, INFO-level notice logged (NEW)              |
| Socket      | True    | present         | boots, no notice (NEW)                             |
| HTTP Events | True    | absent          | raises `ValueError` naming the var (existing)      |
| HTTP Events | True    | present         | boots, no notice (existing)                        |

### Assumptions / doubts to verify with human reviewer
1. ~~Warn vs. raise for AC#2~~ — **resolved twice**: first confirmed via official
   Slack documentation that Socket Mode has no functional need for the secret;
   then, on review, the log **severity** itself was reconsidered and the human
   confirmed INFO (not WARNING) is correct, since Socket-Mode-without-secret is
   today's default/expected state, not a problem. No further sign-off needed.
2. Whether `SLACK_ENABLED`/`SLACK_SIGNING_SECRET` are actually provisioned in the real
   production ECS task definition/SSM today is unverified from this repo alone
   (`terraform/templates/sre-bot.json.tpl` shows no Slack env vars or secrets at all,
   which appears to be a pre-existing terraform/config gap unrelated to this task —
   flagging, not fixing, since it's out of this task's scope). Human has since
   confirmed the secret is indeed absent from the real deployment today, consistent
   with this finding.
3. AC#3 asks the docstring to say verification is "deferred to a separate task" —
   per this repo's established docstring convention (behavior-only, no task IDs/dates
   in code), the docstring will describe the *behavior* (not-yet-implemented) without
   naming TASK-51; the PR description (not code) is where TASK-51 gets linked, per
   DoD #2.

### Blast radius / rollback
- Single subsystem (`app/integrations/slack/`), two production files touched
  (~15-20 LOC total: one new import, one logger, one `if` block, two docstring
  edits), one test file extended. No settings field added/removed/renamed, no env
  var contract change, no route/API/schema change, no terraform change.
- New behavior is additive-only (an info log line) in the only changed runtime
  path; the two existing hard-fail branches are untouched. Fully backward
  compatible: processes that boot successfully today keep booting successfully,
  with no new noise at the default log level operators already watch for problems.
- Rollback: revert the single commit; no data/schema/migration involved.

### Size verdict
Fits comfortably in one reviewable PR (single settings module logic change +
docstring + tests, ~20 production LOC, one subsystem). No decomposition needed.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-27 14:02
---
Scope split (2026-07-27): this task was narrowed to boot-time signing-secret validation, which is doable now while the app runs Socket Mode. The HTTP-mode per-request HMAC verification (v0= HMAC-SHA256 over timestamp+body, constant-time compare, 5-minute replay window) - the provider-signed tier of decisions/security.md's tiered webhook trust model - is split out into a separate follow-up task and DEFERRED until further notice, because HTTP Events mode is future work and is not exposed under Socket Mode. The generic-webhook HMAC tier remains separate (TASK-47/TASK-48); Phase-1 origin observability is TASK-46. GitHub issue 1263 (Slack HTTP verification) moves with the deferred HMAC task.
---

created: 2026-07-29 13:04
---
Confirmed via official Slack docs (2026-07-29): HTTP and Socket Mode are mutually exclusive delivery mechanisms, and the signing-secret/X-Slack-Signature HMAC scheme verifies inbound HTTP requests only -- Socket Mode has no inbound HTTP request to verify, authenticity comes from the WebSocket handshake. This confirms warn-not-raise for AC#2 is the protocol-correct behavior (not just risk-avoidance), and confirms Slack stays an opt-in, non-mandatory configuration (ENABLED defaults false) with the signing secret mandatory only once HTTP mode is selected. Human also confirmed SLACK_SIGNING_SECRET is indeed absent from the real deployment today, consistent with the terraform gap found during planning.
---

created: 2026-07-29 13:14
---
Reconsidered AC#2's log severity (2026-07-29): human correctly challenged WARNING-on-boot for Socket-Mode-without-signing-secret, since that is today's default/expected configuration, not a current problem (unlike the ISSUER_CONFIG precedent I'd reused, which IS a live functional break). Downgraded to an INFO-level structlog notice per human's explicit choice; AC#2 and Description Step 2 reworded from 'error or warning' to 'informational log entry' for consistency. AC#1's hard fail-fast in HTTP mode is unchanged and remains the real safety guarantee for mode switches.
---
<!-- COMMENTS:END -->
