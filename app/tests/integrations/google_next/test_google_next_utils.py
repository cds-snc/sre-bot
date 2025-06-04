from integrations.google_next.utils import extract_google_doc_id


def test_extract_google_doc_id_valid_google_docs_url():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit"
    assert extract_google_doc_id(url) == "1aBcD_efGHI"


def test_extract_google_doc_id_oogle_docs_url_with_parameters():
    url = "https://docs.google.com/document/d/1aBcD_efGHI/edit?usp=sharing"
    assert extract_google_doc_id(url) == "1aBcD_efGHI"


def test_extract_google_doc_id_non_google_docs_url():
    url = "https://www.example.com/page/d/1aBcD_efGHI/other"
    assert extract_google_doc_id(url) is None


def test_extract_google_doc_id_invalid_url_format():
    url = "https://docs.google.com/document/1aBcD_efGHI"
    assert extract_google_doc_id(url) is None


def test_extract_google_doc_id_empty_string():
    assert extract_google_doc_id("") is None


def test_extract_google_doc_id_none_input():
    assert extract_google_doc_id(None) is None
