import re
from core.logging import get_module_logger

logger = get_module_logger()


def extract_google_doc_id(url):
    """
    Extracts the Google Docs ID from a Google Docs URL.

    Args:
        url (str): The URL of the Google Docs document.

    Returns:
        str: The Google Docs ID extracted from the URL.
    """
    logger.debug(
        "extracting_google_doc_id",
        url=url,
    )
    if not url:
        return None

    # Regular expression pattern to match Google Docs ID
    pattern = r"https://docs.google.com/document/d/([a-zA-Z0-9_-]+)/"

    # Search in the given text for all occurences of pattern
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None
