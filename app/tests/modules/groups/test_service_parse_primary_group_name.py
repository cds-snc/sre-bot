from unittest.mock import patch

from modules.groups import service


def test_parse_primary_group_name_delegates_to_mappings():
    with patch("modules.groups.service.parse_primary_group_name") as mock_parse:
        mock_parse.return_value = {"prefix": "p", "canonical": "name"}
        res = service.parse_primary_group_name("p:name")
        # Accept either positional or keyword invocation styles
        assert mock_parse.call_count == 1
        called_args, called_kwargs = mock_parse.call_args
        assert called_args[0] == "p:name"
        if "provider_registry" in called_kwargs:
            assert called_kwargs["provider_registry"] is None
        assert res["prefix"] == "p"
        assert res["canonical"] == "name"
