"""Boot the real application on the ci configuration and print every startup log record as JSON.

Run as a subprocess by test_server_boot_info_event_budget: pytest suppresses logging in its own
process, so the pipeline is only observable in a fresh interpreter. The configure_logging name
the configuration phase calls is wrapped to add a capturing root handler once the pipeline is
installed. The rows are printed on one line after a marker so the application's own console
output cannot be confused with them.
"""

import json
import logging

from fastapi.testclient import TestClient

from server.configuration import host_configuration
from server.server import create_app

MARKER = "BOOT_PROBE_ROWS="


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.rows: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.msg
        if isinstance(message, dict):
            row: dict[str, object] = {"level": record.levelname, "logger": record.name, "event": str(message.get("event"))}
            row["phase"] = message.get("phase")
            if message.get("event") == "configuration_summary":
                row["slices"] = message.get("slices")
        else:
            row = {"level": record.levelname, "logger": record.name, "event": record.getMessage(), "phase": None}
        self.rows.append(row)


def main() -> None:
    capture = _Capture()
    original = host_configuration.configure_logging

    def configure_and_capture(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        logging.getLogger().addHandler(capture)
        return result

    host_configuration.configure_logging = configure_and_capture  # type: ignore[assignment]
    with TestClient(create_app()):
        rows = list(capture.rows)
    print(MARKER + json.dumps(rows))


if __name__ == "__main__":
    main()
