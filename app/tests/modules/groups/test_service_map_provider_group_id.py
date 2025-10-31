from unittest.mock import patch

from modules.groups import service


def test_map_provider_group_id_delegates():
    with patch("modules.groups.mappings.map_provider_group_id") as mock_map:
        mock_map.return_value = "a-my-group"
        res = service.map_provider_group_id("aws", "my-group", "google")
        mock_map.assert_called_once_with(
            from_provider="aws",
            from_group_id="my-group",
            to_provider="google",
            provider_registry=None,
        )
        assert res == "a-my-group"
