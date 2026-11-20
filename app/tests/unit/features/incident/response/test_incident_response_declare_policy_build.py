"""The declare policy the response provider builds from the incident settings slices.

``declare_policy`` reads ``[incident_core] conversation_name_attempts`` each time it
is called. The test replaces the provider's slice getter with constructed slices, so
no configuration file or environment is involved, and calls the provider twice: a
changed value showing on the second call proves it is read at call time, not
captured once.
"""

import pytest

from features.incident.common.settings import IncidentCoreSettings
from features.incident.response import providers

pytestmark = pytest.mark.unit


def test_the_conversation_name_bound_is_read_from_the_core_slice_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    bounds = iter([2, 7])
    monkeypatch.setattr(
        providers, "get_incident_core_settings", lambda: IncidentCoreSettings(conversation_name_attempts=next(bounds))
    )

    first = providers.declare_policy(production=True)
    second = providers.declare_policy(production=False)

    assert (first.conversation_name_attempts, second.conversation_name_attempts) == (2, 7)
    assert (first.production, second.production) == (True, False)
