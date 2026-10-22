"""Build the app lifespan the way create_app does: configuration phase first, then the lifespan bound to it."""

from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI

from server.configuration import load_host_configuration
from server.lifespan import build_lifespan


def lifespan(app: FastAPI) -> AbstractAsyncContextManager[dict[str, object]]:
    """Run the configuration phase under the installed files, then return the lifespan for ``app``.

    The phase runs when this is called, so an invalid slice raises before the
    lifespan context is entered, as it does when create_app builds the app.
    """
    return build_lifespan(load_host_configuration())(app)
