"""Unit tests for the incident role vocabulary.

Plain value tests: the five role names, which are also the names of the role
fields on the incident record.
"""

import dataclasses

import pytest

from features.incident.common.vocabulary import IncidentRole
from features.incident.core.api import Incident

pytestmark = pytest.mark.unit


def test_the_five_roles_are_named() -> None:
    """The role values are the stored names."""
    assert [role.value for role in IncidentRole] == [
        "incident_commander",
        "operations_lead",
        "communications_lead",
        "policy_lead",
        "postmortem_owner",
    ]


def test_each_role_names_a_field_on_the_incident_record() -> None:
    """A role gives generic access to its named field, e.g. getattr(incident, role)."""
    fields = {field.name for field in dataclasses.fields(Incident)}

    assert {role.value for role in IncidentRole} <= fields
