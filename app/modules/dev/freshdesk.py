import os
import json
import re
import time
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from slack import WebClient
from slack_bolt import Ack, Respond
from core.logging import get_module_logger
from core.config import settings

logger = get_module_logger()


def freshdesk_command(
    ack: Ack, client: WebClient, body, respond: Respond, logger, args
):
    ack()
    respond(
        f"Starting search process at {time.strftime('%Y-%m-%d %H:%M:%S')}... this may take some time."
    )
    user_auth_client = WebClient(token=settings.slack.USER_TOKEN)
    expected_user = "U01DBUUHJEP"
    expected_channels = ["C04U4PCDZ24", "C03FA4DJCCU", "C03T4FAE9FV", "CNWA63606"]
    channel_id = body.get("channel_id", {})
    user_id = body.get("user_id", {})
    logger.info("freshdesk_search_started", channel_id=channel_id, user_id=user_id)

    # Load ticket data
    excel_path = os.path.join(os.path.dirname(__file__), "Tickets.xlsx")
    data = pd.read_excel(excel_path)
    if data.empty:
        respond("No data found in the Excel file.")
        return

    report = ReportBuilder()
    report.set_tickets_loaded(data)

    post_ephemeral_message(
        client=client,
        channel_id=channel_id,
        user_id=user_id,
        text=f"Loaded {len(data)} tickets from the Excel file. Starting search...",
    )

    logger.info("ticket_data_loaded", ticket_count=len(data))

    # Make one larger query for all Freshdesk ticket messages
    base_query = "from:freshdesk2 created a ticket"
    max_pages = 0

    all_matches = search_messages(
        base_query=base_query,
        user_auth_client=user_auth_client,
        max_pages=max_pages,
        app_client=client,
        channel_id=channel_id,
        user_id=user_id,
    )

    post_ephemeral_message(
        client=client,
        channel_id=channel_id,
        user_id=user_id,
        text=f"Processing {len(all_matches)} messages found for '{base_query}'...",
    )
    report.set_messages_searched_count(len(all_matches))
    tickets_processed, skipped_messages = process_messages(
        all_matches=all_matches,
        ticket_ids=report.tickets_ids,
        expected_user=expected_user,
        expected_channels=expected_channels,
    )
    # Add results to our report
    for ticket_id, matches in tickets_processed.items():
        report.add_search_result(
            ticket_id=ticket_id,
            query=f"{base_query} {ticket_id}",
            matches=matches,
        )

    report.set_skipped_messages(skipped_messages)

    # Save report
    report.save()

    # Build summary for response
    summary = report.build_summary()
    response_text = (
        f"Search completed.\nFound:\nExact matches for {summary['tickets_with_one_match']} tickets.\n"
        f"Multiple matches for {summary['tickets_with_multiple_matches']} tickets.\n"
        f"No matches for {summary['tickets_with_no_matches']} tickets.\n"
        f"Total tickets loaded: {summary['tickets_loaded_count']}\n"
        f"Report saved to search_report.json."
    )
    respond(response_text)


def post_ephemeral_message(client: WebClient, channel_id: str, user_id: str, text: str):
    """
    Post an ephemeral message to a Slack channel.
    """
    try:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=text,
        )
    except Exception as e:
        logger.error(f"Failed to post ephemeral message: {str(e)}")


def search_messages(
    base_query: str,
    user_auth_client: WebClient,
    max_pages=0,
    app_client: WebClient = None,
    channel_id: str = "",
    user_id: str = "",
):
    """
    Search messages in Slack using the provided base query.
    Returns a list of all matches found.
    """
    all_matches = []
    current_page = 1
    per_page = 100  # Slack API max per page

    while True:
        logger.info(
            "searching_messages",
            base_query=base_query,
            current_page=current_page,
            per_page=per_page,
        )
        try:
            search_response = user_auth_client.search_messages(
                query=base_query, count=per_page, page=current_page
            )
            matches = search_response.get("messages", {}).get("matches", [])
            pagination = search_response.get("messages", {}).get("pagination", {})
            all_matches.extend(matches)

            if current_page == 1:
                if app_client and channel_id and user_id:
                    response_message = f"Found {pagination.get('total_count', 0)} messages matching '{base_query}'.\nWith {per_page} messages per page and {pagination.get('page_count', 0)} total pages, this request will take {3 * pagination.get('page_count', 0)} seconds to complete. (assuming 3 seconds per page for rate limits)."
                    post_ephemeral_message(
                        client=app_client,
                        channel_id=channel_id,
                        user_id=user_id,
                        text=response_message,
                    )
                logger.info(
                    "search_response_received",
                    total_count=pagination.get("total_count", 0),
                    per_page=pagination.get("per_page", 0),
                    page_count=pagination.get("page_count", 0),
                )
            if max_pages == 0 and current_page == 1:
                max_pages = pagination.get("page_count", 0)
            current_page += 1

            if current_page >= max_pages or current_page > pagination.get(
                "page_count", 0
            ):
                logger.info("search_completed", total_matches=len(all_matches))
                break
            time.sleep(3)  # Respect rate limits

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            break

    return all_matches


def process_messages(
    all_matches: List[Dict[str, Any]],
    ticket_ids: set,
    expected_user: str,
    expected_channels: List[str],
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
    """
    Process the list of all matches, filtering by ticket IDs, user, and channel.
    Returns a tuple of two dictionaries:
    - tickets_processed: Maps ticket IDs to lists of messages that matched.
    - skipped_messages: Maps ticket IDs to lists of messages that were skipped, with reasons.
    """
    tickets_processed: Dict[str, List[Dict[str, Any]]] = {}
    skipped_messages: Dict[str, Dict[str, Any]] = {}

    logger.info(
        "processing_messages",
        total_matches=len(all_matches),
        ticket_ids_count=len(ticket_ids),
        expected_user=expected_user,
        expected_channels=expected_channels,
    )
    for msg in all_matches:

        ticket_id = extract_ticket_number(msg)
        # Check if ticket_id is None or empty
        if not ticket_id:
            log_skipped(skipped_messages, "no_ticket_id_found", msg)
            continue

        # Convert ticket_id to string for consistency
        ticket_id = str(ticket_id)
        # Check if ticket_id is in the list of expected ticket IDs
        if ticket_id not in ticket_ids:
            log_skipped(skipped_messages, "ticket_id_not_in_list", msg, ticket_id)
            continue

        # Check if in expected channels
        channel_id = msg.get("channel", {}).get("id")
        if channel_id not in expected_channels:
            log_skipped(skipped_messages, "wrong_channel", msg, ticket_id)
            continue

        # Check if from expected user
        user_id = msg.get("user")
        if user_id != expected_user:
            log_skipped(skipped_messages, "wrong_user", msg, ticket_id)
            continue

        # This message passed all filters
        if ticket_id not in tickets_processed:
            tickets_processed[ticket_id] = []
        tickets_processed[ticket_id].append(msg)
    logger.info(
        "messages_processed",
        total_tickets_processed=len(tickets_processed),
        total_skipped_messages=len(skipped_messages),
    )
    return tickets_processed, skipped_messages


def log_skipped(
    skipped_messages: Dict[str, Dict[str, Any]],
    reason: str,
    msg: Dict[str, Any],
    ticket_id: str | None = None,
):
    """
    Log a skipped message with a reason and add it to the skipped_messages dictionary.
    """
    if reason not in skipped_messages:
        skipped_messages[reason] = {}
    group_id = ticket_id if ticket_id is not None else "no_ticket_id"
    if group_id not in skipped_messages[reason]:
        skipped_messages[reason][group_id] = []
    skipped_messages[reason][group_id].append(msg)
    logger.warning(
        "skipping_message",
        reason=reason,
        ticket_id=ticket_id,
        message=msg,
    )


def default_converter(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    return str(o)


def sanitize_string(s: str) -> str:
    """Sanitize a string by removing non-printable characters."""
    return "".join(c for c in s if c.isprintable())


def extract_ticket_number(msg):
    """
    Extract ticket number from a Slack message by recursively searching through
    all text fields and looking for specific patterns.
    """
    # Strategy 1: Look for ticket numbers in URLs (most reliable)
    url_pattern = r"freshdesk\.com/a/tickets/(\d+)"

    # Strategy 2: Look for "#NNNN" pattern
    hashtag_pattern = r"#(\d+)"

    # Strategy 3: Look for "ticket NNNN" or "ticket #NNNN" pattern
    ticket_pattern = r"ticket\s+#?(\d+)"

    # Function to recursively search through the message structure
    def search_in_object(obj):
        if isinstance(obj, str):
            # Check for URLs first (most reliable)
            url_match = re.search(url_pattern, obj)
            if url_match:
                return url_match.group(1)

            # Then check for hashtag pattern
            hashtag_match = re.search(hashtag_pattern, obj)
            if hashtag_match:
                return hashtag_match.group(1)

            # Finally check for "ticket NNNN" pattern
            ticket_match = re.search(ticket_pattern, obj, re.IGNORECASE)
            if ticket_match:
                return ticket_match.group(1)

        elif isinstance(obj, dict):
            # Prioritize checking specific places where ticket numbers are likely to appear
            if "text" in obj and isinstance(obj["text"], str):
                result = search_in_object(obj["text"])
                if result:
                    return result

            # Then check all other dictionary values
            for key, value in obj.items():
                result = search_in_object(value)
                if result:
                    return result

        elif isinstance(obj, list):
            for item in obj:
                result = search_in_object(item)
                if result:
                    return result

        return None

    return search_in_object(msg)


class ReportBuilder:
    def __init__(self):
        self.tickets_loaded_count = 0
        self.tickets_ids = set()
        self.tickets_without_matches: List[str] = []
        self.search_results_count = 0
        self.search_results: List[Dict[str, Any]] = []
        self.skipped_messages: Dict[str, List[Dict[str, Any]]] = {}

    def set_tickets_loaded(self, tickets: pd.DataFrame):
        self.tickets_loaded_count = len(tickets)
        self.tickets_ids = set(tickets["ID"].astype(str).tolist())

    def set_messages_searched_count(self, count: int):
        self.search_results_count = count

    def add_search_result(
        self,
        ticket_id: str,
        query: str,
        matches: List[Dict[str, Any]],
    ):
        self.search_results.append(
            {
                "ticket_id": ticket_id,
                "query": query,
                "match_count": len(matches),
                "matches": matches,
            }
        )

    def set_skipped_messages(
        self,
        skipped_messages: Dict[str, Any],
    ):
        self.skipped_messages = skipped_messages

    def identify_tickets_without_matches(self):
        """
        Identify tickets that had no matches in the search results.
        This will populate self.tickets_without_matches with ticket IDs that had no matches.
        """
        matched_ticket_ids = {result["ticket_id"] for result in self.search_results}
        self.tickets_without_matches = [
            ticket_id
            for ticket_id in self.tickets_ids
            if ticket_id not in matched_ticket_ids
        ]
        logger.info(
            "identified_tickets_without_matches",
            total_without_matches=len(self.tickets_without_matches),
        )

    def build_summary(self):
        self.identify_tickets_without_matches()
        summary = {
            "messages_searched_count": self.search_results_count,
            "tickets_loaded_count": self.tickets_loaded_count,
            "tickets_with_one_match": 0,
            "tickets_with_multiple_matches": 0,
            "tickets_with_no_matches": 0,
            "skipped_messages_by_reason": {},
            "skipped_messages_total": 0,
        }
        for result in self.search_results:
            if result["match_count"] == 1:
                summary["tickets_with_one_match"] += 1
            elif result["match_count"] > 1:
                summary["tickets_with_multiple_matches"] += 1
        for reason, group in self.skipped_messages.items():
            count = sum(len(msgs) for msgs in group.values())
            summary["skipped_messages_by_reason"][reason] = count
            summary["skipped_messages_total"] += count
        return summary

    def save(self, filepath="search_report.json"):
        report = {
            "summary": self.build_summary(),
            "details": {
                "search_results": self.search_results,
                "skipped_tickets": self.tickets_without_matches,
            },
        }
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=default_converter)

        debug_file = {
            "skipped_messages": self.skipped_messages,
        }
        with open("skipped_messages.json", "w") as f:
            json.dump(debug_file, f, indent=2, default=default_converter)
