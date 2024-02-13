from unittest.mock import MagicMock
from modules.incident import handle_slack_message_reactions


def test_basic_functionality_rearrange_by_datetime_ascending():
    input_text = "2024-01-01 10:00:00 ET Message A\n" "2024-01-02 11:00:00 ET Message B"
    expected_output = (
        "2024-01-01 10:00:00 ET Message A\n" "2024-01-02 11:00:00 ET Message B"
    )
    assert handle_slack_message_reactions.rearrange_by_datetime_ascending(input_text) == expected_output


def test_multiline_entries_rearrange_by_datetime_ascending():
    input_text = (
        "2024-01-01 10:00:00 ET Message A\nContinued\n"
        "2024-01-02 11:00:00 ET Message B"
    )
    expected_output = (
        "2024-01-01 10:00:00 ET Message A\nContinued\n"
        "2024-01-02 11:00:00 ET Message B"
    )
    assert handle_slack_message_reactions.rearrange_by_datetime_ascending(input_text) == expected_output


def test_entries_out_of_order_rearrange_by_datetime_ascending():
    input_text = "2024-01-02 11:00:00 ET Message B\n" "2024-01-01 10:00:00 ET Message A"
    expected_output = (
        "2024-01-01 10:00:00 ET Message A\n" "2024-01-02 11:00:00 ET Message B"
    )
    assert handle_slack_message_reactions.rearrange_by_datetime_ascending(input_text) == expected_output


def test_invalid_entries_rearrange_by_datetime_ascending():
    input_text = "Invalid Entry\n" "2024-01-01 10:00:00 ET Message A"
    expected_output = "2024-01-01 10:00:00 ET Message A"
    assert handle_slack_message_reactions.rearrange_by_datetime_ascending(input_text) == expected_output


def test_empty_input_rearrange_by_datetime_ascending():
    assert handle_slack_message_reactions.rearrange_by_datetime_ascending("") == ""


def test_no_datetime_entries_rearrange_by_datetime_ascending():
    input_text = "Message without datetime\nAnother message"
    assert handle_slack_message_reactions.rearrange_by_datetime_ascending(input_text) == ""


def test_convert_epoch_to_datetime_est_known_epoch_time():
    # Example: 0 epoch time corresponds to 1969-12-31 19:00:00 EST
    assert handle_slack_message_reactions.convert_epoch_to_datetime_est(0) == "1969-12-31 19:00:00 ET"


def test_convert_epoch_to_datetime_est_daylight_saving_time_change():
    # Test with an epoch time known to fall in DST transition
    # For example, 1583652000 corresponds to 2020-03-08 03:20:00 EST
    assert handle_slack_message_reactions.convert_epoch_to_datetime_est(1583652000) == "2020-03-08 03:20:00 ET"


def test_convert_epoch_to_datetime_est_current_epoch_time():
    time = MagicMock()
    time.return_value = 1609459200
    current_est = handle_slack_message_reactions.convert_epoch_to_datetime_est(time)
    assert current_est == "1969-12-31 19:00:01 ET"


def test_convert_epoch_to_datetime_est_edge_cases():
    # Test with the epoch time at 0
    assert handle_slack_message_reactions.convert_epoch_to_datetime_est(0) == "1969-12-31 19:00:00 ET"
    # Test with a very large epoch time, for example
    assert handle_slack_message_reactions.convert_epoch_to_datetime_est(32503680000) == "2999-12-31 19:00:00 ET"
