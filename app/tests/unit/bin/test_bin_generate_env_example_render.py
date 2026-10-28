"""Unit tests for bin/generate_env_example.py: which names it emits and how it lays them out.

Small settings classes declared here exercise the field walk (env-only metadata, the
prefix, a nested tenant entry joined by the delimiter); the real tree is collected once
to show every emitted name is one the ownership check claims and every other claim is
omitted on purpose. Nothing writes app/.env.example.
"""

import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from bin import generate_env_example as generator
from bin.check_settings_key_ownership import APP_ROOT, collect_env_claims
from contracts.configuration import env_only

pytestmark = pytest.mark.unit


class _Tenant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str = Field(description="A public id, held by a file.")
    token: SecretStr = env_only("Tenant token.", "codespaces")


class _Slice(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEMO__", env_nested_delimiter="__")

    tenant: _Tenant | None = None
    timeout_seconds: int = 10
    api_key: SecretStr = env_only("Demo API key.", "codespaces", default=SecretStr(""))
    bypass: str = env_only("A value you set yourself.", "local", default="")


def test_only_env_only_fields_are_walked_into_names_with_the_prefix_and_delimiter() -> None:
    names = generator._walk(_Slice, "DEMO__", "__", "demo.settings")

    assert [(name.name, name.source) for name in names] == [
        ("DEMO__TENANT__TOKEN", "codespaces"),
        ("DEMO__API_KEY", "codespaces"),
        ("DEMO__BYPASS", "local"),
    ]


def test_an_unknown_source_fails() -> None:
    class _Bad(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="BAD__")

        value: str = Field(default="", description="x", json_schema_extra={"env_only": True, "source": "laptop"})

    with pytest.raises(generator.GenerationError, match="laptop"):
        generator._walk(_Bad, "BAD__", None, "bad.settings")


def test_render_groups_by_module_with_the_source_tag_and_description() -> None:
    entries = [
        generator.EnvName("A__ONE", "alpha.settings", "codespaces", "First."),
        generator.EnvName("A__TWO", "alpha.settings", "local", "Second."),
        generator.EnvName("B__LONGER_NAME", "beta.settings", "devcontainer", "Third."),
    ]

    lines = generator.render(entries).splitlines()

    alpha = lines.index("# --- alpha.settings ---")
    beta = lines.index("# --- beta.settings ---")
    assert lines[alpha + 1].startswith("# A__ONE=") and lines[alpha + 1].endswith("[codespaces] First.")
    assert lines[alpha + 2].endswith("[local] Second.")
    assert lines[beta + 1].endswith("[devcontainer] Third.")
    # Names are padded to one column, so the tags line up.
    assert len({line.index("[") for line in (lines[alpha + 1], lines[alpha + 2], lines[beta + 1])}) == 1
    # Every name is commented out: the example sets nothing.
    assert all(line == "" or line.startswith("#") for line in lines)


def test_the_tree_emits_each_secret_and_non_public_name_and_omits_the_rest() -> None:
    entries, omitted = generator.collect()
    emitted = {entry.name for entry in entries}
    claimed = {claim.key for claim in collect_env_claims(APP_ROOT)[0]}

    assert {name.lower() for name in emitted} | set(omitted) == claimed
    assert not {name.lower() for name in emitted} & set(omitted)
    for name in (
        "SLACK__BOT_TOKEN",
        "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY",
        "AWS__TENANT__INSTANCE_ID",
        "TRELLO__TENANT__APP_KEY",
        "OPENAI__API_KEY",
        "SECURITY__DEV_BYPASS_TOKEN",
        "INCIDENT_CORE__FOLDER_ID",
        "TALENT__PANELIST_GUIDEBOOK_TEMPLATE_ID",
    ):
        assert name in emitted
    for name in ("slack__request_timeout_seconds", "incident_core__incidents_table", "environment"):
        assert name in omitted
