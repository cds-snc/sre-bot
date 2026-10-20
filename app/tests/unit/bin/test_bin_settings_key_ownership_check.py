"""Behavior of the guardrail that gives every settings key exactly one owner.

The rules run over small source trees written to ``tmp_path``, so each case
shows the settings code it judges and stays independent of the real tree. A
parity test compares the names derived from source with the names pydantic
itself reads for real settings classes, which is what keeps a source-only
derivation honest. The remaining tests pin the guard against the actual
repository: it must report the tree clean, and it must be wired into the
Makefile and CI, since a guard nothing runs protects nothing.
"""

from pathlib import Path

from pydantic import AliasChoices
from pydantic_settings import BaseSettings

from bin import check_settings_key_ownership as checker
from infrastructure.configuration.app import AppSettings
from infrastructure.security.settings import SecuritySettings
from infrastructure.slack.settings import SlackTransportSettings
from integrations.slack.settings import SlackSettings
from packages.access.common.settings import AccessSettings

APP_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = APP_ROOT.parent

SETTINGS_IMPORTS = "from pydantic import AliasChoices, AliasPath, BaseModel, Field\nfrom pydantic_settings import BaseSettings, SettingsConfigDict\n"


def _write(root: Path, relative: str, source: str) -> None:
    """Write one module of a source tree under root."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _keys(root: Path, owner: str) -> set[str]:
    """Return the folded environment keys the guard derives for one class."""
    claims, _ = checker.collect_env_claims(root)
    return {claim.key for claim in claims if claim.owner == owner}


def _rules(root: Path) -> list[str]:
    """Return the rule name of every violation the guard reports for the tree."""
    return [violation.rule for violation in checker.find_violations(root)]


# Key ownership


def test_alias_read_by_two_classes_fails_naming_both_owners(tmp_path: Path) -> None:
    """Two slices reading one variable is the defect the ADR check forbids."""
    _write(
        tmp_path,
        "one/settings.py",
        SETTINGS_IMPORTS + 'class One(BaseSettings):\n    token: str = Field(default="", alias="SHARED_TOKEN")\n',
    )
    _write(
        tmp_path,
        "two/settings.py",
        SETTINGS_IMPORTS + 'class Two(BaseSettings):\n    secret: str = Field(default="", alias="SHARED_TOKEN")\n',
    )

    violations = checker.find_violations(tmp_path)

    assert [violation.rule for violation in violations] == ["key-ownership"]
    assert "one.settings:One" in violations[0].message
    assert "two.settings:Two" in violations[0].message


def test_names_differing_only_by_case_are_one_key(tmp_path: Path) -> None:
    """pydantic-settings folds case by default, so LOG_LEVEL and log_level collide."""
    _write(tmp_path, "a.py", SETTINGS_IMPORTS + "class A(BaseSettings):\n    LOG_LEVEL: str = 'INFO'\n")
    _write(tmp_path, "b.py", SETTINGS_IMPORTS + "class B(BaseSettings):\n    log_level: str = 'INFO'\n")

    assert _rules(tmp_path) == ["key-ownership"]


def test_env_prefix_plus_field_name_collides_with_a_flat_alias(tmp_path: Path) -> None:
    """A prefixed field name is the same variable as a bare alias spelling it out."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS
        + "class A(BaseSettings):\n    model_config = SettingsConfigDict(env_prefix='SLACK__')\n    TOKEN: str = ''\n",
    )
    _write(
        tmp_path, "b.py", SETTINGS_IMPORTS + "class B(BaseSettings):\n    token: str = Field(default='', alias='SLACK__TOKEN')\n"
    )

    assert _rules(tmp_path) == ["key-ownership"]


def test_alias_is_claimed_without_the_env_prefix(tmp_path: Path) -> None:
    """pydantic-settings applies env_prefix to field names only, never to aliases."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS
        + "class A(BaseSettings):\n    model_config = SettingsConfigDict(env_prefix='APP_')\n    token: str = Field(default='', alias='BOT_TOKEN')\n",
    )

    assert _keys(tmp_path, "a:A") == {"bot_token"}


def test_same_class_reading_its_own_names_twice_passes(tmp_path: Path) -> None:
    """A field name and its alias inside one class have one owner, so no collision."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS
        + "class A(BaseSettings):\n    model_config = SettingsConfigDict(populate_by_name=True)\n    TOKEN: str = Field(default='', alias='token')\n",
    )

    assert _rules(tmp_path) == []


def test_inherited_field_is_owned_by_the_declaring_class_only(tmp_path: Path) -> None:
    """A subclass reuses its base's field; that is one declaration, not two owners."""
    _write(tmp_path, "base.py", SETTINGS_IMPORTS + "class Base(BaseSettings):\n    LOG_LEVEL: str = 'INFO'\n")
    _write(tmp_path, "child.py", "from base import Base\n\nclass Child(Base):\n    EXTRA: str = ''\n")

    assert _rules(tmp_path) == []
    assert _keys(tmp_path, "child:Child") == {"extra"}


def test_base_class_config_is_inherited(tmp_path: Path) -> None:
    """A subclass of a prefixed base reads its own fields under the base's prefix."""
    _write(
        tmp_path,
        "base.py",
        SETTINGS_IMPORTS + "class Base(BaseSettings):\n    model_config = SettingsConfigDict(env_prefix='FEATURE_')\n",
    )
    _write(tmp_path, "child.py", "from base import Base\n\nclass Child(Base):\n    TIMEOUT: int = 1\n")

    assert _keys(tmp_path, "child:Child") == {"feature_timeout"}


def test_nested_model_expands_to_delimited_names(tmp_path: Path) -> None:
    """A nested model reads both the whole-model name and each delimited sub-field."""
    _write(
        tmp_path,
        "access.py",
        SETTINGS_IMPORTS
        + "class Sync(BaseModel):\n    enabled: bool = False\n\n"
        + "class Access(BaseSettings):\n"
        + "    model_config = SettingsConfigDict(env_prefix='ACCESS_', env_nested_delimiter='_', env_nested_max_split=1)\n"
        + "    sync: Sync = Field(default_factory=Sync)\n",
    )

    assert _keys(tmp_path, "access:Access") == {"access_sync", "access_sync_enabled"}


def test_nested_name_collides_with_a_flat_alias_elsewhere(tmp_path: Path) -> None:
    """A delimited nested name is a real variable, so a flat alias spelling it collides."""
    _write(
        tmp_path,
        "access.py",
        SETTINGS_IMPORTS
        + "class Sync(BaseModel):\n    enabled: bool = False\n\n"
        + "class Access(BaseSettings):\n"
        + "    model_config = SettingsConfigDict(env_prefix='ACCESS_', env_nested_delimiter='_', env_nested_max_split=1)\n"
        + "    sync: Sync | None = None\n",
    )
    _write(
        tmp_path,
        "other.py",
        SETTINGS_IMPORTS + "class Other(BaseSettings):\n    flag: bool = Field(default=False, alias='ACCESS_SYNC_ENABLED')\n",
    )

    assert _rules(tmp_path) == ["key-ownership"]


def test_populate_by_name_also_claims_the_field_name(tmp_path: Path) -> None:
    """With populate_by_name the bare field name is read beside the alias."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS
        + "class A(BaseSettings):\n    model_config = SettingsConfigDict(populate_by_name=True)\n    COMMAND_PREFIX: str = Field(default='', alias='SLACK__COMMAND_PREFIX')\n",
    )

    assert _keys(tmp_path, "a:A") == {"slack__command_prefix", "command_prefix"}


def test_validation_alias_choices_are_each_claimed(tmp_path: Path) -> None:
    """A one-release old name read through AliasChoices is still a key the class owns."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS
        + "class A(BaseSettings):\n    token: str = Field(default='', validation_alias=AliasChoices('SLACK__BOT_TOKEN', 'SLACK_TOKEN'))\n",
    )
    _write(
        tmp_path,
        "b.py",
        SETTINGS_IMPORTS + "class B(BaseSettings):\n    old: str = Field(default='', validation_alias='SLACK_TOKEN')\n",
    )

    assert _keys(tmp_path, "a:A") == {"slack__bot_token", "slack_token"}
    assert _rules(tmp_path) == ["key-ownership"]


def test_alias_path_fails_loudly(tmp_path: Path) -> None:
    """An alias the guard cannot turn into a variable name is reported, never skipped."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS + "class A(BaseSettings):\n    token: str = Field(default='', validation_alias=AliasPath('outer', 0))\n",
    )

    assert _rules(tmp_path) == ["unreadable-alias"]


def test_non_literal_alias_fails_loudly(tmp_path: Path) -> None:
    """A computed alias hides the variable name from review, so it is reported."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS + "NAME = 'TOKEN'\n\nclass A(BaseSettings):\n    token: str = Field(default='', alias=NAME)\n",
    )

    assert _rules(tmp_path) == ["unreadable-alias"]


def test_settings_class_nested_in_another_class_is_found(tmp_path: Path) -> None:
    """A settings class nested in another class still reads the environment."""
    _write(
        tmp_path,
        "loader.py",
        SETTINGS_IMPORTS
        + "class Loader:\n    class _Env(BaseSettings):\n        prefix: str = Field(default='', alias='DIR_PREFIX')\n",
    )

    assert _keys(tmp_path, "loader:Loader._Env") == {"dir_prefix"}


def test_plain_models_and_class_vars_are_not_settings_keys(tmp_path: Path) -> None:
    """Only BaseSettings subclasses read the environment; ClassVar and private names are not fields."""
    _write(
        tmp_path,
        "a.py",
        SETTINGS_IMPORTS
        + "from typing import ClassVar\n\n"
        + "class Payload(BaseModel):\n    token: str = ''\n\n"
        + "class A(BaseSettings):\n    LIMIT: ClassVar[int] = 3\n    _cache: dict = {}\n    token: str = ''\n",
    )

    claims, errors = checker.collect_env_claims(tmp_path)

    assert errors == []
    assert {(claim.owner, claim.key) for claim in claims} == {("a:A", "token")}


def test_tests_tree_is_ignored(tmp_path: Path) -> None:
    """Test doubles redeclare real keys on purpose; only shipped code is judged."""
    _write(tmp_path, "a.py", SETTINGS_IMPORTS + "class A(BaseSettings):\n    TOKEN: str = ''\n")
    _write(tmp_path, "tests/fake.py", SETTINGS_IMPORTS + "class Fake(BaseSettings):\n    TOKEN: str = ''\n")

    assert _rules(tmp_path) == []


# Vendor enablement


def test_vendor_enabled_key_in_integrations_fails(tmp_path: Path) -> None:
    """A vendor client is enabled by its tenant entry, never by a <VENDOR>_ENABLED key."""
    _write(
        tmp_path,
        "integrations/opsgenie/settings.py",
        SETTINGS_IMPORTS + "class OpsGenie(BaseSettings):\n    OPSGENIE_ENABLED: bool = False\n",
    )

    assert _rules(tmp_path) == ["vendor-enabled"]


def test_bare_enabled_key_in_integrations_fails(tmp_path: Path) -> None:
    """A prefixed `enabled` field is the same switch under another spelling."""
    _write(
        tmp_path,
        "integrations/trello/settings.py",
        SETTINGS_IMPORTS
        + "class Trello(BaseSettings):\n    model_config = SettingsConfigDict(env_prefix='TRELLO_')\n    enabled: bool = False\n",
    )

    assert _rules(tmp_path) == ["vendor-enabled"]


def test_slack_enabled_is_the_one_allowed_vendor_switch(tmp_path: Path) -> None:
    """SLACK_ENABLED is the interim transport switch until TASK-112 replaces it."""
    _write(
        tmp_path,
        "integrations/slack/settings.py",
        SETTINGS_IMPORTS + "class Slack(BaseSettings):\n    SLACK_ENABLED: bool = False\n",
    )

    assert _rules(tmp_path) == []


def test_enabled_keys_outside_integrations_are_not_vendor_switches(tmp_path: Path) -> None:
    """Feature switches are a TASK-112 concern; this rule covers vendor clients only."""
    _write(
        tmp_path,
        "packages/access/settings.py",
        SETTINGS_IMPORTS + "class Access(BaseSettings):\n    ACCESS_SYNC_ENABLED: bool = False\n",
    )

    assert _rules(tmp_path) == []


# Environment reads


def test_os_environ_read_outside_a_settings_class_fails(tmp_path: Path) -> None:
    """Every spelling of a direct environment read bypasses the owning slice."""
    _write(
        tmp_path,
        "service.py",
        "import os\n\nA = os.environ['A']\nB = os.environ.get('B')\nC = os.getenv('C')\n",
    )

    violations = checker.find_violations(tmp_path)

    assert [violation.location for violation in violations] == ["service.py:3", "service.py:4", "service.py:5"]
    assert {violation.rule for violation in violations} == {"environ-read"}


def test_from_os_import_environ_fails(tmp_path: Path) -> None:
    """Importing environ or getenv by name is the same read under another spelling."""
    _write(tmp_path, "service.py", "from os import environ, path\n")

    assert _rules(tmp_path) == ["environ-read"]


def test_environ_read_inside_a_settings_class_passes(tmp_path: Path) -> None:
    """A settings class is the one place allowed to read the environment."""
    _write(
        tmp_path,
        "a.py",
        "import os\n" + SETTINGS_IMPORTS + "class A(BaseSettings):\n    HOME: str = os.environ.get('HOME', '')\n",
    )

    assert _rules(tmp_path) == []


def test_bin_and_tests_trees_may_read_the_environment(tmp_path: Path) -> None:
    """Developer scripts and tests are not app code, so they are not judged."""
    _write(tmp_path, "bin/dev_token.py", "import os\n\nPORT = os.environ.get('PORT')\n")
    _write(tmp_path, "tests/conftest.py", "import os\n\nos.environ['ENVIRONMENT'] = 'ci'\n")

    assert _rules(tmp_path) == []


# Collision grouping is source-agnostic


def test_find_collisions_groups_by_source_kind() -> None:
    """A config-file key and an env key with the same spelling are different sources."""
    claims = [
        checker.Claim(source_kind="env", key="token", owner="a:A"),
        checker.Claim(source_kind="config-file", key="token", owner="b:B"),
        checker.Claim(source_kind="env", key="token", owner="a:A"),
    ]

    assert checker.find_collisions(claims) == []


# Parity with pydantic and the real tree


def _pydantic_env_names(cls: type[BaseSettings]) -> set[str]:
    """Return the folded environment names pydantic-settings reads for top-level fields."""
    prefix = cls.model_config.get("env_prefix", "")
    by_name = bool(cls.model_config.get("populate_by_name") or cls.model_config.get("validate_by_name"))
    names: set[str] = set()
    for field_name, info in cls.model_fields.items():
        alias = info.validation_alias or info.alias
        if isinstance(alias, AliasChoices):
            names.update(str(choice) for choice in alias.choices)
        elif isinstance(alias, str):
            names.add(alias)
        if alias is None or by_name:
            names.add(prefix + field_name)
    return {name.lower() for name in names}


def test_source_derivation_matches_pydantic_for_real_settings_classes() -> None:
    """The guard re-derives names from source, so it must agree with pydantic on real slices.

    Nested sub-field names are the only extra the guard adds, so pydantic's
    top-level names must be a subset and every extra must extend one of them.
    """
    for cls in (SlackSettings, SlackTransportSettings, AppSettings, AccessSettings, SecuritySettings):
        derived = _keys(APP_ROOT, f"{cls.__module__}:{cls.__qualname__}")
        expected = _pydantic_env_names(cls)

        assert expected <= derived, cls.__qualname__
        assert all(any(extra.startswith(name) for name in expected) for extra in derived - expected), cls.__qualname__


def test_access_settings_nested_names_are_derived() -> None:
    """AccessSettings' documented variables come from nested models, not flat fields."""
    derived = _keys(APP_ROOT, "packages.access.common.settings:AccessSettings")

    assert {"access_sync_enabled", "access_requests_enabled", "access_catalog_enabled", "access_config_source"} <= derived


def test_real_tree_is_clean() -> None:
    """The regression test proper: no key has two owners and no rule is broken today."""
    assert checker.find_violations(APP_ROOT) == []


def test_real_tree_reads_every_settings_class() -> None:
    """A walker that silently scans nothing would also report clean, so coverage is pinned."""
    claims, _ = checker.collect_env_claims(APP_ROOT)
    owners = {claim.owner for claim in claims}

    assert "packages.access.common.config.loaders:EnvConfigLoader._EnvModel" in owners
    assert "jobs.settings:SchedulerSettings" in owners
    assert len(owners) >= 30


def test_guard_is_wired_into_the_makefile_and_ci() -> None:
    """An unrun guard protects nothing, so both entry points are pinned."""
    makefile = (APP_ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci_code.yml").read_text(encoding="utf-8")

    assert "check-settings-key-ownership:" in makefile
    assert "make check-settings-key-ownership" in workflow
