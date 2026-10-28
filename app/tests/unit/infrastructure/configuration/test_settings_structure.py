"""Tests for what remains of infrastructure/configuration until each slice moves with its feature.

The feature package holds the SRE ops and AWS ops slices, each reading its own table of
the configuration files; the incident slice moved to [incident_response] (TASK-111.15.1), the atip and groups slices had no reader and are gone, and so is the
flat-name base class every legacy slice inherited.
"""

import importlib
import importlib.util

import pytest

import infrastructure.configuration.features as features
from contracts.configuration import ConfigurationSlice
from infrastructure.configuration.features import (
    AWSFeatureSettings,
    SreOpsSettings,
    get_aws_feature_settings,
    get_sre_ops_settings,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("settings_class", "table"),
    [(SreOpsSettings, "sre_ops"), (AWSFeatureSettings, "cloud_operations")],
)
def test_each_feature_slice_reads_its_own_table(settings_class: type[ConfigurationSlice], table: str) -> None:
    assert issubclass(settings_class, ConfigurationSlice)
    assert settings_class.model_config.get("toml_table_header") == (table,)


@pytest.mark.parametrize("getter", [get_sre_ops_settings, get_aws_feature_settings])
def test_each_provider_returns_one_instance(getter) -> None:
    getter.cache_clear()

    assert getter() is getter()


@pytest.mark.parametrize("module", ["atip", "groups", "incident"])
def test_the_atip_groups_and_incident_slices_are_gone(module: str) -> None:
    assert importlib.util.find_spec(f"infrastructure.configuration.features.{module}") is None
    assert not any(module in name.lower() for name in features.__all__)


def test_no_flat_name_base_class_remains() -> None:
    assert importlib.util.find_spec("infrastructure.configuration.base") is None
