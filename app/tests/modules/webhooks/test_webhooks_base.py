from unittest.mock import patch, ANY
from modules.webhooks import base
from pydantic import BaseModel


@patch("modules.webhooks.base.logger")
@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_returns_model_if_valid(mock_select_best_model, mock_logger):
    payload = {"text": "Test"}

    class MockModel(BaseModel):
        text: str

    mock_select_best_model.return_value = (
        MockModel,
        MockModel(text="validated_payload"),
    )

    validated = base.validate_payload(payload)

    mock_select_best_model.assert_called_once_with(
        payload,
        ANY,  # models list
        None,  # priorities argument
    )
    assert validated == (MockModel, MockModel(text="validated_payload"))
    mock_logger.info.assert_called_once_with(
        "payload_validation_success",
        model="MockModel",
        payload={"text": "validated_payload"},
    )


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_returns_none_if_invalid(mock_select_best_model):
    payload = {"unknown_field": "value"}
    mock_select_best_model.return_value = None

    validated = base.validate_payload(payload)

    mock_select_best_model.assert_called_once_with(
        payload,
        ANY,  # models list
        None,  # priorities argument
    )
    assert validated is None
