"""App factories the uvicorn launch test starts in a subprocess with ``uvicorn --factory``.

Each factory runs the production logging code a real boot runs. ``serving`` serves
/version over the real pipeline; ``runtime_error`` and ``type_error`` fail inside
the real create_app after the configuration phase's logging setup.
"""

import os

from fastapi import FastAPI

from infrastructure.logging.settings import LoggingSettings
from infrastructure.logging.setup import (
    configure_bootstrap_logging,
    configure_logging,
    install_uncaught_exception_hook,
)


def serving() -> FastAPI:
    """Configure the production pipeline at the level named by LAUNCH_LOG_LEVEL and serve /version."""
    configure_bootstrap_logging()
    install_uncaught_exception_hook(reported=())
    configure_logging(
        "production",
        LoggingSettings.model_construct(),
        log_level=os.environ.get("LAUNCH_LOG_LEVEL", "INFO"),
    )
    app = FastAPI()

    @app.get("/version")
    def version() -> dict[str, str]:
        return {"version": "test"}

    return app


def _failing_create_app(error: Exception) -> FastAPI:
    from server import server  # noqa: PLC0415 - imported only when a failing factory runs

    def failing_configuration() -> None:
        configure_bootstrap_logging()
        install_uncaught_exception_hook(reported=())
        raise error

    server.load_host_configuration = failing_configuration  # type: ignore[assignment]
    return server.create_app()


def runtime_error() -> FastAPI:
    """Fail the real create_app with a RuntimeError, which uvicorn does not catch."""
    return _failing_create_app(RuntimeError("factory exploded"))


def type_error() -> FastAPI:
    """Fail the real create_app with a TypeError, which uvicorn catches and reports by message only."""
    return _failing_create_app(TypeError("factory argument"))
