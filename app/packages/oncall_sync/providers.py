"""Singleton provider wiring for the on-call sync feature.

Selects the concrete adapters that satisfy ``ports.py`` and assembles the
``OnCallSyncService``. Swapping a vendor (e.g. JSM instead of OpsGenie,
MS Teams instead of Slack) is a change here only — ``service.py`` and the
hookimpls in ``__init__.py`` stay untouched.
"""

from functools import lru_cache

from packages.oncall_sync.adapters.opsgenie import OpsGenieScheduleProvider
from packages.oncall_sync.adapters.slack import build_user_group_sync_target
from packages.oncall_sync.ports import (
    OnCallScheduleProvider,
    UserGroupSyncTarget,
)
from packages.oncall_sync.service import OnCallSyncService
from packages.oncall_sync.settings import get_oncall_schedules, get_oncall_sync_settings
from packages.user_rotations.providers import get_user_rotations_service


@lru_cache(maxsize=1)
def get_oncall_schedule_provider() -> OnCallScheduleProvider:
    return OpsGenieScheduleProvider()


@lru_cache(maxsize=1)
def get_user_group_sync_target() -> UserGroupSyncTarget:
    return build_user_group_sync_target(approved_domains=frozenset(get_oncall_sync_settings().APPROVED_EMAIL_DOMAINS))


@lru_cache(maxsize=1)
def get_oncall_sync_service() -> OnCallSyncService:
    return OnCallSyncService(
        on_call=get_oncall_schedule_provider(),
        target=get_user_group_sync_target(),
        schedules=get_oncall_schedules(),
        user_rotations=get_user_rotations_service(),
    )
