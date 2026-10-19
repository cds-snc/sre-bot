"""Unit tests for the ConfiguredSystems contract.

The host implementation is assigned where the Protocol is the declared type,
so mypy checks it satisfies the contract; the runtime assertion checks the
read returns the system-to-tenant mapping that consumers index by system.
"""

import pytest

from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from server.configured_systems import StaticConfiguredSystems

pytestmark = pytest.mark.unit


def test_host_implementation_satisfies_the_contract() -> None:
    systems: ConfiguredSystems = StaticConfiguredSystems({WorkplaceSystem.SLACK: "T0123"})

    assert systems.tenants()[WorkplaceSystem.SLACK] == "T0123"
