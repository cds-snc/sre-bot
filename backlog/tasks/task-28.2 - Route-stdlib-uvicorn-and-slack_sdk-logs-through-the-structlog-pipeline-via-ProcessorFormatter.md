---
id: TASK-28.2
title: >-
  Route uvicorn and pre-configuration lines through the structlog pipeline;
  logger name and explicit UTC on every line
status: To Do
assignee: []
created_date: 2026-09-15 14:08
updated_date: '2026-10-29T17:25:00Z'
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
- [ ] #1 uvicorn's app-factory error and failures before [logging] loads (missing ENVIRONMENT, unreadable configuration file) render in the shape decided at planning, with no raw multi-line traceback in production, verified by a test
- [ ] #2 Every rendered line, structlog-native or foreign, carries a UTC ISO-8601 timestamp (TimeStamper utc=True set explicitly) and a logger name
- [ ] #3 Sensitive keys on foreign records, uvicorn's included, are redacted by the same mask_sensitive_data processor, verified by a test
- [ ] #4 Logging stays fully suppressed under pytest, and existing redaction and stdlib-bridge pipeline tests stay green
- [ ] #5 In production mode, a log.exception call (or any call with exc_info=True) emits exactly one line: a JSON object whose exception field holds the traceback. No raw traceback lines follow on stdout or stderr, verified by a test that captures both streams
- [ ] #6 uvicorn and uvicorn.access records render through the pipeline for the documented launch paths (the Dockerfile ENTRYPOINT and the app/Makefile targets, uvicorn --factory main:create_app); a uvicorn access line renders as one JSON object in production mode, verified by a test
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Finding 2026-09-15 (production incident, webhook_posting_error on /hook/{id}): each exception log is emitted twice. The JSON event, with the traceback in its "exception" field, is followed by the same traceback as raw lines with no level, one CloudWatch event per line.
- Reproduced with a scratch script (not committed) that calls configure_logging with ENVIRONMENT=production and then structlog.get_logger().exception(...) inside an except. stderr shows the JSON line, then the raw "Traceback (most recent call last): ..." block.
- Mechanism (structlog 25.5.0): structlog.stdlib.BoundLogger.exception sets exc_info=True and proxies to logging.Logger.exception. format_exc_info renders the traceback into the event dict, but the stdlib LogRecord still carries exc_info. The root handler from setup.py:224 `logging.basicConfig(format="%(message)s")` uses a plain logging.Formatter, which appends formatException(record.exc_info) after the message.
- Fix path: ProcessorFormatter.format clears record.exc_info and record.exc_text when keep_exc_info=False, the default. Option (a) therefore removes the duplicate, as long as the structlog chain keeps rendering exceptions in-chain (format_exc_info or dict_tracebacks) and keep_exc_info is left False.
- Operational impact: terraform/local.tf:10-14 error metric filter is a free-text regex (error|exception) that excludes only lines matching level.{0,6}(warning|info). Level-less raw traceback lines, and uvicorn plain-text access lines such as "POST /hook/... 500 Internal Server Error", each count as separate errors, so one failed request inflates the SRE Bot Errors alarm several times. The alarm rework is tracked separately and depends on this task.

2026-10-29: launch paths updated (TASK-111.15.1 deleted app/bin/entry.sh; the image starts uvicorn from the Dockerfile ENTRYPOINT). Queued as doc-11 row 9a.1 (human, 2026-10-29), before TASK-28.4 (row 9a.2); TASK-94 also waits on it.
<!-- SECTION:NOTES:END -->
