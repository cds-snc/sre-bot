"""Configuration check: the checked-in production and local files satisfy every enabled plugin's declarations.

For each environment the real base file and environment file are installed, the
plugin switches they set are read (the pytest-env pins, the scheduler pin and every
environment name the settings declare are removed first, and the working directory
holds no ``.env``), the enabled plugins are loaded on a fresh plugin manager with the
disabled names blocked, and only ``register_requirements`` is fired. Each declaration
must resolve against the configured-systems read and the validated slices. Secrets get
placeholder values only here, and only for the environment-only names the environment
is known to supply, derived from the settings classes' ``env_only`` declarations:
production supplies the names in ``terraform/ssm.tf``, local the names whose declared
source is a Codespaces secret. A requirement on a secret nothing supplies must fail.
The check cannot see the values held in SSM or in Codespaces.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pluggy
import pytest
import structlog

from bin.audit_env_coverage import terraform_parameters
from bin.generate_env_example import EnvName, collect
from contracts.configuration import ConfigurationError, install_configuration_files
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.plugins.requirements import Requirement
from integrations.google_workspace.settings import get_google_workspace_settings
from integrations.openai.settings import get_openai_settings
from integrations.opsgenie.settings import get_opsgenie_settings
from integrations.slack.settings import get_slack_settings
from server.configuration import load_configuration_files
from server.configured_systems import read_configured_systems
from server.plugins.manager import load_plugins
from server.plugins.requirements import declared_requirements, unmet_requirements
from server.plugins.settings import get_plugins_settings
from tests.factories.google_service_account import service_account_key

pytestmark = pytest.mark.integration

PLACEHOLDER = "placeholder-value"
SETTINGS_GETTERS = (
    get_plugins_settings,
    get_slack_settings,
    get_google_workspace_settings,
    get_openai_settings,
    get_opsgenie_settings,
)
PLUGIN_AREAS = ("INCIDENT_RESPONSE", "CLOUD_OPERATIONS", "PLATFORM_ACCESS", "WORKPLACE_UTILITIES")


@pytest.fixture(autouse=True)
def _clean_settings_caches() -> Iterator[None]:
    for getter in SETTINGS_GETTERS:
        getter.cache_clear()
    yield
    for getter in SETTINGS_GETTERS:
        getter.cache_clear()


def _placeholder(name: str) -> str:
    # The Google key must parse as a service-account key to build credentials; every other secret is opaque.
    return service_account_key() if name == "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY" else PLACEHOLDER


def _problems(
    environment: str, supplied: set[str], entries: list[EnvName], monkeypatch: pytest.MonkeyPatch, workdir: Path
) -> list[str]:
    """Return what is wrong with the environment's files, given the environment names its secrets come from."""
    monkeypatch.chdir(workdir)
    for area in PLUGIN_AREAS:
        monkeypatch.delenv(f"PLUGINS__{area}", raising=False)
    monkeypatch.delenv("SCHEDULER__ENABLED", raising=False)
    for entry in entries:
        monkeypatch.delenv(entry.name, raising=False)
    for entry in entries:
        if entry.name in supplied:
            monkeypatch.setenv(entry.name, _placeholder(entry.name))
    monkeypatch.setenv("ENVIRONMENT", environment)
    install_configuration_files(load_configuration_files(environment))

    logger = structlog.get_logger()
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    load_plugins(pm, get_plugins_settings().disabled(), logger)
    declared = declared_requirements(pm, logger)

    problems: list[str] = []
    known = {entry.name for entry in entries}
    for plugin, requirements in declared.items():
        problems += _unsupplied_secrets(plugin, requirements, known, supplied)
    try:
        failures = unmet_requirements(declared, read_configured_systems())
    except (ConfigurationError, ValueError) as error:
        return [*problems, f"settings do not validate: {error}"]
    return [*problems, *(f"{failure.plugin} requires {failure.setting}, which does not resolve" for failure in failures)]


def _unsupplied_secrets(plugin: str, requirements: tuple[Requirement, ...], known: set[str], supplied: set[str]) -> list[str]:
    names = ((requirement, requirement.setting.upper().replace(".", "__")) for requirement in requirements)
    return [
        f"{plugin} requires {requirement.setting}, an environment-only secret ({name}) no source supplies"
        for requirement, name in names
        if name in known and name not in supplied
    ]


def test_production_files_satisfy_every_enabled_plugin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entries, _ = collect()
    supplied = {entry.name for entry in entries} & terraform_parameters()

    assert _problems("production", supplied, entries, monkeypatch, tmp_path) == []


def test_local_files_satisfy_every_enabled_plugin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entries, _ = collect()
    supplied = {entry.name for entry in entries if entry.source == "codespaces"}

    assert _problems("local", supplied, entries, monkeypatch, tmp_path) == []


def test_production_fails_when_a_required_secret_is_not_in_the_parameter_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entries, _ = collect()
    supplied = ({entry.name for entry in entries} & terraform_parameters()) - {"SLACK__USER_TOKEN"}

    problems = _problems("production", supplied, entries, monkeypatch, tmp_path)

    assert any("oncall_sync requires slack.user_token" in problem for problem in problems)


def test_local_fails_when_a_required_secret_has_no_codespaces_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entries, _ = collect()
    supplied = {entry.name for entry in entries if entry.source == "codespaces"} - {"SLACK__USER_TOKEN"}

    problems = _problems("local", supplied, entries, monkeypatch, tmp_path)

    assert any("oncall_sync requires slack.user_token" in problem for problem in problems)


def test_the_check_does_not_leave_its_environment_behind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entries, _ = collect()
    _problems("local", set(), entries, monkeypatch, tmp_path)
    monkeypatch.undo()

    assert os.environ.get("ENVIRONMENT") == "ci"
