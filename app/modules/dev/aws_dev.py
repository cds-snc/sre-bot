"""Testing AWS service (will be removed)"""

import json
import time
from core.logging import get_module_logger
from integrations.aws import identity_store, identity_store_next
from models.integrations import IntegrationResponse

logger = get_module_logger()


def aws_dev_command(ack, client, body, respond, logger):
    ack()

    logger.info("aws_dev_command", body=body)
    respond("AWS dev command received!")

    legacy_function = identity_store.list_groups_with_memberships
    next_function = identity_store_next.list_groups_with_memberships
    result = performance_comparison_example(
        legacy_func=legacy_function,
        next_func=next_function,
        legacy_formatter=format_groups,
        next_formatter=format_groups,
    )

    try:
        with open("test_aws_next.json", "w", encoding="utf-8") as f:
            json.dump(result["next"]["result"], f, indent=2)
        logger.info(
            "Saved group membership result to test_aws_next.json",
            count=len(result["next"]["result"]),
        )
    except Exception as e:
        logger.error("Failed to save test_aws_next.json", error=str(e))
    try:
        with open("test_aws_legacy.json", "w", encoding="utf-8") as f:
            json.dump(result["legacy"]["result"], f, indent=2)
        logger.info(
            "Saved group membership result2 to test_aws_legacy.json",
            count=len(result["legacy"]["result"]),
        )
    except Exception as e:
        logger.error("Failed to save test_aws_legacy.json", error=str(e))

    if result:
        respond(f"Comparison complete:\n{result['comparison']}")
    else:
        respond("No groups found or failed to retrieve group information.")


def format_users(users):
    return f"Users: {len(users)}"


def format_groups(groups):
    return f"Groups: {len(groups)}"


def format_group_memberships(memberships):
    return f"Group Memberships: {len(memberships)}"


def format_groups_with_members(groups):
    group_count = len(groups)
    member_count = sum(len(g.get("GroupMemberships", [])) for g in groups)
    return f"Groups: {group_count}, Total memberships: {member_count}"


def performance_comparison_example(
    legacy_func=None,
    next_func=None,
    legacy_formatter=None,
    next_formatter=None,
    legacy_label="legacy",
    next_label="next",
):
    """
    Compare two AWS Identity Store functions and return timing, counts, and formatted summaries.
    If only one function is provided, still returns timing for that function.
    """
    logger.info("starting_comparison", legacy=legacy_label, next=next_label)

    # Legacy
    if legacy_func:
        start_time = time.time()
        legacy_result = legacy_func()
        legacy_time = time.time() - start_time
        legacy_summary = (
            legacy_formatter(legacy_result)
            if legacy_formatter
            else f"Items: {len(legacy_result) if legacy_result else 0}"
        )
    else:
        legacy_result = None
        legacy_time = 0.0
        legacy_summary = "Not tested"

    # Next-gen
    if next_func:
        start_time = time.time()
        response: IntegrationResponse = next_func()
        if response.success:
            next_result = response.data
        else:
            next_result = None
            logger.error(
                "Next-gen function failed",
                function=next_label,
                error=response.error,
            )
        next_time = time.time() - start_time
        next_summary = (
            next_formatter(next_result)
            if next_formatter
            else f"Items: {len(next_result) if next_result else 0}"
        )
    else:
        next_result = None
        next_time = 0.0
        next_summary = "Not tested"

    # Calculate speedup only if both functions were tested
    if legacy_time > 0 and next_time > 0:
        speedup = legacy_time / next_time
        speedup_str = f"The next function is {speedup:.2f}x faster than legacy."
    elif legacy_time > 0 and next_time == 0:
        speedup_str = f"Only {legacy_label} was tested."
    elif legacy_time == 0 and next_time > 0:
        speedup_str = f"Only {next_label} was tested."
    else:
        speedup_str = "No functions were tested."

    comparison_lines = [
        f"{legacy_label.capitalize()}:",
        legacy_summary,
        f"Time: {legacy_time:.2f}s",
        "",
        f"{next_label.capitalize()}:",
        next_summary,
        f"Time: {next_time:.2f}s",
        "---",
        speedup_str,
    ]

    return {
        legacy_label: {
            "result": legacy_result,
            "time": legacy_time,
            "summary": legacy_summary,
        },
        next_label: {
            "result": next_result,
            "time": next_time,
            "summary": next_summary,
        },
        "comparison": "\n".join(comparison_lines),
    }
