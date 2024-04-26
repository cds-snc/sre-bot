"""This module contains utility functions for filtering lists and dictionaries."""
from functools import reduce
import logging

logger = logging.getLogger(__name__)


def filter_by_condition(list, condition):
    """Filter a list by a condition, keeping only the items that satisfy the condition."""
    return [item for item in list if condition(item)]


def get_nested_value(dictionary, key):
    if key in dictionary:
        return dictionary[key]
    try:
        return reduce(dict.get, key.split("."), dictionary)
    except TypeError:
        logger.error(f"Error getting nested value for key: {key}")
        return None
