---
id: TASK-28.2
title: >-
  Route stdlib, uvicorn and slack_sdk logs through the structlog pipeline via
  ProcessorFormatter
status: To Do
assignee: []
created_date: '2026-09-15 14:08'
updated_date: '2026-09-15 19:37'
labels:
  - infrastructure
  - phase-4
  - observability
milestone: m-4
dependencies: []
references:
  - decisions/observability.md
  - decisions/health-checks.md
  - app/infrastructure/logging/setup.py
  - app/server/lifespan.py
  - app/bin/entry.sh
  - app/Makefile
  - app/tests/unit/infrastructure/logging/test_setup.py
parent_task_id: TASK-28
priority: high
ordinal: 208000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Step 4 of TASK-28, carved out as its own slice (TASK-28 bundles four independent concerns and exceeds the single-PR size gate). Research recorded 2026-09-15 so planning does not restart from scratch; re-verify line numbers and versions before planning.

OBSERVED (local `make dev`, 2026-09-15)
    2026-09-15T13:22:58.205448Z [info     ] slack_provider_start_skipped   code.file.path=server/lifespan.py ...   <- structlog ConsoleRenderer
    INFO:     Application startup complete.                                   <- uvicorn's own formatter
    A new session has been established (session id: ...)                     <- bare stdlib record, no timestamp/level/logger
    INFO:     127.0.0.1:42196 - "HEAD / HTTP/1.1" 405 Method Not Allowed      <- uvicorn.access
    WARNING:  Invalid HTTP request received.                                  <- uvicorn.error
Three different shapes in one stream. Production runs the same launch path (bin/entry.sh:7 `exec uvicorn main:server_app --host=0.0.0.0`), so CloudWatch gets structlog JSON interleaved with plain-text uvicorn/stdlib lines. That breaks JSONL parsing and violates decisions/observability.md:16 ("one shape for the whole stream"). The ADR already names the gap at :12 and :39.

ROOT CAUSES (verified)
1. infrastructure/logging/setup.py:222-227: `logging.basicConfig(format="%(message)s", level=...)` installs a plain root StreamHandler with no structlog ProcessorFormatter or foreign_pre_chain. Any stdlib logger that propagates to root prints its raw message. Reproduced 2026-09-15: after configure_logging, `structlog.get_logger().info(...)` renders fully, while `logging.getLogger("slack_sdk.socket_mode.builtin.client").info(...)` prints only the message text. basicConfig without force=True is also a no-op if root already has handlers.
2. slack_sdk: slack_sdk/socket_mode/builtin/client.py:107 `logging.getLogger(__name__)` propagates to root, hence the bare "A new session has been established" and "Starting to receive messages" lines. slack_bolt behaves the same way.
3. uvicorn 0.41.0 default LOGGING_CONFIG (introspected): `uvicorn` has handler "default" with propagate=False; `uvicorn.error` has level INFO and propagates to `uvicorn`; `uvicorn.access` has handler "access" with propagate=False. Formatters: default "%(levelprefix)s %(message)s", access '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'. uvicorn is launched from the CLI with no --log-config: app/Makefile:4 and :12 (`make dev` / debug, `--reload`), app/Makefile:110, app/bin/entry.sh:7. uvicorn therefore configures its loggers BEFORE the app imports. configure_logging only runs inside lifespan (server/lifespan.py:236 via _get_logger_from_app), after "Started server process" / "Waiting for application startup" are already emitted. The only caller of configure_logging is lifespan.py:65.

OPTIONS FOR THE PLANNER (not decided; confirm against current structlog and uvicorn docs via web search)
a. In configure_logging: install one root handler using structlog.stdlib.ProcessorFormatter (foreign_pre_chain = the shared base processors, final renderer ConsoleRenderer or JSONRenderer). Then clear the handlers on `uvicorn`/`uvicorn.access` and set propagate=True. Smallest diff; misses the few uvicorn lines emitted before lifespan runs.
b. Pass a logging config to uvicorn (`--log-config` file in entry.sh and Makefile, or `log_config=None` when started programmatically) so uvicorn never installs its own handlers. Covers every line; touches the deploy entrypoint and Dockerfile/ECS behaviour, so it may warrant its own slice.
c. Configure at import time in main.py: conflicts with the no-import-time-side-effects rule (CLAUDE.md, decisions/plugins.md). Avoid.
The structlog chain also needs: `structlog.stdlib.ProcessorFormatter.wrap_for_formatter` as the last structlog processor, `ProcessorFormatter.remove_processors_meta`, and `structlog.stdlib.add_logger_name` (absent today, required by the ADR). Callsite parameters on foreign records resolve to the logging module, not the caller; decide whether to drop them for foreign records.

ALREADY TRUE (the TASK-28 description and ADR are stale here)
- Timestamps are already UTC: structlog 25.5.0 `TimeStamper.__init__(fmt=None, utc=True, ...)` defaults to UTC, and setup.py:120 uses TimeStamper(fmt="iso"). Output ends in `Z`. Update the "local-time timestamps" item in decisions/observability.md:39 and the TASK-28 description when this lands (architecture agent).
- Redaction is installed (TASK-8): setup.py:136 mask_sensitive_data. Make sure foreign records pass through it too (foreign_pre_chain).

RELATED ADR NUANCE (TASK-28 comment #1, decisions/observability.md:18)
Once uvicorn.access goes through the pipeline, add a narrow logging.Filter that classifies EXACT liveness hits (GET, path in {/version, /health}, status 200, no query string) as DEBUG or event_type=healthcheck. Never drop them; anything else stays INFO+. Probe sources: ALB target group GET /version (terraform/alb.tf:10-17), Route53 HTTPS /version (terraform/route53.tf:21-27), Dockerfile HEALTHCHECK GET /health (Dockerfile:75). The planner decides whether this fits the slice or becomes a follow-up (size gate).

EXISTING TESTS (starting points)
- tests/unit/infrastructure/logging/test_setup.py: class TestConfigureLoggingRealCodePath (:202-246) monkeypatches _is_test_environment to run the real production and dev pipelines, including redaction through JSON. Extend it for foreign-record and uvicorn-access rendering. Nothing currently pins the basicConfig format, so no test needs rewriting for that.
- tests/unit/infrastructure/test_logging.py largely duplicates test_setup.py (legacy). Touch it minimally.
- Test-mode suppression branch setup.py:172-196 (root level CRITICAL+1) must keep silencing everything under pytest.

NOT A BUG, DO NOT CHASE (human decision 2026-09-15: leave as is)
Local-dev `WARNING: Invalid HTTP request received.` bursts and `HEAD / HTTP/1.1 405`: all from 127.0.0.1 through VS Code port forwarding of 8000 (devcontainer.json has no portsAttributes). Reproduced 2026-09-15 with a throwaway uvicorn: a TLS ClientHello sent to the plain-HTTP port produces exactly that warning, consistent with a browser trying https:// before falling back to the `GET / 200` seen afterwards. HEAD gets 405 because the landing route is GET-only (api/routes/landing.py:441). Production can't see it: the ALB terminates TLS on 443 and forwards plain HTTP to 8000, and every health check is GET. Do not suppress: the ADR requires probing traffic to stay visible. After this slice those lines render through the pipeline like everything else.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A record from a stdlib logger (e.g. slack_sdk.socket_mode.builtin.client) renders through the same processor chain as structlog events, with timestamp, level and logger name: ConsoleRenderer in non-production, one JSON object per line in production
- [ ] #2 uvicorn and uvicorn.access records render through the pipeline for the documented launch paths (app/Makefile dev targets and app/bin/entry.sh); a uvicorn access line renders as JSON in production mode, verified by a test
- [ ] #3 Every rendered line, structlog-native or foreign, carries a UTC ISO-8601 timestamp and a logger name
- [ ] #4 Sensitive keys on foreign records are redacted by the same mask_sensitive_data processor, verified by a test
- [ ] #5 Logging stays fully suppressed under pytest, and existing redaction pipeline tests stay green
- [ ] #6 In production mode, a log.exception call (or any call with exc_info=True) emits exactly one line: a JSON object whose exception field holds the traceback. No raw traceback lines follow on stdout or stderr, verified by a test that captures both streams
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Finding 2026-09-15 (production incident, webhook_posting_error on /hook/{id}): each exception log is emitted twice. The JSON event, with the traceback in its "exception" field, is followed by the same traceback as raw lines with no level, one CloudWatch event per line.
- Reproduced with a scratch script (not committed) that calls configure_logging with ENVIRONMENT=production and then structlog.get_logger().exception(...) inside an except. stderr shows the JSON line, then the raw "Traceback (most recent call last): ..." block.
- Mechanism (structlog 25.5.0): structlog.stdlib.BoundLogger.exception sets exc_info=True and proxies to logging.Logger.exception. format_exc_info renders the traceback into the event dict, but the stdlib LogRecord still carries exc_info. The root handler from setup.py:224 `logging.basicConfig(format="%(message)s")` uses a plain logging.Formatter, which appends formatException(record.exc_info) after the message.
- Fix path: ProcessorFormatter.format clears record.exc_info and record.exc_text when keep_exc_info=False, the default. Option (a) therefore removes the duplicate, as long as the structlog chain keeps rendering exceptions in-chain (format_exc_info or dict_tracebacks) and keep_exc_info is left False.
- Operational impact: terraform/local.tf:10-14 error metric filter is a free-text regex (error|exception) that excludes only lines matching level.{0,6}(warning|info). Level-less raw traceback lines, and uvicorn plain-text access lines such as "POST /hook/... 500 Internal Server Error", each count as separate errors, so one failed request inflates the SRE Bot Errors alarm several times. The alarm rework is tracked separately and depends on this task.
<!-- SECTION:NOTES:END -->
