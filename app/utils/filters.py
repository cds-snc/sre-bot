"""This module contains utility functions for filtering lists and dictionaries."""
from functools import reduce
import logging

logger = logging.getLogger(__name__)


def filter_by_condition(list, condition):
    """Filter a list by a condition, keeping only the items that satisfy the condition.
        Examples:

        filter_by_condition([1, 2, 3, 4, 5], lambda x: x % 2 == 0)
        Output: [2, 4]

    Args:
        list (list): The list to filter.
        condition (function): The condition to apply to the items in the list.

    Returns:
        list: A list containing the items that satisfy the condition.
    """
    return [item for item in list if condition(item)]


def get_nested_value(dictionary, key):
    """Get a nested value from a dictionary using a dot-separated key.

    Args:
        dictionary (dict): The dictionary to search.
        key (str): The dot-separated key to search for.

    Returns:
        The value of the nested key in the dictionary, or None if the key is not found.
    """
    if key in dictionary:
        return dictionary[key]
    try:
        return reduce(dict.get, key.split("."), dictionary)
    except TypeError:
        logger.error(f"Error getting nested value for key: {key}")
        return None


def compare_lists(source, target, mode="sync"):
    """Compares two lists and returns specific elements based on the comparison mode and keys provided.

    Args:
        `source (dict)`: Source data with `values` (list) and `key` (string).
        `target (dict)`: Target data with `values` (list) and `key` (string).
        `mode (str)`: Operation mode - `sync` or `match`.

         In `sync` mode (default), the function returns:

            1. Elements in the source list but not in the target list (to be added to the target).
            2. Elements in the target list but not in the source list (to be removed from the target).

        In `match` mode, the function returns:

            1. Elements present in both the source and target lists.

    Returns:
        tuple: Contains the elements as per the operation mode.
    """
    source_key = source.get("key", None)
    target_key = target.get("key", None)
    source_values = source.get("values", None)
    target_values = target.get("values", None)

    if not source_key or not target_key:
        return [], []

    filtered_source_values = {
        get_nested_value(value, source_key): value for value in source_values
    }
    filtered_target_values = {
        get_nested_value(value, target_key): value for value in target_values
    }

    if mode == "sync":
        values_to_add = [
            filtered_source_values[key]
            for key in filtered_source_values
            if key not in filtered_target_values
        ]
        values_to_remove = [
            filtered_target_values[key]
            for key in filtered_target_values
            if key not in filtered_source_values
        ]

        return values_to_add, values_to_remove

    elif mode == "match":
        matching_values = set(filtered_source_values.keys()) & set(
            filtered_target_values.keys()
        )

        filtered_source_groups = [
            filtered_source_values[value] for value in matching_values
        ]
        filtered_target_groups = [
            filtered_target_values[value] for value in matching_values
        ]

        filtered_source_groups.sort(key=lambda x: x[source_key])
        filtered_target_groups.sort(key=lambda x: x[target_key])

        return filtered_source_groups, filtered_target_groups


def get_unique_nested_dicts(source_items, nested_key):
    """Get the unique items from a list located in a dict or from a list of dicts with the same data schema.
    Considers the whole object for uniqueness, not specific keys.

    Args:
        source_items (list or dict): A list of dicts or a single dict.
        nested_key (str): The key to search for nested items.

    Returns:
        list: A list containing the unique dictionaries found in the nested key.
    """
    unique_dicts = {}
    if isinstance(source_items, list):
        logger.info(f"Getting unique dictionaries from {len(source_items)} items.")
        for item in source_items:
            for nested_dict in get_nested_value(item, nested_key):
                if nested_dict:
                    unique_dicts[str(nested_dict)] = nested_dict
    elif isinstance(source_items, dict):
        logger.info("Getting unique dictionaries from a single item.")
        for nested_dict in get_nested_value(source_items, nested_key):
            if nested_dict:
                unique_dicts[str(nested_dict)] = nested_dict
    logger.info(f"Found {len(unique_dicts)} unique dictionaries.")
    return list(unique_dicts.values())
