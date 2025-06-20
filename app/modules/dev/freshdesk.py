import datetime
import os
import json
import re
import time
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from slack_sdk import WebClient
from slack_sdk.web import SlackResponse
from slack_bolt import Ack, Respond
from core.logging import get_module_logger
from core.config import settings

logger = get_module_logger()


class ReportBuilder:
    def __init__(self):
        self.search_results_count = 0
        self.tickets_ids_loaded = set()
        self.tickets_without_matches: List[str] = []
        self.tickets_search_results: List[Dict[str, Any]] = []
        self.skipped_messages: Dict[str, List[Dict[str, Any]]] = {}

    def set_tickets_ids_loaded(self, tickets: pd.DataFrame):
        self.tickets_ids_loaded = set(tickets["ID"].astype(str).tolist())

    def get_tickets_ids_loaded_count(self) -> int:
        """
        Get the count of tickets that were loaded.
        This is used to report the total number of tickets processed.
        """
        return len(self.tickets_ids_loaded)

    def set_messages_searched_count(self, count: int):
        """Set the count of messages that were searched during the process using the basic query."""
        self.search_results_count = count

    def add_ticket_search_result(
        self,
        ticket_id: str,
        query: str,
        matches: List[Dict[str, Any]],
    ):
        self.tickets_search_results.append(
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
        matched_ticket_ids = {
            result["ticket_id"] for result in self.tickets_search_results
        }
        self.tickets_without_matches = [
            ticket_id
            for ticket_id in self.tickets_ids_loaded
            if ticket_id not in matched_ticket_ids
        ]
        self.tickets_without_matches.sort()
        logger.info(
            "identified_tickets_without_matches",
            total_without_matches=len(self.tickets_without_matches),
        )

    def load_from_file(self, report_data, skipped_messages):
        """
        Load the report from a JSON file.
        This will populate the report with data from the file.
        """
        self.search_results_count = report_data["summary"]["messages_searched_count"]
        self.tickets_search_results = report_data["details"]["tickets_search_results"]
        self.tickets_without_matches = report_data["details"]["skipped_tickets"]
        self.skipped_messages = skipped_messages

    def build_summary(self):
        self.identify_tickets_without_matches()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = {
            "report_generated_at": now,
            "messages_searched_count": self.search_results_count,
            "tickets_loaded_count": self.get_tickets_ids_loaded_count(),
            "tickets_with_one_match": 0,
            "tickets_with_multiple_matches": 0,
            "tickets_with_no_matches": len(self.tickets_without_matches),
            "skipped_messages_by_reason": {},
            "skipped_messages_total": 0,
        }
        for result in self.tickets_search_results:
            if result["match_count"] == 1:
                summary["tickets_with_one_match"] += 1
            elif result["match_count"] > 1:
                summary["tickets_with_multiple_matches"] += 1
        for reason, group in self.skipped_messages.items():
            count = sum(len(msgs) for msgs in group.values())
            summary["skipped_messages_by_reason"][reason] = count
            summary["skipped_messages_total"] += count
        return summary

    def save(self):
        directory = os.path.dirname(__file__)
        report_path = os.path.join(directory, "search_report.json")
        skipped_messages_path = os.path.join(directory, "skipped_messages.json")
        report = {
            "summary": self.build_summary(),
            "details": {
                "tickets_search_results": self.tickets_search_results,
                "skipped_tickets": self.tickets_without_matches,
            },
        }
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=default_converter)

        with open(skipped_messages_path, "w") as f:
            json.dump(self.skipped_messages, f, indent=2, default=default_converter)


def freshdesk_command(ack: Ack, client: WebClient, body, respond: Respond, args):
    ack()
    respond(f"Starting search process at {time.strftime('%Y-%m-%d %H:%M:%S')}.")
    logger.info("freshdesk_command_received", body=json.dumps(body), args=args)
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

    search_report_path = os.path.join(os.path.dirname(__file__), "search_report.json")
    skipped_messages_path = os.path.join(
        os.path.dirname(__file__), "skipped_messages.json"
    )
    execute_search = True
    if os.path.exists(search_report_path) and os.path.exists(skipped_messages_path):
        execute_search = False

    report = ReportBuilder()
    report.set_tickets_ids_loaded(data)

    if execute_search:
        response_text = search_and_process(
            client=client,
            channel_id=channel_id,
            user_id=user_id,
            user_auth_client=user_auth_client,
            report=report,
            data=data,
            expected_user=expected_user,
            expected_channels=expected_channels,
        )
        respond(response_text)
    else:
        response_text = load_from_files(
            client=client,
            channel_id=channel_id,
            user_id=user_id,
            report=report,
            search_report_path=search_report_path,
            skipped_messages_path=skipped_messages_path,
        )
        respond(response_text)

    time_sleep_value = 1
    search_complete_message = (
        f"Tickets matches completed. Starting to fetch thread messages for parent messages.\n"
        f"With {len(report.tickets_search_results)} matching tickets found, it should take approximately {len(report.tickets_search_results) * time_sleep_value/60} minutes. (API rate limit of 50 calls per minute, so approximately 2 seconds per call to support pagination)."
    )
    post_ephemeral_message(
        client=client,
        channel_id=channel_id,
        user_id=user_id,
        text=search_complete_message,
    )
    # for each search result, lookup the thread messages for the is_parent_message matches
    total_results = len(report.tickets_search_results)
    for idx, result in enumerate(report.tickets_search_results, start=1):
        ticket_id = result["ticket_id"]
        matches = result["matches"]
        if not matches:
            continue
        # Find the first match that is a parent message
        parent_message = next(
            (msg for msg in matches if msg.get("is_parent_message")), None
        )
        if not parent_message:
            continue
        thread_ts = parent_message.get("ts")
        if not thread_ts:
            continue
        parent_message_channel_id = parent_message.get("channel", {}).get("id")
        if not parent_message_channel_id:
            continue

        # Fetch all messages in the thread
        thread_messages = find_thread_messages(
            client=client, channel_id=parent_message_channel_id, thread_ts=thread_ts
        )
        # API rate limit of 50 calls per minute
        time.sleep(time_sleep_value)

        # Add thread messages to the report
        result["thread_messages"] = thread_messages
        result["thread_messages_count"] = len(thread_messages)
        progress = f"{idx}/{total_results} ({(idx / total_results) * 100:.2f}%)"
        logger.info(
            "thread_messages_found",
            progress=progress,
            ticket_id=ticket_id,
            thread_ts=thread_ts,
            message_count=len(thread_messages),
        )
    report.save()


def post_ephemeral_message(
    client: WebClient, channel_id: str, user_id: str, text: str
) -> Any | None:
    """
    Post an ephemeral message to a Slack channel.
    """
    try:
        response = client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=text,
        )
        if response.get("ok", None):
            return response
    except Exception as e:
        logger.error(f"Failed to post ephemeral message: {str(e)}")
    return None


def load_from_files(
    client: WebClient,
    channel_id: str,
    user_id: str,
    report: ReportBuilder,
    search_report_path: str,
    skipped_messages_path: str,
):
    """
    Load tickets from the json files generated by the search process.
    """
    post_ephemeral_message(
        client=client,
        channel_id=channel_id,
        user_id=user_id,
        text="Search report already exists. Loading from search_report.json.",
    )
    # Load existing report
    with open(search_report_path, "r") as f:
        report_data = json.load(f)
    with open(skipped_messages_path, "r") as f:
        skipped_messages = json.load(f)

    report.load_from_file(report_data, skipped_messages)

    # Build summary for response
    summary = report.build_summary()
    response_text = (
        f"Search completed.\n"
        f"Total tickets provided: {report.get_tickets_ids_loaded_count()}\n"
        f"Messages found for basic query: {summary['messages_searched_count']}\n"
        f"Found:\nExact matches for {summary['tickets_with_one_match']} tickets.\n"
        f"Multiple matches for {summary['tickets_with_multiple_matches']} tickets.\n"
        f"No matches for {summary['tickets_with_no_matches']} tickets.\n"
        f"Total tickets loaded: {summary['tickets_loaded_count']}\n"
        f"Report loaded from search_report.json."
    )
    return response_text


def search_and_process(
    client: WebClient,
    channel_id: str,
    user_id: str,
    user_auth_client: WebClient,
    report: ReportBuilder,
    data: pd.DataFrame,
    expected_user: str,
    expected_channels: List[str],
):
    post_ephemeral_message(
        client=client,
        channel_id=channel_id,
        user_id=user_id,
        text=f"Loaded {len(data)} tickets from the Excel file. Starting search...",
    )
    # Make one larger query for all Freshdesk ticket messages
    base_query = "from:freshdesk2 created a ticket"
    max_pages = 0  # 0 means no limit, will fetch all pages

    all_matches = search_messages(
        base_query=base_query,
        user_auth_client=user_auth_client,
        max_pages=max_pages,
        client=client,
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

    # Process the messages to find matches for each ticket ID provided
    tickets_processed, skipped_messages = process_messages(
        all_matches=all_matches,
        ticket_ids=report.tickets_ids_loaded,
        expected_user=expected_user,
        expected_channels=expected_channels,
    )
    # Add results to our report
    for ticket_id, matches in tickets_processed.items():
        report.add_ticket_search_result(
            ticket_id=ticket_id,
            query=f"{base_query} {ticket_id}",
            matches=matches,
        )
    # Add messages that had no matches
    report.set_skipped_messages(skipped_messages)

    # Save report
    report.save()

    # Build summary for response
    summary = report.build_summary()
    response_text = (
        f"Search completed.\n"
        f"Total tickets provided: {report.get_tickets_ids_loaded_count()}\n"
        f"Messages found for basic query: {summary['messages_searched_count']}\n"
        f"Found:\nExact matches for {summary['tickets_with_one_match']} tickets.\n"
        f"Multiple matches for {summary['tickets_with_multiple_matches']} tickets.\n"
        f"No matches for {summary['tickets_with_no_matches']} tickets.\n"
        f"Total tickets loaded: {summary['tickets_loaded_count']}\n"
        f"Report saved to search_report.json."
    )
    return response_text


def search_messages(
    client: WebClient | None = None,
    user_id: str = "",
    channel_id: str = "",
    base_query: str = "",
    user_auth_client: WebClient | None = None,
    max_pages: int = 0,
):
    """
    Search messages in Slack using the provided base query.
    Returns a list of all matches found.
    """
    all_matches: List[Dict[str, Any]] = []
    current_page = 1
    per_page = 100  # Slack API max per page

    if not user_auth_client:
        raise ValueError("user_auth_client must be provided for searching messages.")

    while True:
        logger.info(
            "searching_messages",
            base_query=base_query,
            current_page=current_page,
            per_page=per_page,
        )
        try:
            search_response: SlackResponse = user_auth_client.search_messages(
                query=base_query, count=per_page, page=current_page
            )
            messages: dict[str, Any] = search_response.get("messages", {})
            matches = messages.get("matches") or []
            pagination = messages.get("pagination", {})
            all_matches.extend(matches)

            if current_page == 1:
                if client and channel_id and user_id:
                    response_message = (
                        f"Found {pagination.get('total_count', 0)} messages matching '{base_query}'.\n"
                        f"With {per_page} messages per page and {pagination.get('page_count', 0)} total pages, this request will take {3 * pagination.get('page_count', 0) / 60} minutes to complete. (assuming 3 seconds per page for rate limits)."
                    )
                    post_ephemeral_message(
                        client=client,
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
        message_channel_id = msg.get("channel", {}).get("id")
        if message_channel_id not in expected_channels:
            log_skipped(skipped_messages, "wrong_channel", msg, ticket_id)
            continue

        # Check if from expected user
        author_user_id = msg.get("user")
        if author_user_id != expected_user:
            log_skipped(skipped_messages, "wrong_user", msg, ticket_id)
            continue

        # Check if the text contains the expected pattern

        text = msg.get("text", "")
        if re.search(r"\bcreated a ticket\b", text, re.IGNORECASE):
            msg["is_parent_message"] = True
        else:
            msg["is_parent_message"] = False

        keys_to_remove = ["attachments", "blocks"]
        for key in keys_to_remove:
            if key in msg:
                del msg[key]
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


def process_messages_threads():
    pass


def is_conversation_member(
    client: WebClient,
    channel_id: str,
) -> bool:
    """
    Check if the client app is a member of a Slack conversation (channel).
    Returns True if the client app is a member, False otherwise.
    """
    try:
        response = client.conversations_members(channel=channel_id)
        members = response.get("members", [])
        return client.auth_test().get("user_id") in members
    except Exception as e:
        logger.error(
            "error_checking_conversation_membership",
            channel_id=channel_id,
            error=str(e),
        )
        return False


def find_thread_messages(
    client: WebClient,
    channel_id: str,
    thread_ts: str,
) -> List[Dict[str, Any]]:
    """
    Find all messages in a thread given the channel ID and thread timestamp.
    Returns a list of messages in the thread.
    """
    all_messages: List[Dict[str, Any]] = []
    is_member = is_conversation_member(
        client=client,
        channel_id=channel_id,
    )
    if not is_member:
        try:
            client.conversations_join(channel=channel_id)
        except Exception as e:
            logger.error("error_joining_channel", channel_id=channel_id, error=str(e))
            return all_messages
    try:
        response = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
        )
        messages: list[dict[str, Any]] = response.get("messages", [])
        if messages:
            # keep the following keys of the message
            keys_to_keep = [
                "ts",
                "user",
                "text",
                "type",
                "thread_ts",
                "reply_count",
                "reply_users_count",
                "reply_users",
            ]
            for msg in messages:
                filtered_msg = {k: msg[k] for k in keys_to_keep if k in msg}
                all_messages.append(filtered_msg)

    except Exception as e:
        logger.error(
            "error_fetching_thread_messages",
            channel_id=channel_id,
            thread_ts=thread_ts,
            error=str(e),
        )

    return all_messages


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
            for _key, value in obj.items():
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
