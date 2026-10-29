"""Unit tests for how settings slices hold credentials.

The test walks every ConfigurationSlice subclass the application defines and the
models nested in its fields, so a slice added later is covered without a list. Three
rules: a credential-named env-only field is typed SecretStr or SecretBytes (the name
heuristic lives only here; production code withholds by metadata and type); a
SecretStr or SecretBytes field is env-only, so no configuration file can hold a
credential; and with a canary set for each credential through the environment, no
repr and no JSON dump of the built slice contains it.
"""

import importlib
import json
import sys
import types
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, SecretBytes, SecretStr
from pydantic.fields import FieldInfo

from contracts.configuration import ConfigurationSlice, install_configuration_files, is_env_only
from infrastructure.logging.formatters import mask_sensitive_data
from tests.factories.google_service_account import service_account_info

pytestmark = pytest.mark.unit

TESTS_ROOT = Path(__file__).resolve().parents[2]
CREDENTIAL_WORDS = ("token", "secret", "password", "key")
SECRET_TYPES = (SecretStr, SecretBytes)


def _defined_in_tests(slice_class: type) -> bool:
    """Whether a test module declared the class: those are fixtures of other tests, not application slices."""
    return TESTS_ROOT in Path(sys.modules[slice_class.__module__].__file__ or "").parents


def _slices() -> list[type[ConfigurationSlice]]:
    importlib.import_module("server.configuration")
    importlib.import_module("packages.access.common.settings")
    pending = list(ConfigurationSlice.__subclasses__())
    found: list[type[ConfigurationSlice]] = []
    while pending:
        candidate = pending.pop()
        pending.extend(candidate.__subclasses__())
        if not _defined_in_tests(candidate):
            found.append(candidate)
    return sorted(found, key=lambda candidate: candidate.__name__)


def _models_in(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    if get_origin(annotation) in (Union, types.UnionType, list, tuple):
        return [model for argument in get_args(annotation) for model in _models_in(argument)]
    return []


def _holds_secret_type(annotation: Any) -> bool:
    if isinstance(annotation, type) and issubclass(annotation, SECRET_TYPES):
        return True
    return any(_holds_secret_type(argument) for argument in get_args(annotation))


def _fields(model: type[BaseModel], path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], FieldInfo]]:
    for name, field in model.model_fields.items():
        yield (*path, name), field
        for nested in _models_in(field.annotation):
            yield from _fields(nested, (*path, name))


def _all_fields() -> list[tuple[str, tuple[str, ...], FieldInfo]]:
    return [(slice_class.__name__, path, field) for slice_class in _slices() for path, field in _fields(slice_class)]


def test_the_walk_finds_the_application_slices() -> None:
    """Guards the walk itself: it reaches the vendor slices and their nested tenant entries."""
    names = {slice_class.__name__ for slice_class in _slices()}
    paths = {(owner, ".".join(path)) for owner, path, _ in _all_fields()}

    assert {"SlackSettings", "GoogleWorkspaceSettings", "TrelloSettings", "SecuritySettings"} <= names
    assert ("GoogleWorkspaceSettings", "tenant.service_account_key") in paths


def test_every_credential_named_env_only_field_is_a_secret_type() -> None:
    """A field named like a credential and held only in the environment cannot be a plain str."""
    plain = [
        f"{owner}.{'.'.join(path)}"
        for owner, path, field in _all_fields()
        if is_env_only(field) and any(word in path[-1] for word in CREDENTIAL_WORDS) and not _holds_secret_type(field.annotation)
    ]

    assert plain == []


def test_every_secret_typed_field_is_env_only() -> None:
    """A SecretStr or SecretBytes field never sits in a reviewed configuration file."""
    in_files = [
        f"{owner}.{'.'.join(path)}"
        for owner, path, field in _all_fields()
        if _holds_secret_type(field.annotation) and not is_env_only(field)
    ]

    assert in_files == []


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


def _canary_environment() -> dict[str, tuple[str, str]]:
    """Environment name to (value to set, text that must not appear), for every secret-typed field."""
    environment: dict[str, tuple[str, str]] = {}
    for slice_class in _slices():
        prefix = str(slice_class.model_config["env_prefix"])
        for path, field in _fields(slice_class):
            if _holds_secret_type(field.annotation):
                name = f"{prefix}{'__'.join(path)}".upper()
                canary = f"canary-{name.lower()}-9f3a"
                environment[name] = (canary, canary)
    return environment


# Non-credential values a slice needs next to its credentials to validate: its tenant entry.
_COMPANIONS = {
    "SLACK__TENANT__TEAM_ID": "T0CANARY1",
    "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID": "C0CANARY1",
    "NOTIFY__TENANT__API_URL": "https://notify.example",
    "OPENAI__TENANT__BASE_URL": "https://openai.example",
    "OPENAI__TENANT__MODEL": "canary-model",
    "OPSGENIE__TENANT__API_URL": "https://opsgenie.example",
}


def test_no_repr_and_no_json_dump_shows_a_canary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a canary in every credential field, repr, str and model_dump_json of each built slice hide it."""
    canaries = _canary_environment()
    google_key_name = "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY"
    info = service_account_info()
    canaries[google_key_name] = (json.dumps(info), info["private_key"].splitlines()[1])
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "base.toml"
    base.write_text(
        "".join(f"[{slice_class.model_config['toml_table_header'][0]}]\n" for slice_class in _slices()), encoding="utf-8"
    )
    install_configuration_files(_Files(environment="ci", paths=(base,)))
    for name, (value, _) in canaries.items():
        monkeypatch.setenv(name, value)
    for name, value in _COMPANIONS.items():
        monkeypatch.setenv(name, value)
    needles = [needle for _, needle in canaries.values()]
    built = 0

    for slice_class in _slices():
        if not any(str(slice_class.model_config["env_prefix"]) in name for name in canaries):
            continue
        slice_values = slice_class()
        rendered = repr(slice_values) + str(slice_values) + slice_values.model_dump_json()
        assert [needle for needle in needles if needle in rendered] == [], slice_class.__name__
        built += 1

    assert built >= 8


# Names the summary logs as dict keys that the pipeline's key-name redaction masks:
# "auth" in unauthorized_*, "token" in max_output_tokens, "api_key" in the table name.
EXPECTED_MASKED_NAMES = {"aws.unauthorized_codes", "notify_api_key_leak", "openai.max_output_tokens", "slack.unauthorized_errors"}


def _shown_names(slice_class: type[ConfigurationSlice]) -> Iterator[str]:
    for field_name, field in slice_class.model_fields.items():
        if is_env_only(field) or field.annotation in SECRET_TYPES:
            continue
        yield field_name
        for model in _models_in(field.annotation):
            for nested_name, nested in model.model_fields.items():
                if not is_env_only(nested) and nested.annotation not in SECRET_TYPES:
                    yield f"{field_name}.{nested_name}"


def test_the_summary_names_key_name_redaction_masks_are_pinned() -> None:
    """A table or shown field name matching a redaction pattern is masked in the summary, so the set is pinned.

    The summary keys sections by table and shown values by field name; the redaction
    processor is applied to a one-key event per name, so a new collision fails here and
    is decided in review rather than found missing in a production log.
    """
    redact = mask_sensitive_data()
    masked: set[str] = set()
    for slice_class in _slices():
        table = slice_class.model_config["toml_table_header"][0]
        if redact(None, "info", {table: "x"})[table] != "x":
            masked.add(table)
            continue
        masked |= {f"{table}.{name}" for name in _shown_names(slice_class) if redact(None, "info", {name: "x"})[name] != "x"}

    assert masked == EXPECTED_MASKED_NAMES
