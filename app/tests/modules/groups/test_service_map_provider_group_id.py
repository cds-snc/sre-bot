from unittest.mock import patch

from modules.groups import service


def test_map_provider_group_id_delegates():
    with patch("modules.groups.service.map_provider_group_id") as mock_map:
        mock_map.return_value = "a-my-group"
        res = service.map_provider_group_id("aws", "my-group", "google")
        # Accept either positional or keyword invocation styles
        assert mock_map.call_count == 1
        called_args, called_kwargs = mock_map.call_args
        assert called_args == ("aws", "my-group", "google")
        if "provider_registry" in called_kwargs:
            assert called_kwargs["provider_registry"] is None
        assert res == "a-my-group"
