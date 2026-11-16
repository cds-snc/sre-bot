"""Unit tests for the public surface of the on-call capability.

Reads the capability's own source and dataclass fields: the exported names, the absence of a
platform-named field in the domain types, the invariant on ``OnCallPerson`` and the absence of
incident or oncall_sync vocabulary under ``capabilities/oncall``. No stubs are needed.
"""

import dataclasses
import re
from pathlib import Path

import pytest

from capabilities.oncall import api
from capabilities.oncall.api import Account, OnCallPerson, Rotation, Schedule, ScheduleReference, Shift

pytestmark = pytest.mark.unit

CAPABILITY = Path(api.__file__).parent


def test_the_api_exports_the_lookup_the_types_the_constants_and_the_accessors() -> None:
    assert set(api.__all__) == {
        "OPSGENIE",
        "ROTATIONS",
        "Account",
        "OnCallLookup",
        "OnCallPerson",
        "Rotation",
        "Schedule",
        "ScheduleReference",
        "Shift",
        "configured_rotations",
        "get_oncall_lookup",
    }
    assert (api.OPSGENIE, api.ROTATIONS) == ("opsgenie", "rotations")


def test_account_carries_platform_tenant_and_account_id() -> None:
    assert [field.name for field in dataclasses.fields(Account)] == ["platform", "tenant", "account_id"]
    assert [field.name for field in dataclasses.fields(OnCallPerson)] == ["email", "account"]
    assert [field.name for field in dataclasses.fields(ScheduleReference)] == ["system", "id"]


def test_no_domain_type_has_a_platform_named_field() -> None:
    names = {
        field.name
        for cls in (Account, OnCallPerson, Rotation, Schedule, ScheduleReference, Shift)
        for field in dataclasses.fields(cls)
    }

    assert not {name for name in names if "slack" in name or "opsgenie" in name}


def test_an_on_call_person_needs_an_email_or_an_account() -> None:
    with pytest.raises(ValueError, match="email or an account"):
        OnCallPerson(email=None, account=None)
    assert OnCallPerson(email="a@example.org", account=None).email == "a@example.org"
    assert OnCallPerson(email=None, account=Account("slack", None, "U1")).account is not None


def test_the_domain_types_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ScheduleReference("rotations", "x").id = "y"  # type: ignore[misc]


def test_the_capability_names_no_incident_or_oncall_sync_vocabulary() -> None:
    sources = [path for path in CAPABILITY.rglob("*") if path.suffix in {".py", ".md"}]
    pattern = re.compile(r"incident|oncall_sync|usergroup_sync", re.IGNORECASE)
    allowed = {"README.md"}

    offenders = {
        path.relative_to(CAPABILITY).as_posix()
        for path in sources
        if path.name not in allowed and pattern.search(path.read_text())
    }

    assert offenders == set()
