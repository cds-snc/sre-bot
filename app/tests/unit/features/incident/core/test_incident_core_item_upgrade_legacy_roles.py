"""Behavior tests for the legacy roles step of the shared per-item upgrade plan.

``roles_report`` and ``with_legacy_roles`` are pure, so the tests call them on
items built by the legacy upgrade factory, with the plan ``plan_item_upgrade``
returns for each. Assertions are on the report a roleless item is read from,
on the role changes placed before the version marker, and on the guards that
hold all five roles at their read value so a concurrent role write wins.
"""

from typing import Any

import pytest

from contracts.records import SetAttribute
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.adapters.incident_items import END_STATE_VERSION, RECORD_VERSION
from features.incident.core.adapters.item_upgrade import (
    ItemUpgrade,
    RolesUnmappable,
    plan_item_upgrade,
    roles_report,
    with_legacy_roles,
)
from features.incident.core.domain import ReportReference
from tests.factories.legacy_upgrade import GOOGLE_TENANT, REPORT_URL, TENANTS, end_state_item, legacy_item

pytestmark = pytest.mark.unit

REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="doc123", url=REPORT_URL)
ROLES = {IncidentRole.INCIDENT_COMMANDER: "U0IC", IncidentRole.OPERATIONS_LEAD: "U0OL"}
NO_ROLES: dict[str, Any] = {"incident_commander": None, "operations_lead": None}
FIVE_ABSENT = {role.value: None for role in IncidentRole}


def _plan(item: dict[str, Any]) -> ItemUpgrade | None:
    plan = plan_item_upgrade(item, TENANTS)
    assert plan is None or isinstance(plan, ItemUpgrade)
    return plan


@pytest.mark.parametrize(
    "item",
    [
        legacy_item("inc-1", operations_lead=None),
        end_state_item("inc-1", incident_commander=None),
        end_state_item("inc-1", version=RECORD_VERSION, **NO_ROLES, policy_lead="U0POLICY"),
    ],
    ids=["legacy", "at-1", "at-2-other-role"],
)
def test_an_item_holding_any_role_is_not_read(item: dict[str, Any]) -> None:
    assert roles_report(item, _plan(item)) is None


@pytest.mark.parametrize(
    "item",
    [
        legacy_item("inc-1", **NO_ROLES),
        end_state_item("inc-1", **NO_ROLES),
        end_state_item("inc-1", version=RECORD_VERSION, **NO_ROLES),
        end_state_item("inc-1", version=RECORD_VERSION, incident_commander=" ", operations_lead=None),
    ],
    ids=["legacy", "at-1", "at-2", "at-2-blank-role"],
)
def test_a_roleless_item_is_read_from_its_google_report(item: dict[str, Any]) -> None:
    assert roles_report(item, _plan(item)) == REPORT


@pytest.mark.parametrize(
    "item",
    [
        legacy_item("inc-1", **NO_ROLES, report_url=None),
        end_state_item("inc-1", version=RECORD_VERSION, **NO_ROLES, report=None),
        end_state_item("inc-1", version=RECORD_VERSION, **NO_ROLES, policy_lead={"not": "text"}),
    ],
    ids=["legacy-no-report", "at-2-no-report", "at-2-unguardable-role"],
)
def test_a_roleless_item_whose_roles_cannot_be_mapped_is_unmappable(item: dict[str, Any]) -> None:
    assert roles_report(item, _plan(item)) == RolesUnmappable("inc-1")


def test_an_item_above_the_record_version_is_left_alone() -> None:
    item = end_state_item("inc-1", version=RECORD_VERSION + 1, **NO_ROLES)

    assert roles_report(item, None) is None


def test_a_legacy_plan_sets_the_roles_before_the_marker_and_guards_all_five() -> None:
    item = legacy_item("inc-1", **NO_ROLES)
    plan = _plan(item)
    assert plan is not None

    mapped = with_legacy_roles(item, plan, ROLES)

    assert mapped.changes[-1] == SetAttribute("record_version", RECORD_VERSION)
    assert mapped.changes[-3:-1] == (SetAttribute("incident_commander", "U0IC"), SetAttribute("operations_lead", "U0OL"))
    assert mapped.changes[:-3] == plan.changes[:-1]
    assert mapped.expected == {**plan.expected, **FIVE_ABSENT}
    assert (mapped.binding, mapped.from_version, mapped.roles) == (plan.binding, None, tuple(ROLES))


def test_an_end_state_plan_gains_the_roles_before_its_marker() -> None:
    item = end_state_item("inc-1", **NO_ROLES)
    plan = _plan(item)
    assert plan is not None

    mapped = with_legacy_roles(item, plan, {IncidentRole.INCIDENT_COMMANDER: "U0IC"})

    assert mapped.changes == (SetAttribute("incident_commander", "U0IC"), SetAttribute("record_version", RECORD_VERSION))
    assert mapped.expected == {**plan.expected, **FIVE_ABSENT}
    assert (mapped.from_version, mapped.roles) == (END_STATE_VERSION, (IncidentRole.INCIDENT_COMMANDER,))


def test_an_item_at_the_record_version_gets_a_roles_only_plan_guarded_at_its_read_roles() -> None:
    item = end_state_item("inc-1", version=RECORD_VERSION, incident_commander="", operations_lead=None)

    mapped = with_legacy_roles(item, None, ROLES)

    assert mapped.changes == (SetAttribute("incident_commander", "U0IC"), SetAttribute("operations_lead", "U0OL"))
    assert mapped.expected == {"record_version": RECORD_VERSION, **FIVE_ABSENT, "incident_commander": ""}
    assert (mapped.incident_id, mapped.from_version, mapped.binding) == ("inc-1", RECORD_VERSION, None)
