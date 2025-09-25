from unittest.mock import patch, ANY
from modules.webhooks import base


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_returns_model_if_valid(mock_select_best_model):
    payload = {"id": 1, "name": "Test"}
    mock_select_best_model.return_value = "model", "validated_payload"

    validated = base.validate_payload(payload)

    mock_select_best_model.assert_called_once_with(
        payload,
        ANY,
        None,
    )
    assert validated == ("model", "validated_payload")


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_returns_none_if_invalid(mock_select_best_model):
    payload = {"unknown_field": "value"}
    mock_select_best_model.return_value = None
    validated = base.validate_payload(payload)
    assert validated is None
