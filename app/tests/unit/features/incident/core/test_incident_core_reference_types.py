"""Behavior tests for the typed references an incident record carries.

Plain value tests. Every reference records the system and tenant beside the
vendor's id (never a bare vendor id), the system must be a WorkplaceSystem
member (strict where it is chosen), and each kind of reference is its own type
so a report can never be passed where a conversation is expected.
"""

import dataclasses

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.api import (
    ConversationReference,
    ExternalCaseReference,
    PostmortemMeetingReference,
    ReportReference,
    SourceAlertReference,
    VideoCallReference,
)

pytestmark = pytest.mark.unit

REFERENCE_TYPES = [
    ConversationReference,
    ReportReference,
    VideoCallReference,
    PostmortemMeetingReference,
    ExternalCaseReference,
    SourceAlertReference,
]


@pytest.mark.parametrize("reference_type", REFERENCE_TYPES)
def test_a_reference_carries_system_tenant_vendor_id_and_link(reference_type: type[ConversationReference]) -> None:
    """The four parts are kept as given; the link is optional."""
    reference = reference_type(
        system=WorkplaceSystem.GOOGLE, tenant="C03abc123", vendor_id="1AbC", url="https://example.test/1AbC"
    )

    assert (reference.system, reference.tenant, reference.vendor_id, reference.url) == (
        WorkplaceSystem.GOOGLE,
        "C03abc123",
        "1AbC",
        "https://example.test/1AbC",
    )
    assert reference_type(system=WorkplaceSystem.SLACK, tenant="T0", vendor_id="C0").url is None


@pytest.mark.parametrize("reference_type", REFERENCE_TYPES)
@pytest.mark.parametrize("field", ["tenant", "vendor_id"])
def test_a_blank_tenant_or_vendor_id_is_rejected(reference_type: type[ConversationReference], field: str) -> None:
    """A reference without its tenant is a bare vendor id, which is never stored."""
    fields = {"system": WorkplaceSystem.SLACK, "tenant": "T0", "vendor_id": "C0", field: " "}

    with pytest.raises(ValueError, match=field):
        reference_type(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize("reference_type", REFERENCE_TYPES)
@pytest.mark.parametrize("system", ["slack", "teams"])
def test_a_system_that_is_not_a_member_is_rejected(reference_type: type[ConversationReference], system: str) -> None:
    """Even a plain string equal to a member's value is refused where a system is chosen."""
    with pytest.raises(ValueError, match="system"):
        reference_type(system=system, tenant="T0", vendor_id="C0")  # type: ignore[arg-type]


def test_each_kind_of_reference_is_its_own_type() -> None:
    """No reference type is a subclass of another, so type checks tell them apart."""
    for reference_type in REFERENCE_TYPES:
        others = [other for other in REFERENCE_TYPES if other is not reference_type]
        assert not any(issubclass(reference_type, other) for other in others)


def test_a_reference_is_frozen() -> None:
    """A reference is an immutable value."""
    reference = ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C03abc123", vendor_id="1AbC")

    with pytest.raises(dataclasses.FrozenInstanceError):
        reference.vendor_id = "2XyZ"  # type: ignore[misc]
