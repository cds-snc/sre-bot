import pytest
from integrations.utils.api import (
    convert_string_to_camel_case,
    convert_dict_to_camel_case,
    convert_kwargs_to_camel_case,
)


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


def test_convert_dict_to_camel_case():
    dict = {
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
    }

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


def test_convert_kwargs_to_camel_case():
    kwargs = [
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
