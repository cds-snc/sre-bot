import os
import json
import traceback
import pandas as pd
from slack import WebClient
from core.logging import get_module_logger
from core.config import settings

logger = get_module_logger()


def slack_command(ack, client: WebClient, body, respond, logger, args):
    ack()
    respond("Processing request...")
    user_auth_client = WebClient(settings.slack.USER_TOKEN)
    response_text = "Finding messages in Slack completed"
    expected_user = "U01DBUUHJEP"
    expected_channels = ["C04U4PCDZ24", "C03FA4DJCCU", "C03T4FAE9FV"]
    excel_path = os.path.join(os.path.dirname(__file__), "Tickets.xlsx")
    data = pd.read_excel(excel_path)

    if data.empty:
        logger.error("Excel file is empty or not found.")
        respond("Error: Excel file is empty or not found.")
        return

    for index, row in data.head(3).iterrows():
        respond(f"Processing query for ticket ID: {row['ID']}")
        try:
            query = f"Freshdesk created a ticket {row['ID']}"
            search_response = user_auth_client.search_messages(query=query)

            if search_response.get("ok", False):
                logger.info("Search completed successfully.")
                messages: list[dict] = search_response.get("messages", []).get(
                    "matches", []
                )
                logger.info(
                    f"Found {len(messages)} messages matching the query: {query}"
                )
                # logger.info(f"Messages content: {json.dumps(messages, indent=2)}")
                if messages:
                    response_text = "Search results:\n"
                    for message in messages:
                        message_user = message.get("user", "Unknown User")
                        channel = message.get("channel", {}).get(
                            "id", "Unknown Channel"
                        )
                        logger.info(f"Found message: {json.dumps(message, indent=2)}")
                        logger.info(
                            "checking_user_match",
                            match=message_user == expected_user,
                            expected_user=expected_user,
                            message_user=message_user,
                        )
                        response_text += f"- {message['permalink']}\n"
                else:
                    response_text = "No messages found."
            else:
                logger.error(f"Error searching messages: {search_response}")
                response_text = f"Error searching messages: {search_response['error']}"
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            stack_trace = traceback.format_exc()
            logger.error(
                f"Error processing Slack command: {error_type}: {error_message}\n{stack_trace}"
            )
            response_text = (
                f"An error occurred while processing your request.\n"
                f"Error type: {error_type}\n"
                f"Error message: {error_message}"
            )

    respond(response_text)
