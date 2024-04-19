"""Utilities for API integrations."""


def convert_string_to_camel_case(snake_str):
    """Convert a snake_case string to camelCase."""
    if not isinstance(snake_str, str):
        raise TypeError("Input must be a string")
    components = snake_str.split("_")
    if len(components) == 1:
        return components[0]
    else:
        return components[0] + "".join(
            x[0].upper() + x[1:] if x else "" for x in components[1:]
        )


def convert_dict_to_camel_case(dict):
    """Convert all keys in a dictionary from snake_case to camelCase."""
    new_dict = {}
    for k, v in dict.items():
        new_key = convert_string_to_camel_case(k)
        new_dict[new_key] = convert_kwargs_to_camel_case(v)
    return new_dict


def convert_kwargs_to_camel_case(kwargs):
    """Convert all keys in a list of dictionaries from snake_case to camelCase."""
    if isinstance(kwargs, dict):
        return convert_dict_to_camel_case(kwargs)
    elif isinstance(kwargs, list):
        return [convert_kwargs_to_camel_case(i) for i in kwargs]
    else:
        return kwargs
