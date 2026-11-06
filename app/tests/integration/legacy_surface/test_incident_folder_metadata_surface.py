"""Pinning tests for the Slack editor of product-folder metadata, which the rebuild deletes.

Every test is named ``legacy_only_``: the product's on-call schedule reference moves to the
bot's own product list and the editor is deleted with the legacy incident module. The
tests are thin, one per interaction. Each opens the folder list with
``/sre incident product list``, then walks the modals using the action ids, callback ids,
block ids and private metadata read from the recorded view payloads, so no modal-internal
id is hard-coded. The external edges are faked: the Slack Web API and the Google Drive
service. Outcomes are asserted at the Drive edge (the folder's ``appProperties``, the
``genie_schedule`` key being the one the on-call schedule is read from) and in what the
modals show.
"""

from typing import Any

import pytest

from features.incident.common.settings import get_incident_core_settings

from .conftest import (
    IncidentSurface,
    click_payload,
    last_view,
    submission_payload,
    view_button,
    view_text,
)

pytestmark = pytest.mark.integration

FOLDER = "F0PLATFORM"


@pytest.fixture
def surface(incident_surface: IncidentSurface) -> IncidentSurface:
    """The incident surface with a Platform product folder carrying a ``genie_schedule`` and a Forms folder with none."""
    parent = get_incident_core_settings().folder_id
    incident_surface.google.drive.add(FOLDER, "Platform", parent=parent, folder=True, genie_schedule="platform-schedule")
    incident_surface.google.drive.add("F0FORMS", "Forms", parent=parent, folder=True)
    return incident_surface


def open_folder_list(surface: IncidentSurface) -> dict[str, Any]:
    surface.sre("incident product list")
    return last_view(surface.slack.client)


def open_metadata(surface: IncidentSurface) -> dict[str, Any]:
    """Open the folder list, then the Platform folder's metadata modal."""
    folders = open_folder_list(surface)
    surface.slack.interaction(click_payload(folders, view_button(folders, value=FOLDER)))
    return last_view(surface.slack.client)


def test_legacy_only_product_list_shows_the_folders_by_name_up_to_twenty_five(surface: IncidentSurface) -> None:
    """The command opens a loading modal, then fills it with the product folders sorted by name, at most 25."""
    for number in range(30):
        surface.google.drive.add(
            f"F0EXTRA{number:02}", f"Extra {number:02}", parent=get_incident_core_settings().folder_id, folder=True
        )

    response = surface.sre("incident product list")

    assert (response.status, response.body) == (200, "")
    [opened] = surface.slack.client.calls_to("views_open")
    assert "Loading products" in view_text(opened["view"])
    [filled] = surface.slack.client.calls_to("views_update")
    assert filled["view_id"] == "VFAKE"
    names = [block["text"]["text"] for block in filled["view"]["blocks"] if block["type"] == "section"]
    assert len(names) == 25
    assert names == sorted(names)
    assert names[:3] == ["*Extra 00*", "*Extra 01*", "*Extra 02*"]


def test_legacy_only_manage_metadata_shows_the_folders_properties(surface: IncidentSurface) -> None:
    """Pressing a folder's button replaces the list with that folder's name and its stored key and value."""
    folders = open_folder_list(surface)

    response = surface.slack.interaction(click_payload(folders, view_button(folders, value=FOLDER)))

    assert (response.status, response.body) == (200, "")
    [*_, update] = surface.slack.client.calls_to("views_update")
    assert update["view_id"] == "V0OPEN"
    assert update["view"]["title"]["text"] == "SRE - Showing metadata"
    assert view_text(update["view"]) == "Platform\n*genie_schedule*\nplatform-schedule"


def test_legacy_only_add_metadata_stores_the_property_on_the_folder(surface: IncidentSurface) -> None:
    """The add button opens the key and value form; submitting it sets the folder's property and shows it."""
    metadata = open_metadata(surface)

    surface.slack.interaction(click_payload(metadata, view_button(metadata, value=FOLDER)))
    form = last_view(surface.slack.client)
    response = surface.slack.interaction(submission_payload(form, {"key": "genie_schedule", "value": "new-schedule"}))

    assert (response.status, response.body) == (200, "")
    assert surface.google.drive.properties(FOLDER) == {"genie_schedule": "new-schedule"}
    assert view_text(last_view(surface.slack.client)) == "Platform\n*genie_schedule*\nnew-schedule"


def test_legacy_only_delete_metadata_removes_the_property_from_the_folder(surface: IncidentSurface) -> None:
    """The delete button removes the property at Drive and the metadata modal then reports none."""
    metadata = open_metadata(surface)

    response = surface.slack.interaction(click_payload(metadata, view_button(metadata, value="genie_schedule")))

    assert (response.status, response.body) == (200, "")
    assert surface.google.drive.properties(FOLDER) == {}
    assert "No metadata found" in view_text(last_view(surface.slack.client))


def test_legacy_only_returning_from_the_metadata_modal_lists_the_folders_again(surface: IncidentSurface) -> None:
    """Submitting the metadata modal (its return button) opens the folder list again."""
    metadata = open_metadata(surface)
    surface.slack.client.calls.clear()

    response = surface.slack.interaction(submission_payload(metadata, {}))

    assert (response.status, response.body) == (200, "")
    [filled] = surface.slack.client.calls_to("views_update")
    assert [block["text"]["text"] for block in filled["view"]["blocks"] if block["type"] == "section"] == [
        "*Forms*",
        "*Platform*",
    ]
