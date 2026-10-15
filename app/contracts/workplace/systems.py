"""The closed set of workplace systems a reference or a policy setting may name.

A stored reference records its system beside the tenant and the vendor's id
(``decisions/workplace-systems.md`` rules 3 and 4). The value is validated
strictly where it is chosen (settings, record construction) and read
tolerantly by stores; a new member ships in readers one deploy before any
writer (``decisions/cloud-portability.md`` contract 4).
"""

from enum import StrEnum


class WorkplaceSystem(StrEnum):
    """A workplace system, by its stored value; members arrive with their adapters."""

    SLACK = "slack"
    GOOGLE = "google"
