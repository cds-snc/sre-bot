"""Unit tests for the service identity in server.configuration.identity.

The identity is built from the deployment identity slice (environment, git_sha) and the
installed distribution's metadata. IdentitySettings is constructed directly, so no
environment variable or file is read. Assertions read the dotted OpenTelemetry resource
names the logging pipeline carries on every record.
"""

import re
from importlib.metadata import metadata
from uuid import UUID

import pytest

from server.configuration.identity import IdentitySettings, build_service_identity

pytestmark = pytest.mark.unit


def _identity(**overrides: str) -> IdentitySettings:
    return IdentitySettings(**{"environment": "ci", "git_sha": "abc123", **overrides})  # type: ignore[arg-type]


def test_log_fields_use_the_opentelemetry_resource_names() -> None:
    """Exactly the four resource attributes, flat and dotted."""
    fields = build_service_identity(_identity()).log_fields()

    assert set(fields) == {"service.name", "service.version", "service.instance.id", "deployment.environment.name"}


def test_service_name_is_the_distribution_name() -> None:
    """The name is the installed project's metadata name, with no setting to drift from it."""
    fields = build_service_identity(_identity()).log_fields()

    assert fields["service.name"] == metadata("sre-bot")["Name"]


def test_version_and_environment_come_from_the_identity_slice() -> None:
    """service.version is the image's git_sha and the environment name is the selected environment."""
    fields = build_service_identity(_identity(environment="production", git_sha="deadbeef")).log_fields()

    assert fields["service.version"] == "deadbeef"
    assert fields["deployment.environment.name"] == "production"


def test_instance_id_is_a_random_uuid_that_differs_per_build() -> None:
    """Each process builds its own version 4 UUID, so replicas of one image are told apart."""
    first = build_service_identity(_identity()).log_fields()["service.instance.id"]
    second = build_service_identity(_identity()).log_fields()["service.instance.id"]

    assert UUID(first).version == 4
    assert first != second
    assert re.fullmatch(r"[0-9a-f-]{36}", first)
