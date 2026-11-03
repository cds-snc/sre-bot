---
id: TASK-28.2
title: >-
  Route uvicorn and pre-configuration lines through the structlog pipeline;
  logger name and explicit UTC on every line
status: In Progress
assignee: []
created_date: 2026-09-15 14:08
updated_date: '2026-11-03T17:20:00Z'
labels:
  - infrastructure
  - phase-4
  - observability
milestone: m-4
dependencies:
  - TASK-111.17
references:
  - decisions/observability.md
  - decisions/health-checks.md
  - app/infrastructure/logging/setup.py
  - app/server/lifespan.py
  - app/Makefile
  - app/tests/unit/infrastructure/logging/test_setup.py
  - https://github.com/cds-snc/sre-bot/issues/1609
  - Dockerfile
parent_task_id: TASK-28
priority: high
ordinal: 208000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Step 4 of TASK-28 (decisions/observability.md: one shape for the whole stream; stdlib and uvicorn logs route through ProcessorFormatter with a matching foreign chain). Re-verify line numbers and versions before planning.

ALREADY IN PLACE. infrastructure/logging/setup.py configure_logging installs one root StreamHandler with a structlog.stdlib.ProcessorFormatter (foreign_pre_chain = add_logger_name plus the shared base processors, redaction included; renderers remove_processors_meta then ConsoleRenderer or JSONRenderer), and structlog events end in wrap_for_formatter. Stdlib loggers that propagate to root (slack_sdk, slack_bolt, botocore) already render through the pipeline, and a stdlib exception renders as one JSON line (tests/unit/infrastructure/logging/test_setup.py TestStdlibLoggingBridge). TASK-111.17 calls configure_logging in create_app()'s configuration phase right after identity and [logging], and lifespan stops configuring logging.

THIS TASK OWNS how the remaining non-structlog lines render:
1. uvicorn and uvicorn.access. uvicorn is launched with no --log-config (the image's ENTRYPOINT in Dockerfile: uvicorn --factory main:create_app --host=0.0.0.0, since TASK-111.15.1 deleted app/bin/entry.sh; app/Makefile dev, debug and run targets), so its default LOGGING_CONFIG gives uvicorn and uvicorn.access their own handlers with propagate=False and plain formatters; their lines (startup, access lines, uvicorn's own 'Error loading ASGI app factory' traceback) bypass the pipeline.
2. Lines emitted before create_app runs, and failures before [logging] loads (missing ENVIRONMENT, unreadable configuration file).
3. structlog-native events carry no logger name (add_logger_name is only in the foreign chain), and TimeStamper(fmt="iso") relies on the library's UTC default where the ADR Checks require utc=True set explicitly.

OPTIONS FOR THE PLANNER (confirm against current structlog and uvicorn docs)
a. In configure_logging: clear the handlers on uvicorn and uvicorn.access and let them propagate to the root handler. Smallest diff; misses what uvicorn emits before create_app runs, including its app-factory error.
b. Pass a logging config to uvicorn (--log-config in the Dockerfile ENTRYPOINT and the Makefile) so uvicorn never installs its own handlers. Covers every line; touches the deploy entrypoint.
c. Configure at import time in main.py: conflicts with the no-import-time-side-effects rule (CLAUDE.md, decisions/plugins.md). Avoid.
Callsite parameters on foreign records resolve to the logging module, not the caller; decide whether to drop them for foreign records.

HEALTH-CHECK CLASSIFICATION (decisions/observability.md). Once uvicorn.access goes through the pipeline, a narrow logging.Filter classifies EXACT liveness hits (GET, path in {/version, /health}, status 200, no query string) as DEBUG or event_type=healthcheck; never drop them. Probe sources: ALB target group GET /version (terraform/alb.tf), Route53 HTTPS /version (terraform/route53.tf), Dockerfile HEALTHCHECK GET /health. The planner decides whether this fits the slice or becomes a follow-up (size gate).

OPERATIONAL IMPACT. terraform/local.tf's error metric filter is a free-text regex, so uvicorn plain-text access lines such as 'POST /hook/... 500' count as separate errors; TASK-94 reworks the alarms on JSON fields and depends on this task.

NOT A BUG, DO NOT CHASE (human decision: leave as is). Local-dev 'WARNING: Invalid HTTP request received.' bursts and 'HEAD / HTTP/1.1 405' come from VS Code port forwarding of 8000 (a TLS ClientHello on the plain-HTTP port; HEAD on the GET-only landing route). Production cannot see them (the ALB terminates TLS; every health check is GET). Do not suppress: after this slice they render through the pipeline like everything else.

TESTS. Extend tests/unit/infrastructure/logging/test_setup.py (TestConfigureLoggingRealCodePath, TestStdlibLoggingBridge) for uvicorn and uvicorn.access rendering; tests/unit/infrastructure/test_logging.py is legacy, touch it minimally; the pytest suppression branch of configure_logging must keep silencing everything.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 uvicorn's app-factory error and failures before [logging] loads (missing ENVIRONMENT, unreadable configuration file) render in the shape decided at planning, with no raw multi-line traceback in production, verified by a test
- [x] #2 Every rendered line, structlog-native or foreign, carries a UTC ISO-8601 timestamp (TimeStamper utc=True set explicitly) and a logger name
- [x] #3 Sensitive keys on foreign records, uvicorn's included, are redacted by the same mask_sensitive_data processor, verified by a test
- [x] #4 Logging stays fully suppressed under pytest, and existing redaction and stdlib-bridge pipeline tests stay green
- [x] #5 In production mode, a log.exception call (or any call with exc_info=True) emits exactly one line: a JSON object whose exception field holds the traceback. No raw traceback lines follow on stdout or stderr, verified by a test that captures both streams
- [x] #6 uvicorn and uvicorn.access records render through the pipeline for the documented launch paths (the Dockerfile ENTRYPOINT and the app/Makefile targets, uvicorn --factory main:create_app); a uvicorn access line renders as one JSON object in production mode, verified by a test
- [x] #7 A failure before [logging] loads (invalid ENVIRONMENT, unreadable or malformed configuration file) and any exception that escapes create_app each render as exactly one JSON line at CRITICAL on stderr and the process exits non-zero, verified by a subprocess test that launches uvicorn --factory
- [x] #8 Exact liveness hits on uvicorn.access (GET, path /version or /health, status 200, no query string) log at DEBUG and are emitted when DEBUG is enabled; any other method, status, path or query logs unchanged at INFO; never dropped; verified by boundary tests
- [x] #9 bin/deploy-checks.zsh post no longer expects uvicorn plain-text lines: the Non-JSON section excludes only the known import-time webhook pattern lines and returns PASS or WARN; no terraform, Dockerfile or Makefile change
- [x] #10 Dead code in the touched logging files is deleted with its tests (truncate_large_values, add_environment_info, the vacuous get_module_logger tests); ruff, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Proposed 2026-10-30, awaiting human approval.

PLAN FOR TASK-28.2 (single PR from main after TASK-175 merges; no terraform, Dockerfile or Makefile change)

== 1. Verified facts the design rests on (versions: uvicorn 0.54.0, structlog 26.1.0, fastapi 0.156.8, starlette 1.9.0: app/uv.lock; pyproject.toml:11,30,32) ==
F1. uvicorn builds Config (and runs dictConfig of its default LOGGING_CONFIG: uvicorn/config.py:83-114, Config.__init__ calls configure_logging at :303) BEFORE it imports the app and calls the factory (Config.load, :439; factory call :513). So every uvicorn handler already exists when create_app runs; clearing them from create_app's configuration phase works (scratch run with the real configure_logging: every startup, access and shutdown line rendered as one JSON object).
F2. uvicorn catches ONLY TypeError from the factory call (config.py:513-518, "Error loading ASGI app factory: %s", message only, no traceback) and only ImportFromStringError for the import (:431-437). Any other exception from create_app (ConfigurationError, pydantic ValidationError for a missing ENVIRONMENT, TOML errors) is NOT logged by uvicorn: it reaches Python's default excepthook and prints a raw multi-line traceback. Reproduced: today, after the configuration_invalid JSON line, a raw traceback follows (so AC #1/#5's "no raw traceback" is not met by option a or b alone). Neither --log-config nor handler clearing touches this path.
F3. structlog 26.1 CallsiteParameterAdder reads the LogRecord's own pathname/lineno/funcName for foreign records (structlog/processors.py:927-938), so foreign callsite values are the real caller (uvicorn/protocols/http/h11_impl.py:477 in the scratch run), not the logging module. The task description's premise is stale. Decision: keep.
F4. ProcessorFormatter.format (structlog/stdlib.py:1136-1215) clears record.exc_info/exc_text when keep_exc_info is False (default); the setup.py basicConfig remnant named in the 2026-09-15 finding is gone from the production branch (only the pytest branch calls basicConfig, setup.py:207-211). The duplicate-traceback mechanism is therefore already closed for stdlib records; remaining raw tracebacks come from F2.
F5. dictConfig cannot carry the structlog chain from a JSON/YAML file: "()" factories are resolved only for handler/formatter/filter entries, and kwargs values are passed as-is (docs.python.org/3/library/logging.config.html); structlog's own dictConfig example builds the processor list in Python (structlog.org/en/stable/standard-library.html). A --log-config file would need an importable factory that returns a formatter delegating to a pipeline configured later (it needs ENVIRONMENT and redaction_extra_keys, known only after the configuration phase).
F6. uvicorn 0.54 access records carry only args (client, method, path?query, http_version, status) in message '%s - "%s %s HTTP/%s" %d' (protocols/http/h11_impl.py:477-484); no extra fields. The plain-text 'Internal Server Error' phrase in today's access lines comes from uvicorn's AccessFormatter, which disappears once the handler is cleared.
F7. Structlog events emitted while modules IMPORT (modules/webhooks: registered_notification_pattern, registered_pattern, no_handlers_found_in_module, notification_handlers_initialization_complete: 13 lines in a local run of main:create_app) and Python warnings raised at import render before create_app runs, in structlog's unconfigured default console format on stdout. Only configuring at import time would change that (option c, rejected). TASK-168 removes the import-time discovery.

== 2. Design (decisions; reasons in the report) ==
D1. Option (a), plus two additions that option a/b both need and neither provides: a bootstrap pipeline and an uncaught-exception hook. Option (b) rejected: it only adds coverage for uvicorn's own 'Error loading ASGI app' message, the --reload supervisor lines in local dev and uvicorn lines before the factory (none in production), at the price of a second place defining the shape (importable lazy formatter), an image-entrypoint change (Dockerfile:57 and its contract test test_bin_container_start_contract.py:35), three Makefile targets (app/Makefile:4,12,126) and a rollback target that is the image rather than the code.
D2. Lines before [logging] loads: a bootstrap pipeline = configure_logging("production", LoggingSettings.model_construct()) installed first thing in load_host_configuration (always JSON, default level INFO, default redaction keys, no service identity because identity is what may have failed). Failure shape: ONE JSON line at CRITICAL. A ConfigurationError or pydantic ValidationError raised in the configuration phase (identity, file selection, [logging]) is logged as configuration_invalid (phase=configuration, error=value-free text from describe_validation_error), then re-raised UNCHANGED (test_server.py:144 expects ValueError). Anything else escaping the factory is logged by sys.excepthook as uncaught_exception (CRITICAL, exception field with the traceback). The hook skips the types already reported (ConfigurationError, ValidationError) so each failure is one line, not two. KeyboardInterrupt goes to sys.__excepthook__. Exit code stays 1.
D3. uvicorn routing: in configure_logging's non-pytest branch, for uvicorn, uvicorn.error, uvicorn.access, uvicorn.asgi: handlers cleared, propagate=True, level NOTSET (root level from [logging] is the one knob). The pytest branch is untouched, so it keeps silencing everything and never touches excepthook or the uvicorn loggers.
D4. Logger name and UTC: add structlog.stdlib.add_logger_name to _build_base_processors (after add_log_level, so native and foreign records share one chain) and drop it from the foreign_pre_chain list; TimeStamper(fmt="iso", utc=True). Verified that structlog.get_logger() gives the caller's module name through LoggerFactory.
D5. Health checks in this slice (about 40 LOC, no new subsystem): a logging.Filter on uvicorn.access (new infrastructure/logging/filters.py) re-levels EXACT liveness hits (args: method GET, path exactly /version or /health with no query, status 200) to DEBUG and emits them only when DEBUG is enabled, which is what logger.debug does; any other method, status, path or query logs unchanged at INFO. It must live on the logger (not the root handler) and return False when DEBUG is off, because a handler without a level would otherwise still emit a re-levelled record. Never dropped at DEBUG; probes: terraform/alb.tf (GET /version), terraform/route53.tf (GET /version), Dockerfile:52-53 and the task definition healthCheck (GET /health).
D6. Residual plain lines after this slice, stated in the ADR and the deploy check: uvicorn's own 'Error loading ASGI app' import message, the --reload supervisor lines in local dev, import-time structlog events (webhook patterns, until TASK-168) and import-time warnings. logging.captureWarnings(True) in configure_logging routes warnings raised after the factory starts into the pipeline.
D7. create_app guard (AC #1): since uvicorn keeps only the message of a TypeError raised inside the factory, create_app logs app_factory_failed (CRITICAL, exc_info) for a TypeError and re-raises; uvicorn's own message line then renders as JSON too.

== 3. Ordered steps (TDD: failing tests first, then code) ==
S1 app/infrastructure/logging/setup.py
 - :136 TimeStamper(fmt="iso", utc=True); add structlog.stdlib.add_logger_name inside _build_base_processors (:129-153) and remove it from foreign_pre_chain (:246).
 - after the root handler block (:241-256): helper _route_uvicorn_through_root() for the four loggers (D3), logging.captureWarnings(True), and attach the liveness filter (S2) to the uvicorn.access logger.
 - new configure_bootstrap_logging() (D2) and install_uncaught_exception_hook(reported: tuple[type[BaseException], ...]) (D2); both return immediately when _is_test_environment() (:97-103).
 - update the module docstring (:1-20).
S2 app/infrastructure/logging/filters.py (new): LivenessAccessFilter(logging.Filter), constants for the two paths. No import of concrete infrastructure services (CLAUDE.md import boundaries). Lives in the logging directory so TASK-115's directory move carries it.
S3 app/server/configuration/host_configuration.py:158-182 (load_host_configuration): call configure_bootstrap_logging() and install_uncaught_exception_hook(reported=(ConfigurationError, ValidationError)) first; wrap get_identity_settings / load_configuration_files / install_configuration_files / get_logging_settings (:166-169) in the same except branches that already exist for the slices (:173-180) so a pre-[logging] failure logs configuration_invalid once; keep the raised type. The existing _log_invalid (:185-186) is reused.
S4 app/server/server.py:18-45 (create_app): the TypeError guard (D7), a few lines.
S5 Dead code in the touched logging files (delete, evidence: rg finds only __init__.py, formatters.py and test_formatters.py; the human dropped the environment field in TASK-156): app/infrastructure/logging/formatters.py:140-163 truncate_large_values, :166-end add_environment_info; their exports app/infrastructure/logging/__init__.py:56-61,76-79; their tests tests/unit/infrastructure/logging/test_formatters.py (TestTruncateLargeValues :266, TestAddEnvironmentInfo :347). In the legacy tests/unit/infrastructure/test_logging.py delete only the class TestGetModuleLoggerBackwardCompat (:90-105, tests a function that no longer exists); check tests/integration/infrastructure/test_logging_integration.py:7,18,30 for the same names and delete the vacuous ones only. Fix the stale docstring references in formatters.py/__init__.py ("extra_processors").
S6 bin/deploy-checks.zsh:144-146 (Non-JSON section): retitle (drop 'uvicorn lines expected until TASK-28.2'), exclude the known import-time webhook pattern lines from the count with a second 'not like' clause, add result non_json_lines PASS or WARN (n); update the header comment of the check. Verify with zsh -n bin/deploy-checks.zsh. Lines 93-95 (pre baseline), 112-124 (boot and runtime errors keyed on level and /Traceback/, still true for JSON lines whose exception field holds the traceback) and 153 need no change.
S7 Docs in the same PR (decisions/observability.md, health-checks.md Checks, doc-11 rows 9a.1/9a.2 and the open-decisions line, TASK-28.2 notes): see the report's proposed edits; they are applied after the human decides.

== 4. Operational impact (verified, no terraform change) ==
- terraform/local.tf:10-16 error filter: [w=%error|exception% && w!=%level.{0,6}warning|level.{0,6}info|HTTP/1.[01]. [1-4][0-9][0-9] %] is applied to the raw line. After this PR (a) every uvicorn INFO line is JSON with "level": "info", which the level.{0,6}info clause excludes (the "uvicorn.error" logger name contains 'error' but is excluded by the same clause); (b) uvicorn access lines at status 5xx are INFO, so they NO LONGER count (today they count through the 'Internal Server Error' phrase of AccessFormatter): this is a coverage loss for a 5xx that has no application error event, until TASK-94; (c) an unhandled exception is now ONE level=error line ('Exception in ASGI application', exception field) instead of the header plus one count per traceback line; (d) raw level-less lines (tracebacks) disappear, except import-time console lines which contain neither 'error' nor 'exception'.
- terraform/local.tf:19-26 warning filter ("*WARNING*" or level.{0,6}warning): uvicorn 'Invalid HTTP request received.' moves from the plain 'WARNING:' prefix to JSON "level": "warning"; still counted once.
- Blast radius on the SRE Bot Errors alarm (terraform/alarms.tf:1-30, Sum >= var.error_threshold over 60 s): counts fall (no traceback-line inflation, no 5xx access lines); no new source of counts. The Warnings alarm is unchanged.
- bin/deploy-checks.zsh: boot-error and runtime-error checks (:118-124) match level and /Traceback/ over @message, which still contains the JSON exception field; configured_systems_built (:95,113,153) unaffected; nothing greps 'Application startup complete', 'Uvicorn running' or access-line text (rg over bin/, terraform/, .github/, docs/: only docs/runbooks/roll-back-a-deployment.md:87 filter-pattern '?Traceback', which still matches the JSON line). bin/env-checks.zsh: not affected.
- All output now goes to stderr (the root StreamHandler) instead of access lines on stdout; the awslogs driver (terraform/templates/sre-bot.json.tpl:12-19) collects both.
- Manual-check rule (doc-11 open decisions, TASK-177 line): NOT required. No terraform, task definition, IAM, SSM or environment name changes; the Dockerfile is untouched (and even an ENTRYPOINT change would change the image, not the task definition). Merge with a successful deploy and no alarm closes the task. Optional: one 'zsh bin/deploy-checks.zsh post' after the deploy to read the new Non-JSON verdict.

== 5. Test matrix (files; docstrings describe behavior only) ==
Extend app/tests/unit/infrastructure/logging/test_setup.py (TestConfigureLoggingRealCodePath, TestStdlibLoggingBridge; fixture must also save and restore the four uvicorn loggers' handlers/propagate/level, sys.excepthook and logging.captureWarnings state):
 - uvicorn and uvicorn.access handlers cleared, propagate True, level NOTSET after configure_logging; an access-shaped record renders one JSON object with logger=uvicorn.access, level, UTC timestamp ending Z (AC #2, #6).
 - a uvicorn.error ERROR with exc_info renders as exactly one line on a captured stream pair (stdout and stderr via capfd), exception field holds the traceback, no raw trailing lines (AC #5).
 - native event carries logger = caller module, explicit logger name kept; TimeStamper utc explicit (assert the processor's utc attribute) (AC #2).
 - a sensitive-named static field (e.g. session.id) is redacted on a foreign uvicorn record and on a native one by the same chain (AC #3); foreign callsite fields point at the emitting file (decision to keep).
 - pytest branch: after configure_logging under pytest, root level > CRITICAL, uvicorn loggers and sys.excepthook untouched (AC #4); existing redaction and bridge tests stay green.
 - bootstrap then configure_logging: handler replaced, not duplicated; a logger first used after the second call carries the service identity fields.
New app/tests/unit/infrastructure/logging/test_logging_filters_liveness_access.py (AC #8): GET /version 200, GET /health 200 -> DEBUG and absent at INFO, present at DEBUG; boundaries that stay INFO: ?x=1, POST, HEAD, 404/500/204, /versions, /health/, /api/health, malformed args; never dropped (parametrized).
New app/tests/unit/infrastructure/logging/test_logging_setup_uncaught_exception_hook.py (AC #7): hook logs one CRITICAL uncaught_exception JSON line with the traceback in exception; skips reported types; KeyboardInterrupt delegates; no-op under pytest.
Extend app/tests/integration/server/test_server_configuration_phase_logging_render.py (real load_host_configuration against tmp dirs, capfd): missing file, malformed TOML, unreadable file and invalid [logging] each yield exactly one JSON configuration_invalid line (CRITICAL, no value), original exception type raised, no raw traceback text (AC #1, #7).
Extend app/tests/unit/server/test_server.py: create_app logs app_factory_failed and re-raises a TypeError.
New app/tests/integration/server/test_server_uvicorn_launch_logging.py (AC #1, #5, #6, #7; marker integration; sys.executable -m uvicorn --factory in a subprocess, cwd=app, PYTHONPATH set, free port, SIGTERM at the end): (1) with ENVIRONMENT unset, main:create_app exits non-zero with exactly one stderr line, JSON, CRITICAL, no 'Traceback (most recent call last)' outside the exception field; (2) a minimal test factory module under tests/ that calls the real configure_bootstrap_logging/configure_logging and serves /version: every stdout and stderr line parses as JSON, the startup lines, one access line for /version at DEBUG (absent at INFO) and one access line for a 404 probe at INFO; factory raising a plain RuntimeError -> one uncaught_exception line; factory raising TypeError -> app_factory_failed plus uvicorn's 'Error loading ASGI app factory' as JSON. FEASIBILITY: verified by scratch runs. Booting the REAL main:create_app to a serving state is not feasible in a test (needs Slack/Google/AWS configuration; a local run fails slice validation), so the happy path uses the small factory over the real pipeline code and the real uvicorn CLI; each case costs about 1.5 to 2 s (import of main ~1.5 s), 4 cases under 10 s.
Existing bin test test_bin_container_start_contract.py stays valid (ENTRYPOINT untouched).

== 6. AC traceability ==
#1 -> S1,S3,S4; integration config-phase tests + subprocess (1). #2 -> S1; setup tests. #3 -> S1; redaction test. #4 -> S1 pytest branch; pytest-branch test + existing suites. #5 -> S1 (uvicorn routing) + S3; capfd test + subprocess. #6 -> S1; access-line test + subprocess (2). #7 (new) -> S1,S3; hook + subprocess. #8 (new) -> S1,S2; filter tests. #9 (new) -> S6; zsh -n, operational impact section. #10 (new) -> S5; ruff, import contracts, tests.

== 7. Assumptions and doubts (verify before coding) ==
A1 The error metric filter's single field w is the whole raw line (terraform/local.tf comment and alarms.tf); verify with aws logs test-metric-filter on a captured JSON access line, uvicorn.error ERROR line and an import-time console line (read-only; record in notes).
A2 No code reads uvicorn plain-text lines: rg -n 'Uvicorn running|Application startup|Started server' over app/ bin/ terraform/ .github/ docs/ (done once, none; repeat at implementation).
A3 LoggingSettings.model_construct() needs no configuration files (scratch run succeeded); a ConfigurationSlice default must not read files.
A4 An exception thrown out of the uvicorn factory call reaches sys.excepthook with exit code 1 under both python -m uvicorn and the uvicorn console script (verified with a scratch factory).
A5 SIGTERM shutdown of the subprocess produces no ERROR line (a SIGINT shutdown in a scratch run logged a CancelledError traceback from uvicorn/lifespan/on.py:134 as one JSON error line; the test sends SIGTERM and asserts it, and if it fails the case is reported, not suppressed).
A6 cache_logger_on_first_use=True (setup.py:238): a logger first used between the bootstrap and the real call would keep the bootstrap chain; nothing logs in that window on the success path (loader.py and identity.py log nothing, verified with rg); the bootstrap-then-configure test pins it.
A7 TASK-175 only adds configured_systems_built from the core-service build; no overlap with these files.

== 8. Size and gate ==
Production files: 7 (setup.py, filters.py new, host_configuration.py, server.py, formatters.py and __init__.py as deletions, bin/deploy-checks.zsh). Production LOC: about 130 added, about 55 deleted. Subsystems: app logging and server (one), bin script (two). Terraform, Dockerfile, Makefile untouched. No mechanical refactor mixed with behavior; delete-only dead code is small. Gate: PASS (under 400 LOC, 10 files, 2 subsystems). Tests: about 5 new or extended files, not counted.

== 9. Blast radius and rollback ==
If shipped wrong: logs unreadable or missing (a handler cleared with no root handler would silence uvicorn; the subprocess test covers it), a boot that exits without a line (hook error), or the Errors alarm quiet for 5xx. A single git revert restores the previous behavior: no data, config, terraform or entrypoint change, nothing to order. Merging to main deploys; the rollback target is the then-current revision's image tag (bin/deploy-checks.zsh pre prints it, build_and_deploy image_tag input). ECS circuit breaker (TASK-111.16) rolls back a failed boot; the hook keeps exit code 1.

== 10. Implementation gate rule (verbatim for the implementation agent) ==
During implementation run ruff and the targeted test files only. Once every other change is finished, run the full mypy and fix what it finds, then the full pytest on its own: once each, one after the other, never in parallel with each other or other heavy work; rerun one only on a real error. Always from app/, scoped to project code, never against .venv or paths outside the repo:
  cd app && uv run ruff check .
  cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
  cd app && uv run pytest tests --ignore=tests/smoke
Also from app/: make check-import-contracts and make check-settings-key-ownership. Full mypy currently reports 41 pre-existing errors outside the touched files (modules/*, infrastructure/i18n/service.py and resolvers.py, features/incident/scheduling/adapters/google_calendar.py, features/incident/meet/adapters/google_meet.py, integrations/slack/channels.py): judge only the touched files and do not fix those. Do not run tests/smoke. Check ACs one by one as each is verified; stop at In Progress with notes; never Done. Report command and actual output.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Finding 2026-09-15 (production incident, webhook_posting_error on /hook/{id}): each exception log is emitted twice. The JSON event, with the traceback in its "exception" field, is followed by the same traceback as raw lines with no level, one CloudWatch event per line.
- Reproduced with a scratch script (not committed) that calls configure_logging with ENVIRONMENT=production and then structlog.get_logger().exception(...) inside an except. stderr shows the JSON line, then the raw "Traceback (most recent call last): ..." block.
- Mechanism (structlog 25.5.0): structlog.stdlib.BoundLogger.exception sets exc_info=True and proxies to logging.Logger.exception. format_exc_info renders the traceback into the event dict, but the stdlib LogRecord still carries exc_info. The root handler from setup.py:224 `logging.basicConfig(format="%(message)s")` uses a plain logging.Formatter, which appends formatException(record.exc_info) after the message.
- Fix path: ProcessorFormatter.format clears record.exc_info and record.exc_text when keep_exc_info=False, the default. Option (a) therefore removes the duplicate, as long as the structlog chain keeps rendering exceptions in-chain (format_exc_info or dict_tracebacks) and keep_exc_info is left False.
- Operational impact: terraform/local.tf:10-14 error metric filter is a free-text regex (error|exception) that excludes only lines matching level.{0,6}(warning|info). Level-less raw traceback lines, and uvicorn plain-text access lines such as "POST /hook/... 500 Internal Server Error", each count as separate errors, so one failed request inflates the SRE Bot Errors alarm several times. The alarm rework is tracked separately and depends on this task.

2026-10-29: launch paths updated (TASK-111.15.1 deleted app/bin/entry.sh; the image starts uvicorn from the Dockerfile ENTRYPOINT). Queued as doc-11 row 9a.1 (human, 2026-10-29), before TASK-28.4 (row 9a.2); TASK-94 also waits on it.

2026-11-03: plan approved (human): OQ1 option (a) plus the bootstrap pipeline and the uncaught-exception hook (no Dockerfile, Makefile or task definition change; manual-check rule does not apply); OQ2 5xx access lines stay INFO, TASK-94 counts them on fields; OQ3 exact liveness hits at DEBUG in this slice; OQ4 import-time webhook lines and warnings stay plain until TASK-168 (deploy-checks exclusion, removed by 168); OQ5 TypeError guard in create_app kept; OQ6 truncate_large_values and add_environment_info deleted; OQ7 bootstrap always JSON at INFO. AC readings carried by the plan: #1 covers any exception escaping create_app and uvicorn's TypeError message; #3 is tested with a sensitive-named field on a foreign record; #6 is met through the shared factory path (the ENTRYPOINT and Makefile are not edited). ADRs amended 2026-11-03: observability.md (configuration-phase plain lines, exceptions render once, health-check filter placement, 5xx access lines, subprocess check, Migration, Changes), health-checks.md (Checks, Changes). Implement on a branch from main after TASK-175 (#1812, 2a73d00a) deploys.

2026-11-03 implementation (agent). Plan followed S1-S6; docs (S7) were already in the working tree.
Changed: app/infrastructure/logging/setup.py (add_logger_name in the shared chain, TimeStamper utc=True, uvicorn loggers cleared/propagate/NOTSET, captureWarnings, configure_bootstrap_logging, install_uncaught_exception_hook); new app/infrastructure/logging/filters.py (LivenessAccessFilter on uvicorn.access); app/server/configuration/host_configuration.py (bootstrap + hook first, pre-[logging] failures log configuration_invalid once and re-raise unchanged); app/server/server.py (TypeError guard app_factory_failed); formatters.py/__init__.py (truncate_large_values, add_environment_info deleted); bin/deploy-checks.zsh (Non-JSON section retitled, import-time webhook pattern events and warnings excluded, result non_json_lines PASS or WARN (n), comment that TASK-168 removes the exclusion; zsh -n OK). The 'contract' task check was already gone (only 'summary', TASK-156, remains) and no bin test pins deploy-checks, so nothing to delete.
Tests: extended test_setup.py, unit conftest (process_logging_state fixture), test_server.py, test_server_configuration_phase_logging_render.py; new test_logging_filters_liveness_access.py, test_logging_setup_uncaught_exception_hook.py, test_server_uvicorn_launch_logging.py (+ helper tests/integration/server/uvicorn_launch_factories.py). Deleted tests for the removed processors, TestGetModuleLoggerBackwardCompat, and tests/integration/infrastructure/test_logging_integration.py (both tests vacuous).
Deviations: (1) an unreadable file (OSError) is not a ConfigurationError, so load_host_configuration does not log it; the uncaught-exception hook renders it as one uncaught_exception CRITICAL line (tested in-process by invoking the hook, loader untouched). (2) The subprocess cases run with PYTHONWARNINGS=ignore: the real main import emits plain dependency DeprecationWarnings (fastapi/testclient, slowapi) to stderr before create_app, which is the plan's D6 residual 'import-time warnings'; they are present in production too. (3) uvicorn re-raises the captured SIGTERM after shutdown, so the subprocess exit status on SIGTERM is -15; the test accepts 0 or -15 and asserts 'Finished server process'. A5 holds: no error or critical line on SIGTERM shutdown. (4) The [logging] invalid case raises ConfigurationError (ConfigurationSlice wraps pydantic), not ValidationError; both are in the hook's reported tuple.
Gates (from app/): ruff check . -> All checks passed!; ruff format --check . -> 1082 files already formatted; make check-import-contracts -> Contracts: 13 kept, 0 broken; make check-settings-key-ownership -> OK; mypy -> Found 41 errors in 14 files (checked 423 source files), all the pre-existing ones outside touched files; pytest tests --ignore=tests/smoke -> 6010 passed, 44 warnings in 185.67s.
Open for the human: A1 (aws logs test-metric-filter of terraform/local.tf on a captured JSON access line, uvicorn.error ERROR line and an import-time console line) needs AWS and was not run. Task left In Progress.

2026-11-03 test fix: test_malformed_access_arguments_pass_through_unchanged failed when pytest's capture handlers run below WARNING (e.g. -o log_level=INFO). pytest 9 catching_logs attaches its LogCaptureHandler to every non-propagating logger at test entry (_pytest/logging.py:357-366); the fixture set propagate False without restoring it, and the malformed records ('msg' with tuple args) raised TypeError when that handler formatted them. Fixed in the test only: each malformed case carries a message matching its args, and the fixture restores propagate. Logging tests pass at INFO, DEBUG and WARNING; full pytest tests --ignore=tests/smoke: 6010 passed, 44 warnings in 175.21s.

2026-11-03: merged (#1814, 90ed5968, 16:24:40Z); build_and_deploy run 41673920664 success (verify waited out the alarm window), no alarm. Closed: every AC checked, no manual check required; the human sets Done. Rollback target now 90ed5968's image tag. A1 (test-metric-filter) optional, not run.
<!-- SECTION:NOTES:END -->
