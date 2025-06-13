import os
import json
import traceback
import time
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from slack import WebClient
from core.logging import get_module_logger
from core.config import settings

logger = get_module_logger()


def slack_command(ack, client: WebClient, body, respond, logger, args):
    ack()
    user_auth_client = WebClient(settings.slack.USER_TOKEN)
    expected_user = "U01DBUUHJEP"
    expected_channels = ["C04U4PCDZ24", "C03FA4DJCCU", "C03T4FAE9FV"]
    excel_path = os.path.join(os.path.dirname(__file__), "Tickets.xlsx")

    data = pd.read_excel(excel_path)
    report = ReportBuilder()

    if data.empty:
        logger.error("Excel file is empty or not found.")
        respond("Error: Excel file is empty or not found.")
        return

    response_text = f"Starting search for tickets in Slack at: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report.set_tickets_loaded(len(data))
    for index, row in data.head(300).iterrows():
        response_text += f"---\nProcessing query for ticket ID: {row['ID']}\n"
        try:
            query = f"Freshdesk created a ticket {row['ID']}"
            # Rate limiting: ensure no more than 20 calls per minute (i.e., 3 seconds between calls)
            if index > 0:
                time.sleep(3)
            search_response = user_auth_client.search_messages(query=query)

            if search_response.get("ok", False):
                messages: list[dict] = search_response.get("messages", []).get(
                    "matches", []
                )
                if messages:
                    response_text += "Search results:\n"
                    filtered_messages = []
                    skipped_messages = []
                    for message in messages:

                        message_creator = message.get("user", "Unknown User")
                        channel = message.get("channel", {}).get(
                            "id", "Unknown Channel"
                        )
                        if channel not in expected_channels:
                            logger.info(
                                f"Skipping message from unexpected channel: {channel}"
                            )
                            skipped_messages.append(message)
                            continue
                        if message_creator != expected_user:
                            logger.info(
                                f"Skipping message from unexpected user: {message_creator}"
                            )
                            skipped_messages.append(message)
                            continue

                        # text = sanitize_string(message.get("text", ""))
                        response_text += f"- {message['text']} <{message['permalink']}|(message link)>\n"
                        filtered_messages.append(message)
                    report.add_search_result(
                        ticket_id=row["ID"],
                        query=query,
                        matches=filtered_messages,
                        skipped_messages=skipped_messages,
                    )
                else:
                    response_text += "- No messages found.\n"

            else:
                logger.error(f"Error searching messages: {search_response}")
                response_text += (
                    f"- Error searching messages: {search_response['error']}\n"
                )
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            stack_trace = traceback.format_exc()
            logger.error(
                f"Error processing Slack command: {error_type}: {error_message}\n{stack_trace}"
            )
            response_text += (
                f"An error occurred while processing your request.\n"
                f"Error type: {error_type}\n"
                f"Error message: {error_message}"
            )
            continue

    report.save()
    respond(response_text + "\nSearch completed. Report saved to search_report.json.")


class ReportBuilder:
    def __init__(self):
        self.tickets_loaded = 0
        self.search_results: List[Dict[str, Any]] = []

    def set_tickets_loaded(self, count: int):
        self.tickets_loaded = count

    def add_search_result(
        self,
        ticket_id: str,
        query: str,
        matches: List[Dict[str, Any]],
        skipped_messages: List[Dict[str, Any]] = [],
    ):
        self.search_results.append(
            {
                "ticket_id": ticket_id,
                "query": query,
                "match_count": len(matches),
                "matches": matches,  # You can filter fields here if needed
                "skipped_messages": skipped_messages,
            }
        )

    def build_summary(self):
        summary = {
            "tickets_loaded": self.tickets_loaded,
            "tickets_with_one_match": 0,
            "tickets_with_multiple_matches": 0,
            "tickets_with_no_matches": 0,
            "skipped_messages": 0,
        }
        for result in self.search_results:
            if result["match_count"] == 1:
                summary["tickets_with_one_match"] += 1
            elif result["match_count"] > 1:
                summary["tickets_with_multiple_matches"] += 1
            else:
                summary["tickets_with_no_matches"] += 1
            summary["skipped_messages"] += len(result.get("skipped_messages", []))
        return summary

    def save(self, filepath="search_report.json"):
        report = {
            "summary": self.build_summary(),
            "details": self.search_results,
        }
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=default_converter)


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
