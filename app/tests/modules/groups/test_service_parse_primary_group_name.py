from unittest.mock import patch

from modules.groups import service


def test_parse_primary_group_name_delegates_to_mappings():
    with patch("modules.groups.mappings.parse_primary_group_name") as mock_parse:
        mock_parse.return_value = {"prefix": "p", "canonical": "name"}
        res = service.parse_primary_group_name("p:name")
        mock_parse.assert_called_once_with("p:name", provider_registry=None)
        assert res["prefix"] == "p"
        assert res["canonical"] == "name"
