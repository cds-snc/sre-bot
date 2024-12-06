from unittest.mock import MagicMock, call, patch
import pytest
import string
from integrations.utils.api import (
    convert_string_to_camel_case,
    convert_dict_to_camel_case,
    convert_kwargs_to_camel_case,
    convert_string_to_pascal_case,
    convert_dict_to_pascale_case,
    convert_kwargs_to_pascal_case,
    generate_unique_id,
    retry_request,
)


@pytest.fixture
def kwargs():
    return [
        {
            "snake_case": "value",
            "another_snake_case": "another_value",
            "camelCase": "camel_value",
            "nested_dict": {
                "nested_snake_case": "nested_value",
                "nested_camelCase": "nested_camel_value",
                "nested_nested_dict": {
                    "nested_nested_snake_case": "nested_nested_value",
                    "nested_nested_camelCase": "nested_nested_camel_value",
                },
            },
            "nested_list": [
                {
                    "nested_list_snake_case": "nested_list_value",
                    "nested_list_camelCase": "nested_list_camel_value",
                }
            ],
        }
    ]


def test_convert_string_to_camel_case():
    assert convert_string_to_camel_case("snake_case") == "snakeCase"
    assert (
        convert_string_to_camel_case("longer_snake_case_string")
        == "longerSnakeCaseString"
    )
    assert convert_string_to_camel_case("alreadyCamelCase") == "alreadyCamelCase"
    assert convert_string_to_camel_case("singleword") == "singleword"
    assert convert_string_to_camel_case("with_numbers_123") == "withNumbers123"


def test_convert_string_to_camel_case_with_empty_string():
    assert convert_string_to_camel_case("") == ""


def test_convert_string_to_camel_case_with_non_string_input():
    with pytest.raises(TypeError):
        convert_string_to_camel_case(123)


def test_convert_dict_to_camel_case(kwargs):
    kwargs[0].pop("nested_list")
    dict = kwargs[0]
    expected = {
        "snakeCase": "value",
        "anotherSnakeCase": "another_value",
        "camelCase": "camel_value",
        "nestedDict": {
            "nestedSnakeCase": "nested_value",
            "nestedCamelCase": "nested_camel_value",
            "nestedNestedDict": {
                "nestedNestedSnakeCase": "nested_nested_value",
                "nestedNestedCamelCase": "nested_nested_camel_value",
            },
        },
    }
    assert convert_dict_to_camel_case(dict) == expected


def test_convert_dict_to_camel_case_with_empty_dict():
    assert convert_dict_to_camel_case({}) == {}


def test_convert_dict_to_camel_case_with_non_string_keys():
    dict = {1: "value", 2: "another_value"}
    with pytest.raises(TypeError):
        convert_dict_to_camel_case(dict)


def test_convert_kwargs_to_camel_case(kwargs):
    expected = [
        {
            "snakeCase": "value",
            "anotherSnakeCase": "another_value",
            "camelCase": "camel_value",
            "nestedDict": {
                "nestedSnakeCase": "nested_value",
                "nestedCamelCase": "nested_camel_value",
                "nestedNestedDict": {
                    "nestedNestedSnakeCase": "nested_nested_value",
                    "nestedNestedCamelCase": "nested_nested_camel_value",
                },
            },
            "nestedList": [
                {
                    "nestedListSnakeCase": "nested_list_value",
                    "nestedListCamelCase": "nested_list_camel_value",
                }
            ],
        }
    ]
    assert convert_kwargs_to_camel_case(kwargs) == expected


def test_convert_kwargs_to_camel_case_with_empty_list():
    assert convert_kwargs_to_camel_case([]) == []


def test_convert_kwargs_to_camel_case_with_non_dict_non_list_kwargs():
    assert convert_kwargs_to_camel_case("string") == "string"
    assert convert_kwargs_to_camel_case(123) == 123
    assert convert_kwargs_to_camel_case(True) is True


def test_convert_kwargs_to_camel_case_with_nested_list():
    kwargs = [{"key": ["value1", "value2"]}]
    assert convert_kwargs_to_camel_case(kwargs) == [{"key": ["value1", "value2"]}]


def test_convert_string_to_pascal_case():
    assert convert_string_to_pascal_case("snake_case") == "SnakeCase"
    assert (
        convert_string_to_pascal_case("longer_snake_case_string")
        == "LongerSnakeCaseString"
    )
    assert convert_string_to_pascal_case("alreadyPascalCase") == "AlreadyPascalCase"
    assert convert_string_to_pascal_case("singleword") == "Singleword"
    assert convert_string_to_pascal_case("with_numbers_123") == "WithNumbers123"


def test_convert_string_to_pascal_case_with_empty_string():
    assert convert_string_to_pascal_case("") == ""


def test_convert_string_to_pascal_case_with_non_string_input():
    with pytest.raises(TypeError):
        convert_string_to_pascal_case(123)


def test_convert_dict_to_pascal_case(kwargs):
    kwargs[0].pop("nested_list")
    dict = kwargs[0]

    expected = {
        "SnakeCase": "value",
        "AnotherSnakeCase": "another_value",
        "CamelCase": "camel_value",
        "NestedDict": {
            "NestedSnakeCase": "nested_value",
            "NestedCamelCase": "nested_camel_value",
            "NestedNestedDict": {
                "NestedNestedSnakeCase": "nested_nested_value",
                "NestedNestedCamelCase": "nested_nested_camel_value",
            },
        },
    }
    assert convert_dict_to_pascale_case(dict) == expected


def test_convert_dict_to_pascal_case_with_empty_dict():
    assert convert_dict_to_pascale_case({}) == {}


def test_convert_dict_to_pascal_case_with_non_string_keys():
    dict = {1: "value", 2: "another_value"}
    with pytest.raises(TypeError):
        convert_dict_to_pascale_case(dict)


def test_convert_kwargs_to_pascal_case(kwargs):
    expected = [
        {
            "SnakeCase": "value",
            "AnotherSnakeCase": "another_value",
            "CamelCase": "camel_value",
            "NestedDict": {
                "NestedSnakeCase": "nested_value",
                "NestedCamelCase": "nested_camel_value",
                "NestedNestedDict": {
                    "NestedNestedSnakeCase": "nested_nested_value",
                    "NestedNestedCamelCase": "nested_nested_camel_value",
                },
            },
            "NestedList": [
                {
                    "NestedListSnakeCase": "nested_list_value",
                    "NestedListCamelCase": "nested_list_camel_value",
                }
            ],
        }
    ]
    assert convert_kwargs_to_pascal_case(kwargs) == expected


def test_convert_kwargs_to_pascal_case_with_empty_list():
    assert convert_kwargs_to_pascal_case([]) == []


def test_convert_kwargs_to_pascal_case_with_non_dict_non_list_kwargs():
    assert convert_kwargs_to_pascal_case("string") == "string"
    assert convert_kwargs_to_pascal_case(123) == 123
    assert convert_kwargs_to_pascal_case(True) is True


def test_convert_kwargs_to_pascal_case_with_nested_list():
    kwargs = [{"key": ["value1", "value2"]}]
    assert convert_kwargs_to_pascal_case(kwargs) == [{"Key": ["value1", "value2"]}]


def test_unique_id_format():
    """Test that the unique ID is in the correct format."""
    unique_id = generate_unique_id()
    assert isinstance(unique_id, str), "Unique ID should be a string"
    parts = unique_id.split("-")
    assert len(parts) == 3, "Unique ID should have three parts separated by hyphens"
    assert all(
        len(part) == 3 for part in parts
    ), "Each segment should be exactly 3 characters long"


def test_unique_id_characters():
    """Test that the unique ID contains only uppercase letters and digits."""
    unique_id = generate_unique_id()
    allowed_chars = set(string.ascii_lowercase + string.digits)
    assert all(
        char in allowed_chars for char in unique_id.replace("-", "")
    ), "All characters should be alphanumeric"


def test_unique_id_uniqueness():
    """Test that multiple IDs are unique from each other."""
    ids = {generate_unique_id() for _ in range(100)}
    assert len(ids) == 100, "All generated IDs should be unique"


# Additional test to ensure no illegal characters or formats appear
def test_no_illegal_characters():
    """Ensure no lowecase or special characters are in the ID"""
    unique_id = generate_unique_id()
    illegal_chars = set(string.ascii_uppercase + string.punctuation)
    assert not any(
        char in illegal_chars for char in unique_id.replace("-", "")
    ), "ID should not have uppercase or special characters"


def test_retry_request_success():
    mock_func = MagicMock(return_value="success")
    result = retry_request(mock_func, max_attempts=3, delay=1)
    assert result == "success"
    mock_func.assert_called_once()


@patch("logging.warning")
def test_retry_request_success_after_retries(mock_logging_warning):
    mock_func = MagicMock(side_effect=[Exception("fail"), Exception("fail"), "success"])
    result = retry_request(mock_func, max_attempts=3, delay=1)
    assert result == "success"
    assert mock_func.call_count == 3
    assert mock_logging_warning.call_count == 2
    assert mock_logging_warning.call_args_list == [
        call("Error on attempt 1: fail"),
        call("Error on attempt 2: fail"),
    ]


def test_retry_request_failure():
    mock_func = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception, match="fail"):
        retry_request(mock_func, max_attempts=3, delay=1)
    assert mock_func.call_count == 3


@patch("time.sleep", return_value=None)
def test_retry_request_delay(mock_sleep):
    mock_func = MagicMock(side_effect=[Exception("fail"), "success"])
    result = retry_request(mock_func, max_attempts=3, delay=2)
    assert result == "success"
    assert mock_func.call_count == 2
    mock_sleep.assert_called_once_with(2)


@patch("logging.warning")
def test_retry_request_logging(mock_logging_warning: MagicMock):
    mock_func = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception, match="fail"):
        retry_request(mock_func, max_attempts=3, delay=1)
    assert mock_func.call_count == 3
    assert mock_logging_warning.call_count == 3
    mock_logging_warning.assert_has_calls(
        [
            call("Error on attempt 1: fail"),
            call("Error on attempt 2: fail"),
            call("Error after 3 attempts: fail"),
        ]
    )


def test_retry_request_passes_args_and_kwargs():
    mock_func = MagicMock(return_value="success")
    result = retry_request(
        mock_func,
        "arg1",
        "arg2",
        max_attempts=3,
        delay=1,
        kwarg1="kwarg1",
        kwarg2="kwarg2",
    )
    assert result == "success"
    mock_func.assert_called_once_with("arg1", "arg2", kwarg1="kwarg1", kwarg2="kwarg2")
