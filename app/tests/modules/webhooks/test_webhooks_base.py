import json
from typing import Optional
from unittest.mock import patch

from modules.webhooks import base
from pydantic import BaseModel


class ModelA(BaseModel):
    id: int
    name: str


class ModelB(BaseModel):
    title: str
    description: str


class ModelC(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]


class ModelD(BaseModel):
    id: int
    title: Optional[str]
    department: Optional[str]


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_no_models(mock_select_best_model):
    mock_select_best_model.return_value = (ModelA, ModelA(id=1, name="Test"))
    models = None
    payload = {"id": 1, "name": "Test"}

    validated = base.validate_payload(payload, models)

    mock_select_best_model.assert_not_called()
    assert validated == None


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_valid_dict(mock_select_best_model):
    mock_select_best_model.return_value = (ModelA, ModelA(id=1, name="Test"))
    models = [ModelA, ModelB]
    payload = {"id": 1, "name": "Test"}

    validated = base.validate_payload(payload, models)

    mock_select_best_model.assert_called_once_with(payload, models, None)
    assert validated == (ModelA, ModelA(id=1, name="Test"))


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_valid_json(mock_select_best_model):
    mock_select_best_model.return_value = (
        ModelB,
        ModelB(title="Hello", description="World"),
    )
    models = [ModelA, ModelB]
    payload = '{"title": "Hello", "description": "World"}'

    validated = base.validate_payload(payload, models)

    mock_select_best_model.assert_called_once_with(
        {"title": "Hello", "description": "World"}, models, None
    )
    assert validated == (ModelB, ModelB(title="Hello", description="World"))


@patch("modules.webhooks.base.select_best_model")
@patch("modules.webhooks.base.json.loads")
def test_validate_payload_invalid_json(mock_json_loads, mock_select_best_model):
    models = [ModelA, ModelB]
    payload = '{"id": 3, "name": "Invalid JSON"}'

    mock_json_loads.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    validated = base.validate_payload(payload, models)

    mock_select_best_model.assert_not_called()
    assert validated is None


@patch("modules.webhooks.base.select_best_model")
def test_validate_payload_invalid_type(mock_select_best_model):
    models = [ModelA, ModelB]
    payload = ["id", 1, "name", "Test"]

    validated = base.validate_payload(payload, models)

    mock_select_best_model.assert_not_called()
    assert validated is None
