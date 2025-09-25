from typing import Optional
from unittest.mock import patch

import models.utils as model_utils
from pydantic import BaseModel


class MockModel(BaseModel):
    field1: str
    field2: int
    field3: float


class EmptyModel(BaseModel):
    pass


class MockModelA(BaseModel):
    field1: str
    field2: Optional[int] = None


class MockModelB(BaseModel):
    field3: float
    field4: Optional[str] = None


class MockModelC(BaseModel):
    field1: str
    field5: Optional[bool] = None


def test_get_parameters_from_model():
    expected = ["field1", "field2", "field3"]
    result = model_utils.get_parameters_from_model(MockModel)
    assert result == expected

    expected_empty = []
    result_empty = model_utils.get_parameters_from_model(EmptyModel)
    assert result_empty == expected_empty


def test_get_dict_of_parameters_from_models():
    models = [MockModel, EmptyModel]
    expected = {"MockModel": ["field1", "field2", "field3"], "EmptyModel": []}
    result = model_utils.get_dict_of_parameters_from_models(models)
    assert result == expected


def test_is_parameter_in_model():
    model_params = ["field1", "field2", "field3"]
    payload = {"field1": "value", "non_field": "value"}
    assert model_utils.is_parameter_in_model(model_params, payload)

    payload = {"non_field1": "value", "non_field2": "value"}
    assert not model_utils.is_parameter_in_model(model_params, payload)

    empty_payload = {}
    assert not model_utils.is_parameter_in_model(model_params, empty_payload)

    partial_payload = {"field1": "value"}
    assert model_utils.is_parameter_in_model(model_params, partial_payload)

    non_string_keys_payload = {1: "value", 2: "value"}
    assert not model_utils.is_parameter_in_model(model_params, non_string_keys_payload)


def test_has_parameters_in_model():
    model_params = ["field1", "field2", "field3"]

    payload = {"field1": "value", "field2": "value"}
    assert model_utils.has_parameters_in_model(model_params, payload) == 2

    payload = {"field1": "value", "non_field": "value"}
    assert model_utils.has_parameters_in_model(model_params, payload) == 1

    empty_payload = {}
    assert model_utils.has_parameters_in_model(model_params, empty_payload) == 0

    partial_payload = {"field1": "value"}
    assert model_utils.has_parameters_in_model(model_params, partial_payload) == 1

    non_string_keys_payload = {1: "value", 2: "value"}
    assert (
        model_utils.has_parameters_in_model(model_params, non_string_keys_payload) == 0
    )


def test_are_all_parameters_in_model():
    model_params = ["field1", "field2", "field3"]

    payload = {"field1": "value", "field2": "value"}
    assert model_utils.are_all_parameters_in_model(model_params, payload)

    payload = {"field1": "value", "non_field": "value"}
    assert not model_utils.are_all_parameters_in_model(model_params, payload)

    empty_payload = {}
    assert model_utils.are_all_parameters_in_model(model_params, empty_payload)

    partial_payload = {"field1": "value"}
    assert model_utils.are_all_parameters_in_model(model_params, partial_payload)

    non_string_keys_payload = {1: "value", 2: "value"}
    assert not model_utils.are_all_parameters_in_model(
        model_params, non_string_keys_payload
    )


def test_select_best_model_with_exact_match():
    data = {"field1": "value", "field2": 123}
    models = [MockModelA, MockModelB, MockModelC]
    result = model_utils.select_best_model(data, models)
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelA
    assert isinstance(instance, MockModelA)


def test_select_best_model_with_partial_match():
    data = {"field1": "value"}
    models = [MockModelA, MockModelB, MockModelC]
    result = model_utils.select_best_model(data, models)
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelA
    assert isinstance(instance, MockModelA)


def test_select_best_model_with_priorities():
    data = {"field1": "value"}
    models = [MockModelA, MockModelB, MockModelC]
    priorities = {MockModelC: 10}
    result = model_utils.select_best_model(data, models, priorities)
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelC
    assert isinstance(instance, MockModelC)


def test_select_best_model_with_no_match():
    data = {"unknown_field": "value"}
    models = [MockModelA, MockModelB, MockModelC]
    result = model_utils.select_best_model(data, models)
    assert result is None


def test_select_best_model_with_empty_data():
    data = {}
    models = [MockModelA, MockModelB, MockModelC]
    result = model_utils.select_best_model(data, models)
    assert result is None


def test_select_best_model_logs_warning_on_no_match():
    data = {"unknown_field": "value"}
    models = [MockModelA, MockModelB, MockModelC]

    with patch("models.utils.logger.warning") as mock_logger:
        result = model_utils.select_best_model(data, models)
        assert result is None
        mock_logger.assert_called_once_with(
            "invalid_model_detected",
            payload=str(data),
        )


def test_select_best_model_with_valid_and_invalid_models():
    class InvalidModel(BaseModel):
        field1: int

    data = {"field1": "value"}
    models = [InvalidModel, MockModelC]

    result = model_utils.select_best_model(data, models)
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelC
    assert isinstance(instance, MockModelC)
