"""Incident Management Process Module

This module contains the functions used to manage the Incident Management Process.
"""


def new_incident_request():
    # open the modal to request a new incident to be created
    pass


def create(title, folder, product, locale="en-US"):
    """Create New Incident

    This function is responsible for creating a new incident based on the key metadata provided by the user.

    It can be triggered upon successfully completing an incident request in Slack modal or via a web form calling the bot's designated API.

    It will:
    - Create the record in the database (Google Sheet for now)
    - Create the new incident document (Google Doc)
    - Create an incident channel in Slack with:
       - channel name
       - description
       - instructions
       - default users
    - Setup a Google Meet for the incident
    - Send a notification to the incident channel
    - Add the default users to the incident channel

    Args:
    """
    pass


def update_status():
    # status can be open, resolved, closed
    pass


def close():
    # closing an incident means that the incident is no longer active and is closed. It will trigger a series of steps to close the incident and notify the relevant stakeholders
    pass
