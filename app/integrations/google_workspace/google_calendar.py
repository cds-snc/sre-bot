import datetime
import os.path
import pickle
import base64
import logging
from datetime import datetime, timedelta, timezone

import pytz
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

GOOGLE_DELEGATED_ADMIN_EMAIL = 	"sre-bot@cds-snc.ca" #os.environ.get("GOOGLE_DELEGATED_ADMIN_EMAIL")

import os
from integrations.google_workspace.google_service import (
    get_google_service,
    handle_google_api_errors,
)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

@handle_google_api_errors
def schedule_event(emails):
    # pylint: disable=no-member
    service = get_google_service("calendar", "v3", delegated_user_email=GOOGLE_DELEGATED_ADMIN_EMAIL,scopes=SCOPES)

    # Define the time range for the query
    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'  # 'Z' indicates UTC time
    time_max = (now + timedelta(days=60)).isoformat() + 'Z'

    # Construct the request body
    freebusy_query = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": "primary"}, {"id": "guillaume.charest@cds-snc.ca"}, {"id": "sylvia.mclaughlin@cds-snc.ca"}]  # Query the primary calendar
    }

    # Execute the query
    freebusy_result = service.freebusy().query(body=freebusy_query).execute()

    first_available_start, first_available_end = find_first_available_slot(freebusy_result)
    if first_available_start is None and first_available_end is None:
        logging.info("No available slots found")
        return None
    #first_available_start, first_available_end = find_first_available_slot_take_two(freebusy_result)
    print("First available slot:", first_available_start, first_available_end)

    event_link = book_calendar_event(service, first_available_start, first_available_end, emails, incident_name)
    return event_link



def book_calendar_event(service, start, end, emails, incident_name):
    # split the emails into a list
    emails = emails.split(",")
    
    # Build the attendees array
    attendees = []
    for email in emails:
        attendees.append({'email': email.strip()})
    print("Attendees:", attendees)
    # get user's emails that are in the channel
    event = {
        "summary": "Test event to schedule a retro",
        "description": "This is a test event to schedule a retro",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        'attendees': attendees,
        'conferenceData': {
            'createRequest': {
                'requestId': f"{start.timestamp()}",  # Unique ID per event to avoid collisions
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'  # This automatically generates a Google Meet link
                },
            }
        },
        # Optionally, you can set 'sendNotifications': True to send email notifications to the guests
        'reminders': {
            'useDefault': False,
            'overrides': [
            {'method': 'popup', 'minutes': 10},
            ],
        },
    }
    event = service.events().insert(calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates='all').execute()
    print(f"Event created: {event.get('htmlLink')}")
    return event.get('htmlLink')


def find_first_available_slot(freebusy_response, duration_minutes=30, days_in_future=3, search_days_limit=60):
    # EST timezone
    est = pytz.timezone('US/Eastern')

    # Combine all busy times into a single list and sort them
    busy_times = []
    for calendar in freebusy_response['calendars'].values():
        for busy_period in calendar['busy']:
            start = datetime.strptime(busy_period['start'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC).astimezone(est)
            end = datetime.strptime(busy_period['end'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=pytz.UTC).astimezone(est)
            busy_times.append((start, end))
    busy_times.sort(key=lambda x: x[0])

    for day_offset in range(days_in_future, days_in_future + search_days_limit):
        # Calculate the start and end times of the search window for the current day
        search_date = datetime.now(tz=est) + timedelta(days=day_offset)

        # Check if the day is Saturday (5) or Sunday (6) and skip it
        if search_date.weekday() in [5, 6]:
            continue
        
        search_start = search_date.replace(hour=13, minute=0, second=0, microsecond=0)  # 1 PM EST
        search_end = search_date.replace(hour=15, minute=0, second=0, microsecond=0)    # 3 PM EST

        # Attempt to find an available slot within this day's search window
        for current_time in (search_start + timedelta(minutes=i) for i in range(0, 121, duration_minutes)):
            slot_end = current_time + timedelta(minutes=duration_minutes)
            if all(slot_end <= start or current_time >= end for start, end in busy_times):
                if slot_end <= search_end:
                    return current_time, slot_end

    return None, None  # No available slot found after searching the limit