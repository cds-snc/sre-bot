"""Unit tests for models.utils module.

Tests the model parameter extraction, validation, and best-model selection logic
without external dependencies.
"""

from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

import models.utils as model_utils


# Test Models
class MockModel(BaseModel):
    """Test model with required fields."""

    field1: str
    field2: int
    field3: float


class EmptyModel(BaseModel):
    """Test model with no fields."""

    pass


class MockModelA(BaseModel):
    """Test model with required and optional fields."""

    field1: str
    field2: Optional[int] = None


class MockModelB(BaseModel):
    """Test model with different optional fields."""

    field3: float
    field4: Optional[str] = None


class MockModelC(BaseModel):
    """Test model with optional boolean field."""

    field1: str
    field5: Optional[bool] = None


class MockModelD(BaseModel):
    """Test model with all optional fields."""

    field1: Optional[str] = None
    field2: Optional[int] = None
    field3: Optional[float] = None
    field4: Optional[str] = None
    field5: Optional[bool] = None


# Fixtures
@pytest.fixture
def make_payload():
    """Factory for creating test payloads with customizable fields."""

    def _make(**fields):
        return fields

    return _make


@pytest.fixture
def sample_models():
    """Fixture providing standard test models."""
    return [MockModelA, MockModelB, MockModelC]


# get_parameters_from_model Tests
@pytest.mark.unit
def test_should_extract_parameters_from_model_with_fields():
    """Test that get_parameters_from_model extracts all field names."""
    # Arrange
    expected = ["field1", "field2", "field3"]

    # Act
    result = model_utils.get_parameters_from_model(MockModel)

    # Assert
    assert result == expected


@pytest.mark.unit
def test_should_return_empty_list_when_model_has_no_fields():
    """Test that empty models return empty parameter list."""
    # Arrange
    expected = []

    # Act
    result = model_utils.get_parameters_from_model(EmptyModel)

    # Assert
    assert result == expected


# get_dict_of_parameters_from_models Tests
@pytest.mark.unit
def test_should_extract_parameters_from_multiple_models():
    """Test that get_dict_of_parameters_from_models extracts from all models."""
    # Arrange
    models = [MockModel, EmptyModel]
    expected = {"MockModel": ["field1", "field2", "field3"], "EmptyModel": []}

    # Act
    result = model_utils.get_dict_of_parameters_from_models(models)

    # Assert
    assert result == expected


# is_parameter_in_model Tests
@pytest.mark.unit
@pytest.mark.parametrize(
    "model_params,payload,expected",
    [
        (
            ["field1", "field2", "field3"],
            {"field1": "value", "non_field": "value"},
            True,
        ),
        (
            ["field1", "field2", "field3"],
            {"non_field1": "value", "non_field2": "value"},
            False,
        ),
        (["field1", "field2", "field3"], {}, False),
        (
            ["field1", "field2", "field3"],
            {"field1": "value"},
            True,
        ),
        (["field1", "field2", "field3"], {1: "value", 2: "value"}, False),
    ],
    ids=[
        "when_field_exists_with_other_keys",
        "when_no_matching_fields",
        "when_payload_empty",
        "when_single_matching_field",
        "when_payload_has_non_string_keys",
    ],
)
def test_should_check_parameter_existence(model_params, payload, expected):
    """Test is_parameter_in_model with various payload combinations."""
    # Act
    result = model_utils.is_parameter_in_model(model_params, payload)

    # Assert
    assert result == expected


# has_parameters_in_model Tests
@pytest.mark.unit
@pytest.mark.parametrize(
    "model_params,payload,expected",
    [
        (["field1", "field2", "field3"], {"field1": "value", "field2": "value"}, 2),
        (["field1", "field2", "field3"], {"field1": "value", "non_field": "value"}, 1),
        (["field1", "field2", "field3"], {}, 0),
        (["field1", "field2", "field3"], {"field1": "value"}, 1),
        (["field1", "field2", "field3"], {1: "value", 2: "value"}, 0),
    ],
    ids=[
        "when_multiple_fields_match",
        "when_single_field_matches",
        "when_no_fields_match",
        "when_one_field_matches",
        "when_payload_has_non_string_keys",
    ],
)
def test_should_count_matching_parameters(model_params, payload, expected):
    """Test has_parameters_in_model counts matching fields correctly."""
    # Act
    result = model_utils.has_parameters_in_model(model_params, payload)

    # Assert
    assert result == expected


# are_all_parameters_in_model Tests
@pytest.mark.unit
@pytest.mark.parametrize(
    "model_params,payload,expected",
    [
        (
            ["field1", "field2", "field3"],
            {"field1": "value", "field2": "value"},
            True,
        ),
        (
            ["field1", "field2", "field3"],
            {"field1": "value", "non_field": "value"},
            False,
        ),
        (["field1", "field2", "field3"], {}, True),
        (["field1", "field2", "field3"], {"field1": "value"}, True),
        (["field1", "field2", "field3"], {1: "value", 2: "value"}, False),
    ],
    ids=[
        "when_all_fields_match",
        "when_extra_non_matching_keys",
        "when_payload_empty",
        "when_subset_of_fields_match",
        "when_payload_has_non_string_keys",
    ],
)
def test_should_validate_all_parameters_in_model(model_params, payload, expected):
    """Test are_all_parameters_in_model validates all required parameters."""
    # Act
    result = model_utils.are_all_parameters_in_model(model_params, payload)

    # Assert
    assert result == expected


# select_best_model Tests
@pytest.mark.unit
def test_should_select_model_with_exact_match():
    """Test that select_best_model chooses model with exact field matches."""
    # Arrange
    data = {"field1": "value", "field2": 123}
    models = [MockModelA, MockModelB, MockModelC]

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelA
    assert isinstance(instance, MockModelA)


@pytest.mark.unit
def test_should_select_model_with_partial_match():
    """Test that select_best_model handles partial field matches."""
    # Arrange
    data = {"field1": "value"}
    models = [MockModelA, MockModelB, MockModelC]

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelA
    assert isinstance(instance, MockModelA)


@pytest.mark.unit
def test_should_apply_priority_when_selecting_model():
    """Test that select_best_model respects priority weights."""
    # Arrange
    data = {"field1": "value"}
    models = [MockModelA, MockModelB, MockModelC]
    priorities = {MockModelC: 10}

    # Act
    result = model_utils.select_best_model(data, models, priorities)

    # Assert
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelC
    assert isinstance(instance, MockModelC)


@pytest.mark.unit
def test_should_return_none_when_no_model_matches():
    """Test that select_best_model returns None for unmatched data."""
    # Arrange
    data = {"unknown_field": "value"}
    models = [MockModelA, MockModelB, MockModelC, MockModelD]

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is None


@pytest.mark.unit
def test_should_return_none_for_empty_data():
    """Test that select_best_model returns None when data is empty."""
    # Arrange
    data = {}
    models = [MockModelA, MockModelB, MockModelC]

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is None


@pytest.mark.unit
@patch("models.utils.logger")
def test_should_log_warning_when_no_model_matches(mock_logger):
    """Test that select_best_model logs warning for unmatched payloads."""
    # Arrange
    data = {"unknown_field": "value"}
    models = [MockModelA, MockModelB, MockModelC]
    mock_bound_logger = MagicMock()
    mock_logger.bind.return_value = mock_bound_logger

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is None
    mock_logger.bind.assert_called_once()
    bind_call_kwargs = mock_logger.bind.call_args[1]
    assert "model_count" in bind_call_kwargs
    assert bind_call_kwargs["model_count"] == 3
    assert "data_keys" in bind_call_kwargs
    mock_bound_logger.warning.assert_called_once()


@pytest.mark.unit
@patch("models.utils.log_ops_message")
def test_should_notify_ops_when_no_model_matches(mock_log_ops):
    """Test that select_best_model sends ops notification for invalid payloads."""
    # Arrange
    data = {"unknown_field": "value"}
    models = [MockModelA, MockModelB]

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is None
    mock_log_ops.assert_called_once()
    call_arg = mock_log_ops.call_args[0][0]
    assert "invalid" in call_arg.lower()
    assert str(data) in call_arg


@pytest.mark.unit
def test_should_skip_invalid_models_when_selecting():
    """Test that select_best_model skips models that fail validation."""

    # Arrange
    class TypeMismatchModel(BaseModel):
        field1: int  # Expects int but data has string

    data = {"field1": "value"}
    models = [TypeMismatchModel, MockModelC]

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is not None
    model_class, instance = result
    assert model_class is MockModelC


@pytest.mark.unit
def test_should_prefer_model_with_more_matching_required_fields():
    """Test that select_best_model prioritizes required field matches."""
    # Arrange
    data = {"field1": "value", "field3": 1.5}
    models = [
        MockModelA,  # Has field1 (required)
        MockModelB,  # Has field3 (required)
        MockModelC,  # Has field1 and field5 (optional)
    ]

    # Act
    result = model_utils.select_best_model(data, models)

    # Assert
    assert result is not None
    model_class, instance = result
    # Should select either A or C (both have field1), but C adds field5 which is optional
    # The exact selection depends on scoring
    assert model_class in [MockModelA, MockModelC]
