from pydantic import BaseModel
import models.utils as model_utils


class MockModel(BaseModel):
    field1: str
    field2: int
    field3: float


class EmptyModel(BaseModel):
    pass


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
