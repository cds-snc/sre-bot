"""Integration tests: every line of a real ``uvicorn --factory`` launch is one JSON object.

Each case starts uvicorn from the command line in a subprocess, the way the image does,
with an explicit environment (the test run blanks variables through pytest-env). The
serving cases use a small factory over the real logging pipeline, because booting the
real application needs Slack, Google and AWS configuration; the failure cases run the
real create_app. Processes are stopped with SIGTERM and both streams are parsed.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

APP_DIR = Path(__file__).resolve().parents[3]
FACTORIES = "tests.integration.server.uvicorn_launch_factories"
BOOT_TIMEOUT_SECONDS = 30


def _environment(**overrides: str) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key != "ENVIRONMENT"}
    env.update({"PYTHONPATH": str(APP_DIR), "PYTHONUNBUFFERED": "1", **overrides})
    return env


def _command(target: str, port: int) -> list[str]:
    return [sys.executable, "-m", "uvicorn", "--factory", target, "--host", "127.0.0.1", "--port", str(port)]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _json_lines(text: str) -> list[dict[str, Any]]:
    """Parse every non-empty line as JSON; a plain-text line fails the test with the line shown."""
    events = []
    for line in text.splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _run_to_exit(target: str, **overrides: str) -> subprocess.CompletedProcess[str]:
    """Run uvicorn to its exit; dependency deprecation warnings raised while the app imports are plain
    interpreter output that precedes the factory, so they are silenced to isolate the factory's own output."""
    overrides.setdefault("PYTHONWARNINGS", "ignore")
    return subprocess.run(  # noqa: S603
        _command(target, _free_port()),
        cwd=APP_DIR,
        env=_environment(**overrides),
        capture_output=True,
        text=True,
        timeout=BOOT_TIMEOUT_SECONDS,
        check=False,
    )


@contextmanager
def _serving(log_level: str) -> Iterator[tuple[int, subprocess.Popen[str]]]:
    port = _free_port()
    process = subprocess.Popen(  # noqa: S603
        _command(f"{FACTORIES}:serving", port),
        cwd=APP_DIR,
        env=_environment(LAUNCH_LOG_LEVEL=log_level),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/version", timeout=2):
                    break
            except OSError:
                assert process.poll() is None, "uvicorn exited before it served"
                assert time.monotonic() < deadline, "uvicorn did not serve in time"
                time.sleep(0.1)
        yield port, process
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)


def _probe_404(port: int) -> None:
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/missing", timeout=5)


def _stop(process: subprocess.Popen[str]) -> tuple[list[dict[str, Any]], int]:
    process.send_signal(signal.SIGTERM)
    out, err = process.communicate(timeout=BOOT_TIMEOUT_SECONDS)
    return _json_lines(out) + _json_lines(err), process.returncode


def _access_lines(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["logger"] == "uvicorn.access"]


def test_missing_environment_is_one_critical_json_line_on_stderr_and_a_non_zero_exit() -> None:
    """The real create_app without ENVIRONMENT prints a single CRITICAL JSON line on stderr and no traceback."""
    result = _run_to_exit("main:create_app")

    assert result.returncode != 0
    (event,) = _json_lines(result.stderr)
    assert event["event"] == "configuration_invalid"
    assert event["level"] == "critical"
    assert "Traceback (most recent call last)" not in result.stderr


def test_serving_at_info_renders_every_line_as_json_and_keeps_liveness_out() -> None:
    """Startup, a 404 access line and shutdown are JSON; the /version probe is absent at INFO; SIGTERM logs no error."""
    with _serving("INFO") as (port, process):
        _probe_404(port)
        events, returncode = _stop(process)

    # uvicorn re-raises the captured SIGTERM once it has shut down, so the status is the signal.
    assert returncode in {0, -signal.SIGTERM}
    assert any(event["event"].startswith("Finished server process") for event in events)
    access = _access_lines(events)
    assert [(line["level"], "/missing" in line["event"]) for line in access] == [("info", True)]
    assert all("/version" not in line["event"] for line in access)
    assert any(event["event"].startswith("Uvicorn running") for event in events)
    assert all(event["timestamp"].endswith("Z") for event in events)
    assert [event for event in events if event["level"] in {"error", "critical"}] == []


def test_serving_at_debug_emits_the_liveness_access_line_at_debug() -> None:
    """With DEBUG enabled the /version probe is emitted as a DEBUG access line instead of being dropped."""
    with _serving("DEBUG") as (_port, process):
        events, _returncode = _stop(process)

    liveness = [line for line in _access_lines(events) if "GET /version" in line["event"]]
    assert liveness
    assert {line["level"] for line in liveness} == {"debug"}


def test_a_runtime_error_in_the_factory_is_one_uncaught_exception_line() -> None:
    """An exception uvicorn does not catch renders as one CRITICAL JSON line holding the traceback, exiting non-zero."""
    result = _run_to_exit(f"{FACTORIES}:runtime_error")

    assert result.returncode != 0
    (event,) = _json_lines(result.stderr)
    assert event["event"] == "uncaught_exception"
    assert event["level"] == "critical"
    assert "RuntimeError: factory exploded" in event["exception"]
    assert result.stderr.count("Traceback (most recent call last)") == 1


def test_a_type_error_in_the_factory_logs_app_factory_failed_and_uvicorns_message_as_json() -> None:
    """A TypeError is logged with its traceback by the factory, then uvicorn's own message renders as JSON."""
    result = _run_to_exit(f"{FACTORIES}:type_error")

    assert result.returncode != 0
    events = _json_lines(result.stderr)
    assert [event["event"] for event in events][0] == "app_factory_failed"
    assert events[0]["level"] == "critical"
    assert "TypeError: factory argument" in events[0]["exception"]
    uvicorn_lines = [event for event in events if event["logger"] == "uvicorn.error"]
    assert any("Error loading ASGI app factory" in line["event"] for line in uvicorn_lines)
