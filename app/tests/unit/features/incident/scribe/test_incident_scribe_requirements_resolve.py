"""Unit tests for incident.scribe's ``register_requirements`` hookimpl.

``get_openai_settings`` is patched where the scribe requirements adapter reads it with a stand-in
whose ``tenant`` is set or not, so no configuration file is read. Scribe has no
fallback without text generation, so a missing [openai.tenant] must raise the
required-dependency error naming it; a configured tenant must pass silently.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from contracts.plugins.requirements import RequiredDependencyError
from features.incident import scribe
from features.incident.scribe.adapters import requirements

pytestmark = pytest.mark.unit


def test_scribe_requirements_raise_naming_openai_tenant_when_it_is_not_configured() -> None:
    with (
        patch.object(requirements, "get_openai_settings", return_value=SimpleNamespace(tenant=None)),
        pytest.raises(RequiredDependencyError) as raised,
    ):
        scribe.register_requirements()

    assert raised.value.setting == "openai.tenant"


def test_scribe_requirements_pass_when_the_openai_tenant_is_configured() -> None:
    with patch.object(requirements, "get_openai_settings", return_value=SimpleNamespace(tenant=object())):
        scribe.register_requirements()
