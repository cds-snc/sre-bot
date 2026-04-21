"""Shared fixtures for access sync unit tests.

Provides three layers of shared test infrastructure:

1. **Environment isolation** — ``_access_sync_env_isolation`` is an autouse
   fixture that strips every ``ACCESS_*`` process env var before each test.
   This prevents a local ``.env`` file or a CI/CD pipeline environment from
   silently influencing behaviour.  Tests that need a specific value must
   declare it explicitly via ``monkeypatch.setenv``.

2. **Factory fixtures** — ``make_platform_policy``, ``make_runtime_config``, and
   ``make_adapter_capabilities`` each return a callable factory so tests can
   construct canonical objects with safe production-like defaults and override
   only the field(s) relevant to their scenario.

3. **Settings factory** — ``make_sync_settings`` wraps ``AccessSyncSettings``
   (a plain ``BaseModel``) for direct field-override tests.  For env-var
   loading tests, instantiate ``AccessSettings(_env_file=None).sync`` directly.

Pattern::

    def test_something(make_runtime_config, make_adapter_capabilities):
        config = make_runtime_config()                    # safe defaults
        caps   = make_adapter_capabilities(supports_disable=False)  # edge case
"""

import pytest

from packages.access.common.config import AccessRuntimeConfig, PlatformPolicy
from packages.access.common.settings import AccessSyncSettings
from packages.access.sync.policies import AdapterCapabilities

# env vars managed by this package — all are stripped before every test
_ACCESS_SYNC_ENV_KEYS = [
    "ACCESS_SYNC_ENABLED",
    "ACCESS_SYNC_RECONCILIATION_ENABLED",
    "ACCESS_SYNC_RECONCILIATION_SCHEDULE",
    "ACCESS_SYNC_JOB_TTL_SECONDS",
    "ACCESS_SYNC_LOCK_STALE_SECONDS",
    "ACCESS_CONFIG_SOURCE",
    "ACCESS_CONFIG_REF",
    "ACCESS_CONFIG_REFRESH_SECONDS",
    "ACCESS_REQUESTS_ENABLED",
    "ACCESS_CATALOG_ENABLED",
    # EnvConfigLoader vars
    "ACCESS_SYNC_DIR_PREFIX",
    "ACCESS_SYNC_DIR_SEPARATOR",
    "ACCESS_SYNC_PLATFORMS_JSON",
]


@pytest.fixture(autouse=True)
def _access_sync_env_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip all ACCESS_SYNC_* env vars before every unit test in this package.

    Tests that need a specific value must set it explicitly::

        def test_flag_enabled(make_sync_settings, monkeypatch):
            monkeypatch.setenv("ACCESS_SYNC_ENABLED", "true")
            settings = make_sync_settings()
            assert settings.enabled is True
    """
    for key in _ACCESS_SYNC_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Settings factory
# ---------------------------------------------------------------------------


@pytest.fixture
def make_sync_settings():
    """Factory fixture for ``AccessSyncSettings``.

    ``AccessSyncSettings`` is a plain ``BaseModel`` — no env file reading.
    Pass field overrides directly as keyword arguments.

    To test env-var loading, instantiate ``AccessSettings(_env_file=None)``
    directly in the test after calling ``monkeypatch.setenv``.

    Usage::

        def test_defaults(make_sync_settings):
            settings = make_sync_settings()
            assert settings.enabled is False

        def test_ttl_override(make_sync_settings):
            settings = make_sync_settings(job_ttl_seconds=3600)
            assert settings.job_ttl_seconds == 3600
    """

    def _make(**overrides: object) -> AccessSyncSettings:
        return AccessSyncSettings(**overrides)

    return _make


# ---------------------------------------------------------------------------
# Domain model factories
# ---------------------------------------------------------------------------


@pytest.fixture
def make_platform_policy():
    """Factory fixture for ``PlatformPolicy`` with safe production-like defaults.

    Override only the fields relevant to the scenario under test::

        def test_disable_mode(make_platform_policy):
            policy = make_platform_policy(authn_removal_mode="disable")
            assert policy.authn_removal_mode == "disable"
    """

    def _make(
        authn_token: str = "authn",
        authn_removal_mode: str = "delete",
        adapter_type: str = "fake",
        mode_overrides: dict | None = None,
    ) -> PlatformPolicy:
        return PlatformPolicy(
            authn_token=authn_token,
            authn_removal_mode=authn_removal_mode,
            adapter_type=adapter_type,
            mode_overrides=mode_overrides or {},
        )

    return _make


@pytest.fixture
def make_runtime_config(make_platform_policy):
    """Factory fixture for ``AccessRuntimeConfig`` with safe production-like defaults.

    Default: ``dir_prefix='sg'``, ``dir_separator='-'``, single ``'aws'``
    platform.  Pass ``platforms`` to override the full platforms map; otherwise
    pass keyword arguments forwarded to ``make_platform_policy`` for the default
    platform::

        def test_group_prefix(make_runtime_config):
            config = make_runtime_config()
            assert config.group_prefix("aws") == "sg-aws-"

        def test_ephemeral_override(make_runtime_config):
            config = make_runtime_config(
                mode_overrides={"breakglass-admin": "ephemeral"}
            )

        def test_multi_platform(make_runtime_config, make_platform_policy):
            config = make_runtime_config(
                platforms={
                    "aws": make_platform_policy(),
                    "gcp": make_platform_policy(authn_removal_mode="disable"),
                }
            )
    """

    def _make(
        platform: str = "aws",
        dir_prefix: str = "sg",
        dir_separator: str = "-",
        platforms: dict | None = None,
        **policy_kwargs: object,
    ) -> AccessRuntimeConfig:
        if platforms is None:
            platforms = {platform: make_platform_policy(**policy_kwargs)}  # type: ignore[arg-type]
        return AccessRuntimeConfig(
            dir_prefix=dir_prefix,
            dir_separator=dir_separator,
            platforms=platforms,
        )

    return _make


@pytest.fixture
def make_adapter_capabilities():
    """Factory fixture for ``AdapterCapabilities`` with all features enabled by default.

    Override only the capabilities that differ from the scenario under test::

        def test_lifecycle_delta_skipped(make_adapter_capabilities):
            caps = make_adapter_capabilities(supports_bulk_user_delta=False)
            assert not caps.supports_bulk_user_delta
    """

    def _make(
        supports_disable: bool = True,
        supports_delete: bool = True,
        supports_bulk_user_delta: bool = True,
        supported_entitlement_types: set | None = None,
    ) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=supports_disable,
            supports_delete=supports_delete,
            supports_bulk_user_delta=supports_bulk_user_delta,
            supported_entitlement_types=supported_entitlement_types or {"group"},
        )

    return _make
