"""The report's status-line mapping: every other status's line is rewritten to the new status.

The mapping is pure, so it is asserted directly: for each of the five statuses it
names the four other ``Status: <s>`` lines, never the new status itself, each
rewritten to ``Status: <new>``. A report whose line already shows the new status
is left as it is, which is why the new status is not a key.
"""

import pytest

from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.google_docs import status_line_replacements

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("status", list(IncidentStatus))
def test_each_other_status_line_is_rewritten_to_the_new_status(status: IncidentStatus) -> None:
    replacements = status_line_replacements(status)

    assert replacements == {f"Status: {other.value}": f"Status: {status.value}" for other in IncidentStatus if other != status}


def test_the_lines_keep_the_legacy_order() -> None:
    assert list(status_line_replacements(IncidentStatus.CLOSED)) == [
        "Status: In Progress",
        "Status: Open",
        "Status: Ready to be Reviewed",
        "Status: Reviewed",
    ]
