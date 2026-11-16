"""Singleton providers of the on-call capability: the rotation files and the service over both sources."""

from functools import lru_cache

from capabilities.oncall.adapters.opsgenie import OpsgenieSource
from capabilities.oncall.adapters.rotations import RotationsSource, load_rotation_schedules
from capabilities.oncall.domain import OPSGENIE, ROTATIONS, Schedule
from capabilities.oncall.service import OnCallService


@lru_cache(maxsize=1)
def get_rotation_schedules() -> tuple[Schedule, ...]:
    """Load and validate the rotation files once; raises ValueError for an invalid or duplicated rotation."""
    return load_rotation_schedules()


@lru_cache(maxsize=1)
def get_oncall_service() -> OnCallService:
    """Build the service over the rotations source and the Opsgenie source."""
    return OnCallService({ROTATIONS: RotationsSource(get_rotation_schedules()), OPSGENIE: OpsgenieSource()})
