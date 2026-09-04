"""Behavior tests for AccessRuntimeConfig invariants (TASK-76.2)."""

import pytest

from packages.access.common.config.settings import AccessRuntimeConfig


@pytest.mark.unit
@pytest.mark.parametrize("dir_domain", ["", "   "])
def test_runtime_config_rejects_blank_dir_domain(dir_domain):
    """A blank domain is what makes group keys unusable, so it must be unconstructible."""
    with pytest.raises(ValueError):
        AccessRuntimeConfig(dir_prefix="sg", dir_domain=dir_domain)


@pytest.mark.unit
@pytest.mark.parametrize("dir_prefix", ["", "   "])
def test_runtime_config_rejects_blank_dir_prefix(dir_prefix):
    with pytest.raises(ValueError):
        AccessRuntimeConfig(dir_prefix=dir_prefix, dir_domain="example.com")


@pytest.mark.unit
def test_runtime_config_accepts_fully_specified_values():
    config = AccessRuntimeConfig(dir_prefix="sg", dir_domain="example.com", dir_separator="-")

    assert config.dir_domain == "example.com"
    assert config.group_prefix("aws") == "sg-aws-"
