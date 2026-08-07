"""Singleton provider wiring for the on-call sync feature.

Selects the concrete adapters that satisfy ``ports.py`` and assembles the
``OnCallSyncService``. Swapping a vendor (e.g. JSM instead of OpsGenie,
MS Teams instead of Slack) is a change here only — ``service.py`` and the
hookimpls in ``__init__.py`` stay untouched.
"""

from __future__ import annotations

from functools import lru_cache

from slack_sdk import WebClient

from integrations.slack.settings import get_slack_settings
from packages.oncall_sync.adapters.opsgenie import OpsGenieScheduleProvider
from packages.oncall_sync.adapters.slack import SlackUserGroupTarget
from packages.oncall_sync.ports import (
    OnCallScheduleProvider,
    UserGroupSyncTarget,
)
from packages.oncall_sync.service import OnCallSyncService
from packages.oncall_sync.settings import get_oncall_schedules


@lru_cache(maxsize=1)
def get_oncall_schedule_provider() -> OnCallScheduleProvider:
    return OpsGenieScheduleProvider()


@lru_cache(maxsize=1)
def get_user_group_sync_target() -> UserGroupSyncTarget:
    settings = get_slack_settings()
    if not settings.USER_TOKEN:
        raise ValueError(
            "SLACK_USER_TOKEN is required to sync on-call rotations into Slack user groups "
            "(usergroups.* writes cannot use the shared inbound bot token)."
        )
    return SlackUserGroupTarget(WebClient(token=settings.USER_TOKEN))


@lru_cache(maxsize=1)
def get_oncall_sync_service() -> OnCallSyncService:
    return OnCallSyncService(
        on_call=get_oncall_schedule_provider(),
        target=get_user_group_sync_target(),
        schedules=get_oncall_schedules(),
    )
