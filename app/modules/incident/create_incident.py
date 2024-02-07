"""Create Incident Module

This module is responsible for creating a new incident based on the key metadata provided by the user.

It will:
- Create the record in the database (Google Sheet for now)
- Create the new incident document (Google Doc)
- Create an incident channel in Slack
- Setup a Google Meet for the incident
- Send a notification to the incident channel
- Add the default users to the incident channel
"""