"""No-I/O vocabulary shared by the incident subdomains and core.

Stored strings and levels only; labels belong to whoever renders them.
"""

from enum import IntEnum, StrEnum


class IncidentStatus(StrEnum):
    """Internal lifecycle status of an incident, by its stored string."""

    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    READY_TO_BE_REVIEWED = "Ready to be Reviewed"
    REVIEWED = "Reviewed"
    CLOSED = "Closed"

    @property
    def is_open(self) -> bool:
        """Whether the incident is still open: every status except Closed."""
        return self is not IncidentStatus.CLOSED


class Severity(IntEnum):
    """Incident severity, 0 the most severe; an unset severity is None on the record."""

    SEV0 = 0
    SEV1 = 1
    SEV2 = 2
    SEV3 = 3
    SEV4 = 4


class IncidentRole(StrEnum):
    """The five incident roles; each value is the name of its field on the record."""

    INCIDENT_COMMANDER = "incident_commander"
    OPERATIONS_LEAD = "operations_lead"
    COMMUNICATIONS_LEAD = "communications_lead"
    POLICY_LEAD = "policy_lead"
    POSTMORTEM_OWNER = "postmortem_owner"


class StatusUpdateStage(StrEnum):
    """Public stage of an incident, declared in its only (forward) order.

    A public vocabulary, distinct from the incident's internal lifecycle
    status. The values are the stored strings; labels belong to the comms
    profile that renders them.
    """

    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
