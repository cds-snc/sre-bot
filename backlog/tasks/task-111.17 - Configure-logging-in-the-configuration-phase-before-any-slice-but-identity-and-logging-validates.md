---
id: TASK-111.17
title: >-
  Configure logging in the configuration phase, before any slice but identity
  and [logging] validates
status: Done
assignee: []
created_date: '2026-10-23T16:42:00Z'
updated_date: '2026-10-23T18:25:00Z'
labels:
  - configuration
  - observability
milestone: m-7
dependencies:
  - TASK-111.7
references:
  - https://github.com/cds-snc/sre-bot/issues/1780
parent_task_id: TASK-111
type: feature
ordinal: 435000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The configuration phase runs in create_app() before lifespan configures structlog, so configuration-phase events render in console format in production (slack_signing_secret_not_set_in_socket_mode). Configure the existing pipeline right after the identity slice, the file install and the [logging] slice, before every other slice validates (decisions/observability.md one JSON stream, lifecycle.md phase 1). A slice validation error never carries an input value: pydantic renders every field, tokens included, into a failing validator's text, and ConfigurationSlice re-raises or chains it into uvicorn's boot traceback. Scope is ordering and error content only: how uvicorn and its factory error render is TASK-28.2, the move to server/logging/ TASK-115, the startup summary TASK-156. Single PR from main; deploys alone, before TASK-112 and TASK-111.9.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Logging is configured in the configuration phase right after the identity and [logging] slices load and before any other slice validates, so every configuration-phase event, the Slack slice's included, renders as JSON in production (decisions/observability.md, one shape)
- [x] #2 lifespan no longer configures logging; configure_logging takes the environment and the [logging] slice, with no host_info() fallback
- [x] #3 A slice validation failure raises a ConfigurationError naming each key and the reason, never an input value and with no chained validation error, and logs it once as configuration_invalid at critical; boot fails as before
- [x] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN FOR TASK-111.17 (logging configured in the configuration phase; slice errors carry no input value). STATUS: decisions settled by the human 2026-10-23 (Q3 accepted); plan awaiting final review. Written against main 3d1f33bd. Single PR from main; deploys alone, before TASK-112 and TASK-111.9. Re-run every rg before editing; line numbers are for the reviewer.

Merge gates: G-A1 gates green from app/ (ruff, mypy, pytest tests --ignore=tests/smoke, make check-import-contracts, make check-settings-key-ownership); G-A2 rollback tag re-read at merge (zsh /workspace/.claude-state/delivery/task-111.9/checks.zsh pre, image_tag); G-A3 merge outside a running deploy, an admin available 30 minutes.
AC -> step -> test: #1 A3 / T-A1,T-A2 ; #2 A2,A4 / T-A4,T-A5 ; #3 A3 / T-A3 ; #4 all / gates. T-A6 guards test-mode suppression.

== Ownership of the overlap (TASK-28.2, TASK-115, TASK-156) ==
- 111.17 (AC #5): only WHEN the existing pipeline is configured: right after identity, file install and [logging], before every other slice. configure_logging takes the environment instead of HostInfo; lifespan stops reconfiguring. A boot failure inside the configuration phase is logged once as a JSON CRITICAL event (Q3).
- TASK-28.2: HOW non-structlog records render: uvicorn/uvicorn.access through ProcessorFormatter for the launch paths (--log-config or handler takeover), single exception rendering (its AC #6), health-check classification. Stays the owner of: uvicorn's own "Error loading ASGI app factory" traceback, the lines before create_app runs, and failures before [logging] loads (missing ENVIRONMENT, unreadable file). 111.17 does not touch handlers beyond what configure_logging already installs (root ProcessorFormatter handler exists today, setup.py:226-239).
- TASK-115: the mechanical move of infrastructure/logging/ to server/logging/. 111.17 edits setup.py in its current home; 115 moves it later (its description already orders it after the pipeline fixes). No change to 115.
- TASK-156: WHAT startup reports (identity event, generated configuration summary, SecretStr typing, WARNING for weakening settings). 111.17 makes 156's summary renderable in the configuration phase but adds no event; _list_configs_from_sections stays. Slack tokens stay str here (repr=False only); SecretStr is 156 AC #3.

== Plan ==
Context: server/server.py:24 create_app() calls load_host_configuration() (server/configuration/host_configuration.py:56-90), which builds identity, installs the files, then validates server, security, directory, sre_ops, logging, Slack, Google, notify slices. Logging is configured only in lifespan (server/lifespan.py:60-61, :248 _get_logger_from_app -> configure_logging). Every event logged before lifespan uses structlog's default ConsoleRenderer: slack_signing_secret_not_set_in_socket_mode (integrations/slack/settings.py:129) rendered in console format in production (111.7 deploy, comment #2).
Steps (TDD, red first):
A1 Tests (red): T-A1..T-A6 below.
A2 infrastructure/logging/setup.py:140 configure_logging(environment: Literal["local","ci","production"], logging_settings: LoggingSettings, log_level: str | None = None): drop the HostInfo parameter and the host_info()/get_logging_settings() fallbacks (prod_mode = environment == "production"). Docstrings at setup.py:8-11 and logging/__init__.py:10-33 updated.
A3 server/configuration/host_configuration.py load_host_configuration: identity -> files -> install -> logging_settings = get_logging_settings() -> configure_logging(identity.environment, logging_settings) -> then server, security, directory, sre_ops, Slack, Google, notify (logging moved out of the later list). Wrap the slice builds after configure_logging: on ConfigurationError or pydantic ValidationError log.critical("configuration_invalid", error_type=..., errors=<locations only: loc + type per error, never input values>) then re-raise (Q3).
A4 server/lifespan.py: _get_logger_from_app returns structlog.stdlib.get_logger() (no reconfigure); configure_logging import removed; HostConfiguration.logging stays for the summary.
A5 ADRs (same PR): lifecycle.md phase 1 "logging is configured first, from identity and [logging], so every later configuration event is one JSON stream"; observability.md Logging paragraph adds the same sentence and names TASK-28.2 as owner of uvicorn's factory-error output; dependency-injection.md:72 removes "logging setup" from the host_info() readers; Changes lines dated.
Tests (app/tests; docstrings behaviour only):
T-A1 tests/integration/server/test_server_configuration_phase_logging_render.py: with _is_test_environment patched False (as TestConfigureLoggingRealCodePath does), ENVIRONMENT=production, Slack socket mode without signing secret: load_host_configuration(tmp config dir) emits slack_signing_secret_not_set_in_socket_mode; capfd stdout+stderr: every line json.loads, the event has level "info". Red today (console line).
T-A2 same file: order — a spy on get_server_settings asserts structlog is configured (structlog.is_configured() and root handler formatter is ProcessorFormatter) when the first non-logging slice builds.
T-A3 same file: an invalid [server] key -> one JSON line event "configuration_invalid" level "critical" naming the key location, no input value; the exception still propagates.
T-A4 tests/unit/infrastructure/logging/test_setup.py and test_logging.py: call sites move to configure_logging("ci"/"production", LoggingSettings()) (mechanical); production -> JSONRenderer, local -> ConsoleRenderer.
T-A5 tests/integration/server/test_lifespan.py:109-122: lifespan no longer calls configure_logging (assert not called).
T-A6 test-mode suppression unchanged: under pytest the configuration phase leaves root at CRITICAL+1 and capture_logs still works (test_slack_settings.py:179-204, test_server_configured_systems_read.py:121 green).
Doubts: (a) structlog.configure under pytest inside load_host_configuration may break a capture_logs block that wraps it -> verify by rg "capture_logs" around load_host_configuration/create_app and the T-A6 run. (b) uvicorn --reload/--factory calls create_app in the worker after uvicorn's dictConfig, so our root handler replaces nothing uvicorn owns (uvicorn/uvicorn.access propagate=False) -> verify locally with make dev: config events JSON-free in local (console) and T-A1 for production.
Blast radius A: logging only; a wrong configure call could drop or misformat every log line (the alarms are free-text regex, local.tf:9-26, so JSON level text still matches "level.{0,6}warning" skips). One git revert restores. Rollback: image tag of the then-current revision (G5).
Post-deploy A: zsh /workspace/.claude-state/delivery/task-111.9/checks.zsh post-logging -> RESULT rollout, boot_errors, config_phase_json (json >= running tasks, console = 0), slack_up, version all PASS.

== Decisions (settled by the human 2026-10-23) ==
Q3 How a configuration-phase failure is reported, and secrets in it. ADR: level covered (observability.md: CRITICAL is boot-fatal; lifecycle.md: invalid configuration fails boot naming the key); gap on the report itself and on input values. Reproduced 2026-10-23 with pydantic 2.14.1: a failing model_validator renders input_value={...} holding every field, the tokens included; ConfigurationSlice.__init__ (contracts/configuration.py:151-157) re-raises that ValidationError when no file key matches, and otherwise raises ConfigurationError "from error", whose chained cause prints the same text; uvicorn writes the traceback to stdout, so a failed boot can put a Slack token in CloudWatch, and key-name redaction never sees free text. This exists today (the current SlackSettings validator) and TASK-111.9 adds failure paths. Upcoming: none (TASK-156 covers the summary, TASK-28.2 rendering, not error content). Practice: Spring Boot reports a failed configuration-properties binding through a FailureAnalyzer that names the property and the reason, logged at ERROR, before the process exits; pydantic's ValidationError.errors(include_input=False, include_url=False) drops the value (verified in this repo's venv); `raise ... from None` (PEP 409) stops the chained cause from printing; OWASP Logging Cheat Sheet: never log secrets. ACCEPTED: (a) step A0 in this PR: ConfigurationSlice.__init__ always raises ConfigurationError built from errors(include_input=False), naming the file and table for a file key and the environment name (<TABLE>__<FIELD>) otherwise, raised from None; (b) the configuration_invalid event at CRITICAL (AC #3) carries that same text and the error type, once; (c) observability.md gains "A configuration-phase failure is logged once as configuration_invalid at CRITICAL, naming each key and the reason, never its value; the raised error carries no input value and no chained validation error"; (d) tests: T-A3 asserts a token-shaped value set on a failing slice appears in neither the exception text, its __cause__/__context__ rendering, nor any captured line; tests/unit/contracts/test_contracts_configuration_slice_load.py gains the raised-text cases. Adds contracts/configuration.py (~15 LOC); 4 prod files in all, still one PR.
Q5 Ownership of the overlap with TASK-28.2, TASK-115, TASK-156 (settled; their descriptions state it). ADR: covered (observability.md Migration names TASK-28 for uvicorn and stdlib routing; plugin-architecture.md puts logging setup in server/, TASK-115; TASK-156 records its own amendment). No gap. Scope notes only: comments on TASK-28.2 (the ordering landed here; its gap is uvicorn's own and factory-error output), TASK-115 (configure_logging's signature changes here first), TASK-156 (its AC #2 "Lifespan's configuration phase" is the app factory's since 111.7; the summary can now be emitted there as JSON).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Logging is configured in the configuration phase: load_host_configuration (server/configuration/host_configuration.py) builds identity, installs the files, builds [logging], calls configure_logging(environment, logging_settings), then validates every other slice. configure_logging (infrastructure/logging/setup.py) takes the environment and the slice, with no host_info() or provider fallback; lifespan only fetches the logger.

Slice errors carry no input value: ConfigurationSlice raises ConfigurationError from describe_validation_error (contracts/configuration.py) built from errors(include_input=False), raised from None. The phase also converts a pydantic ValidationError from a slice not yet on the files (Slack, Google) the same way. Either failure logs one configuration_invalid event at critical and re-raises.

Scope addition: modules/sre/platforms/slack.py and modules/dev/platforms/slack.py built a Slack Web client at import, which validated and cached the Slack slice before create_app ran; that import-time build was the console line seen in the 111.7 deploy. Both now build the client when a command runs. Verified with ENVIRONMENT=production and create_app() in a Codespace: slack_signing_secret_not_set_in_socket_mode renders as JSON.

ADRs: observability.md (logging starts in the configuration phase; configuration_invalid), lifecycle.md phase 1, dependency-injection.md (logging setup leaves the host_info() readers).

Tests: test_server_configuration_phase_logging_render.py (JSON render, order, critical event without the value, vendor slice without the token); test_contracts_configuration_slice_load.py (+3 no-value cases); test_modules_slack_platforms_import.py (import builds no Slack settings; red without the fix); configure_logging call sites in test_setup.py and test_logging.py; test_lifespan.py, test_lifespan_vendor_slice_validation.py, the notify slice test and the incident updates surface test follow the new behaviour.

Gates (from app/): ruff check . -> All checks passed!; mypy -> Found 47 errors in 18 files (baseline 47, none in touched files); pytest tests --ignore=tests/smoke -> 5684 passed; make check-import-contracts -> Contracts: 12 kept, 0 broken; make check-settings-key-ownership -> OK.

Open, not in scope: a value supplied by an environment variable for a key that a file also sets is still attributed to the file (the known follow-up); webhook pattern auto-discovery logs at import, before create_app, in console format (TASK-28.2, lines before create_app).
<!-- SECTION:NOTES:END -->
