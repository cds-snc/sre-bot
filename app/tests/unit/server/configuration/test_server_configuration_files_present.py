"""Unit tests for the checked-in configuration files in app/config.

The ENVIRONMENT values come from AppSettings' Literal annotation, so adding an
environment without a file fails here. Each file is loaded through the real
loader, which parses it and applies the table and key-case checks.
"""

from typing import get_args

import pytest

from infrastructure.configuration.app import AppSettings
from server.configuration import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

ENVIRONMENTS = get_args(AppSettings.model_fields["ENVIRONMENT"].annotation)


def test_environment_literal_lists_the_three_environments() -> None:
    """Guards the parametrisation below against an annotation that no longer yields the values."""
    assert set(ENVIRONMENTS) == {"local", "ci", "production"}


@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_every_environment_has_a_file_that_loads_with_the_base_file(environment: str) -> None:
    """base.toml and <environment>.toml exist and pass the loader's checks."""
    files = load_configuration_files(environment)

    assert files.paths == (CONFIG_DIR / "base.toml", CONFIG_DIR / f"{environment}.toml")


def test_no_file_without_an_environment() -> None:
    """Every file in app/config is the base file or one ENVIRONMENT value's file."""
    names = {path.name for path in CONFIG_DIR.glob("*.toml")}

    assert names == {"base.toml", *(f"{environment}.toml" for environment in ENVIRONMENTS)}
