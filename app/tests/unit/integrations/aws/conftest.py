"""Shared fixtures for the AWS slice tests.

``_aws_env_isolation`` (autouse) removes every AWS_* and AWS__* variable, disables the
.env file and clears the cached provider, so a test observes only the files it installs
and the variables it sets. ``install_aws_files`` writes a base and a local file into
tmp_path and installs them.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import install_configuration_files
from integrations.aws.settings import AWSSettings, get_aws_settings
from server.configuration.loader import TomlConfigurationFiles

INSTANCE_ID = "d-1234567890"
INSTANCE_ARN = "arn:aws:sso:::instance/ssoins-1234567890abcdef"


@pytest.fixture(autouse=True)
def _aws_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every AWS unit test."""
    monkeypatch.setitem(AWSSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("AWS_"):
            monkeypatch.delenv(key, raising=False)
    get_aws_settings.cache_clear()
    yield
    get_aws_settings.cache_clear()


def install_aws_files(tmp_path: Path, base: str = "[aws]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
