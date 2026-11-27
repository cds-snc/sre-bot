"""The declare policy the response provider builds from the incident settings slices.

``declare_policy`` reads ``[incident_core] conversation_name_attempts`` and
``dev_conversation_names`` each time it is called. The test replaces the provider's slice getter with constructed slices, so
no configuration file or environment is involved, and calls the provider twice: a
changed value showing on the second call proves it is read at call time, not
captured once.
"""

import pytest

from features.incident.common.settings import IncidentCoreSettings
from features.incident.response import providers

pytestmark = pytest.mark.unit


def test_the_conversation_naming_keys_are_read_from_the_core_slice_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    slices = iter(
        [
            IncidentCoreSettings(conversation_name_attempts=2, dev_conversation_names=False),
            IncidentCoreSettings(conversation_name_attempts=7, dev_conversation_names=True),
        ]
    )
    monkeypatch.setattr(providers, "get_incident_core_settings", lambda: next(slices))

    first = providers.declare_policy()
    second = providers.declare_policy()

    assert (first.conversation_name_attempts, second.conversation_name_attempts) == (2, 7)
    assert (first.production, second.production) == (True, False)
