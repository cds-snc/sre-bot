import logging
from datetime import datetime, timedelta

import json

from integrations.google_workspace.google_calendar import (
    get_freebusy,
    insert_event,
    find_first_available_slot,
)


# Schedule a calendar event by finding the first available slot in the next 60 days that all participants are free in and book the event
def schedule_event(event_details, days):
    # Define the time range for the query
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # time_min is the current time + days and time_max is the current time + 60 days + days
    time_min = (now + timedelta(days=days)).isoformat() + "Z"
    time_max = (now + timedelta(days=(60 + days))).isoformat() + "Z"

    print("EVENT DETAILS: ", event_details)
    # Construct the items array
    items = []
    emails = json.loads(event_details).get("emails")
    incident_name = json.loads(event_details).get("name")
    for email in emails:
        email = email.strip()
        items.append({"id": email})

    # get the incident document link
    incident_document = json.loads(event_details).get("incident_document")

    # Execute the query to find all the busy times for all the participants
    freebusy_result = get_freebusy(time_min, time_max, items)

    # return the first available slot to book the event
    first_available_start, first_available_end = find_first_available_slot(
        freebusy_result, days
    )

    # If there are no available slots, return None
    if first_available_start is None and first_available_end is None:
        logging.info("No available slots found")
        return None

    event_config = {
        "description": "This is a retro meeting to discuss incident: " + incident_name,
        "conferenceData": {
            "createRequest": {
                "requestId": f"{first_available_start.timestamp()}",  # Unique ID per event to avoid collisions
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet"  # This automatically generates a Google Meet link
                },
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
            ],
        },
    }

    result = insert_event(
        first_available_start.isoformat(),
        first_available_end.isoformat(),
        emails,
        "Retro " + incident_name,
        incident_document,
        **event_config,
    )
    return result  # Return the HTML link and event info
