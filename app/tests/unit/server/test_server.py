"""Unit tests for server.server module."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from contracts.configuration import ConfigurationError, host_info, uninstall_configuration_files, uninstall_host_info
from infrastructure.security.settings import SecuritySettings, get_security_settings
from server import server
from server.configuration import CONFIG_DIR, get_identity_settings, get_server_settings, load_configuration_files


@pytest.fixture
def app() -> FastAPI:
    """The application built by the factory under the ci configuration files."""
    return server.create_app()


@pytest.mark.unit
def test_create_app_returns_fastapi_app(app):
    """The factory returns a FastAPI app with routes, middleware and overrides."""
    assert isinstance(app, FastAPI)
    assert len(app.routes) > 0
    assert len(app.user_middleware) > 0
    assert hasattr(app, "dependency_overrides")


@pytest.mark.unit
def test_create_app_installs_files_and_host_info():
    """The configuration phase runs in the factory: files are installed and HostInfo is readable."""
    uninstall_configuration_files()
    uninstall_host_info()

    server.create_app()

    info = host_info()
    assert info.environment == "ci"
    assert info.public_base_url == "http://127.0.0.1:8000"


@pytest.mark.unit
def test_create_app_twice_gives_independent_apps():
    """Each call builds its own app; nothing is shared through a module-level app."""
    assert server.create_app() is not server.create_app()


@pytest.mark.unit
def test_cors_middleware_configured(app):
    """CORS middleware should use the security slice's explicit non-wildcard lists and no credentials mode."""
    security_settings = get_security_settings()
    cors_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_credentials"] is False
    assert cors_middleware.kwargs["allow_origins"] == security_settings.cors_allowed_origins
    assert cors_middleware.kwargs["allow_methods"] == security_settings.cors_allowed_methods
    assert cors_middleware.kwargs["allow_headers"] == security_settings.cors_allowed_headers
    assert "*" not in cors_middleware.kwargs["allow_origins"]
    assert "*" not in cors_middleware.kwargs["allow_methods"]
    assert "*" not in cors_middleware.kwargs["allow_headers"]


@pytest.mark.unit
def test_cors_middleware_uses_configured_origin_list(monkeypatch):
    """The app factory preserves the exact configured origin allow-list of the security slice."""
    configured_origins = ["https://frontend.example"]
    monkeypatch.setattr(
        "server.configuration.host_configuration.get_security_settings",
        lambda: SecuritySettings(
            _env_file=None,
            CORS_ALLOWED_ORIGINS=configured_origins,
            CORS_ALLOWED_METHODS=["GET", "POST"],
            CORS_ALLOWED_HEADERS=["Authorization", "Content-Type"],
        ),
    )

    built = server.create_app()
    cors_middleware = next(
        (m for m in built.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )

    assert cors_middleware is not None
    assert cors_middleware.kwargs["allow_origins"] == configured_origins


@pytest.mark.unit
def test_cors_preflight_from_allowed_origin_grants_no_credentials(monkeypatch):
    """A preflight from an allowed origin is answered without Access-Control-Allow-Credentials.

    The factory is given a security slice allowing one origin; the preflight is
    answered by the CORS middleware, so the lifespan never runs.
    """
    origin = "https://frontend.example"
    monkeypatch.setattr(
        "server.configuration.host_configuration.get_security_settings",
        lambda: SecuritySettings(_env_file=None, CORS_ALLOWED_ORIGINS=[origin]),
    )

    response = TestClient(server.create_app()).options(
        "/version",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers
    assert "PUT" not in response.headers["access-control-allow-methods"]


@pytest.mark.unit
def test_max_body_size_middleware_uses_server_slice_limit(app):
    """Webhook ingress is capped at the [server] slice's webhook_max_body_bytes."""
    max_body_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "MaxBodySizeMiddleware"),
        None,
    )
    assert max_body_middleware is not None
    assert max_body_middleware.kwargs["max_bytes"] == 262_144


@pytest.mark.unit
def test_max_body_size_limit_can_be_overridden_from_environment(monkeypatch):
    """SERVER__WEBHOOK_MAX_BODY_BYTES overrides the file value for the middleware."""
    monkeypatch.setenv("SERVER__WEBHOOK_MAX_BODY_BYTES", "1024")
    get_server_settings.cache_clear()
    try:
        built = server.create_app()
    finally:
        get_server_settings.cache_clear()

    max_body_middleware = next(m for m in built.user_middleware if m.cls.__name__ == "MaxBodySizeMiddleware")
    assert max_body_middleware.kwargs["max_bytes"] == 1024


@pytest.mark.unit
def test_create_app_fails_before_building_on_invalid_environment(monkeypatch):
    """An unknown ENVIRONMENT stops the factory, so no app with half-loaded configuration exists."""
    monkeypatch.setenv("ENVIRONMENT", "rollback-rehearsal")
    get_identity_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="environment"):
            server.create_app()
    finally:
        get_identity_settings.cache_clear()


@pytest.mark.unit
def test_create_app_fails_on_unknown_server_key(monkeypatch, tmp_path):
    """A key outside the [server] table is rejected at boot, naming the key."""
    for name in ("base.toml", "ci.toml"):
        (tmp_path / name).write_text((CONFIG_DIR / name).read_text())
    with (tmp_path / "ci.toml").open("a") as file:
        file.write('\n[server]\nnot_a_key = "x"\n')
    monkeypatch.setattr(
        "server.configuration.host_configuration.load_configuration_files",
        lambda environment, directory=None: load_configuration_files(environment, tmp_path),
    )
    get_server_settings.cache_clear()
    try:
        with pytest.raises(ConfigurationError, match="not_a_key"):
            server.create_app()
    finally:
        get_server_settings.cache_clear()


@pytest.mark.unit
def test_api_router_included(app):
    """The API router is included in the app."""
    assert len(app.routes) > 0


@pytest.mark.unit
def test_configuration_error_exception_exists():
    """Test that ConfigurationError exception is defined."""
    assert hasattr(server, "ConfigurationError")
    assert issubclass(server.ConfigurationError, Exception)


@pytest.mark.unit
def test_sns_message_validator_initialized():
    """Test that SNS message validator is initialized."""
    assert server.sns_message_validator is not None
