"""Manual OpsGenie integration probe (READ-ONLY).

Run from the ``app/`` directory:

    uv run python manual_test_opsgenie.py

Loads the API key from ``../opsgenie-key`` (a single line), exercises the
OpsGenie integration functions used by the slack_opsgenie_sync feature, and
prints results. Performs no writes and never touches Slack.

Delete this file when done.
"""

import json
import os
import sys
from pathlib import Path

# Set env BEFORE importing the integration (key is read at import time).
KEY_PATH = Path(__file__).resolve().parent.parent / "opsgenie-key"
if not KEY_PATH.exists():
    sys.exit(f"opsgenie-key not found at {KEY_PATH}")
os.environ["OPSGENIE_INTEGRATIONS_KEY"] = KEY_PATH.read_text().strip()

from integrations import opsgenie  # noqa: E402
from integrations.opsgenie import client as opsgenie_client  # noqa: E402

SCHEDULE_ID = "657ce41a-2ff6-4d23-b2a2-53571995d710"
ROTATION_NAME = "PSO_rotation"


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    section("1. healthcheck() — confirms the key + connectivity")
    print(f"healthy={opsgenie.healthcheck()}")

    section("2. get_on_call_users(schedule_id) — schedule-wide aggregate")
    users = opsgenie.get_on_call_users(SCHEDULE_ID)
    print(f"on-call across all rotations in schedule: {users}")

    section("3. Raw /timeline payload — shows all rotations on the schedule")
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = (
        f"https://api.opsgenie.com/v2/schedules/{SCHEDULE_ID}/timeline"
        f"?identifierType=id&interval=1&intervalUnit=days&date={now}"
    )
    content = opsgenie_client.api_get_request(
        url, {"name": "GenieKey", "token": opsgenie_client.OPSGENIE_KEY}
    )
    data = json.loads(content)
    rotations = data["data"]["finalTimeline"]["rotations"]
    print(f"rotations on this schedule ({len(rotations)}):")
    for rot in rotations:
        name = rot.get("name")
        periods = rot.get("periods") or []
        print(f"  - rotation {name!r} has {len(periods)} period(s) in window:")
        for p in periods:
            print(
                f"      startDate={p.get('startDate')} "
                f"endDate={p.get('endDate')} "
                f"recipient={p.get('recipient')}"
            )

    section(
        f"4. get_on_call_user_for_rotation({SCHEDULE_ID!r}, {ROTATION_NAME!r})"
    )
    try:
        email = opsgenie.get_on_call_user_for_rotation(SCHEDULE_ID, ROTATION_NAME)
        print(f"current on-call email for {ROTATION_NAME!r}: {email!r}")
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")

    section("5. Same call against a non-existent rotation (should be None)")
    try:
        missing = opsgenie.get_on_call_user_for_rotation(
            SCHEDULE_ID, "does-not-exist-rotation"
        )
        print(f"result: {missing!r}")
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
