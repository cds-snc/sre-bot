"""Behavior tests for IncidentBinding validation.

A binding is a child record of an incident naming one place responders work it.
Its key parts form the stored ``binding_key``, so a part holding the key separator
would make two different places share one key and is rejected at construction.
"""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.domain import BindingKind, IncidentBinding
from tests.factories.incident import DECLARED_AT, binding_on

pytestmark = pytest.mark.unit


def test_a_chat_conversation_binding_is_built_and_frozen() -> None:
    binding = binding_on("C0INCIDENT", "inc-1")

    assert binding.kind is BindingKind.CHAT_CONVERSATION
    assert binding.system is WorkplaceSystem.SLACK
    assert binding.url is None
    assert binding.archived_at is None
    with pytest.raises(FrozenInstanceError):
        binding.primary = False  # type: ignore[misc]


def test_the_only_declared_kind_is_the_chat_conversation() -> None:
    """A Backstage page kind is reserved in the ADR and undeclared, so a stored one is an unknown kind."""
    assert [kind.value for kind in BindingKind] == ["chat_conversation"]


@pytest.mark.parametrize("field", ["incident_id", "tenant", "vendor_id", "bound_by"])
def test_a_blank_text_field_is_rejected_naming_it(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(binding_on("C0INCIDENT", "inc-1"), **{field: "  "})


@pytest.mark.parametrize("field", ["system", "tenant", "vendor_id"])
def test_a_separator_in_a_key_part_is_rejected_naming_it(field: str) -> None:
    value: object = "slack#x" if field == "system" else "a#b"
    with pytest.raises(ValueError, match=field):
        replace(binding_on("C0INCIDENT", "inc-1"), **{field: value})


def test_a_system_that_is_not_a_workplace_system_is_rejected() -> None:
    with pytest.raises(ValueError, match="system"):
        replace(binding_on("C0INCIDENT", "inc-1"), system="slack")  # type: ignore[arg-type]


def test_a_kind_that_is_not_a_binding_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="kind"):
        replace(binding_on("C0INCIDENT", "inc-1"), kind="chat_conversation")  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["bound_at", "archived_at"])
def test_a_naive_time_is_rejected_naming_it(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(binding_on("C0INCIDENT", "inc-1"), **{field: datetime(2026, 10, 1, 12, 0)})


def test_an_archived_binding_keeps_its_archive_time() -> None:
    binding = binding_on("C0INCIDENT", "inc-1", archived_at=DECLARED_AT)

    assert isinstance(binding, IncidentBinding)
    assert binding.archived_at == DECLARED_AT
