"""
Comprehensive unit tests for provisioning groups module using next-gen Google Directory functions.

This test suite validates the groups provisioning logic specifically for the new
google_directory_next integration to ensure proper data formatting and structure.
"""

from unittest.mock import patch, call
from modules.provisioning import groups_next as groups


class TestGetGroupsFromIntegrationGoogle:
    """Test cases for get_groups_from_integration with Google Groups using next-gen functions."""

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_get_groups_from_integration_google_basic(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
        google_groups_with_legacy_structure,
    ):
        """Test basic Google Groups integration with next-gen functions."""
        # Create test data using new factories with legacy structure
        google_groups = google_groups_with_legacy_structure(
            n_groups=2, n_members_per_group=3
        )
        mock_google_list_groups_with_members.return_value = google_groups

        response = groups.get_groups_from_integration("google_groups")

        # Verify response structure
        assert response == google_groups
        assert len(response) == 2

        # Verify each group has the expected structure
        for group in response:
            assert "id" in group
            assert "name" in group
            assert "email" in group
            assert "members" in group

            # Verify member structure includes flattened user details
            for member in group["members"]:
                assert "kind" in member
                assert "email" in member
                assert "role" in member
                assert "type" in member
                assert "status" in member
                assert "id" in member
                # Legacy compatibility - flattened user details
                assert "primaryEmail" in member
                assert "name" in member
                assert "user_details" in member

        # Verify function calls
        mock_google_list_groups_with_members.assert_called_once_with(
            groups_filters=[],
            groups_kwargs=None,
        )
        assert not mock_filters.filter_by_condition.called
        assert not mock_aws_list_groups_with_memberships.called

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_get_groups_from_integration_google_with_query(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
        google_group_factory,
        google_groups_with_legacy_structure,
    ):
        """Test Google Groups integration with query parameter."""
        # Create AWS-prefixed groups and regular groups
        aws_groups = google_groups_with_legacy_structure(
            n_groups=2, n_members_per_group=2
        )
        # Set AWS email prefixes
        aws_groups[0]["email"] = "aws-group1@test.com"
        aws_groups[1]["email"] = "aws-group2@test.com"

        mock_google_list_groups_with_members.return_value = aws_groups

        query = "email:aws-*"
        response = groups.get_groups_from_integration("google_groups", query=query)

        assert response == aws_groups
        assert len(response) == 2
        assert all(group["email"].startswith("aws-") for group in response)

        # Verify the query is passed correctly
        mock_google_list_groups_with_members.assert_called_once_with(
            groups_filters=[],
            groups_kwargs={"query": "email:aws-*"},
        )

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_get_groups_from_integration_google_with_pre_filters(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
        google_groups_with_legacy_structure,
    ):
        """Test Google Groups integration with pre-processing filters."""
        google_groups = google_groups_with_legacy_structure(
            n_groups=3, n_members_per_group=2
        )
        mock_google_list_groups_with_members.return_value = google_groups

        # Define pre-processing filters
        pre_filters = [lambda g: g["email"].startswith("aws-")]

        response = groups.get_groups_from_integration(
            "google_groups", pre_processing_filters=pre_filters
        )

        assert response == google_groups

        # Verify pre-processing filters are passed to the function
        mock_google_list_groups_with_members.assert_called_once_with(
            groups_filters=pre_filters,
            groups_kwargs=None,
        )

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_get_groups_from_integration_google_with_post_filters(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
        google_groups_with_legacy_structure,
    ):
        """Test Google Groups integration with post-processing filters."""
        # Create groups with different prefixes
        all_groups = google_groups_with_legacy_structure(
            n_groups=4, n_members_per_group=2
        )
        # Set different email patterns
        all_groups[0]["email"] = "aws-group1@test.com"
        all_groups[1]["email"] = "aws-group2@test.com"
        all_groups[2]["email"] = "dev-group1@test.com"
        all_groups[3]["email"] = "prod-group1@test.com"

        aws_groups = all_groups[:2]  # Only AWS groups after filtering

        mock_google_list_groups_with_members.return_value = all_groups
        mock_filters.filter_by_condition.return_value = aws_groups

        # Define post-processing filters
        post_filters = [lambda g: g["email"].startswith("aws-")]

        response = groups.get_groups_from_integration(
            "google_groups", post_processing_filters=post_filters
        )

        assert response == aws_groups
        assert len(response) == 2

        # Verify post-processing filters are applied
        mock_filters.filter_by_condition.assert_called_once_with(
            all_groups, post_filters[0]
        )

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_get_groups_from_integration_google_empty_result(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
    ):
        """Test Google Groups integration with empty result."""
        mock_google_list_groups_with_members.return_value = []

        response = groups.get_groups_from_integration("google_groups")

        assert response == []
        mock_google_list_groups_with_members.assert_called_once_with(
            groups_filters=[],
            groups_kwargs=None,
        )


class TestGroupDataStructures:
    """Test specific data structure requirements for Google Groups."""

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_google_group_structure_validation(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
        google_group_factory,
        google_member_factory,
        google_user_factory,
    ):
        """Test that Google Groups have the correct structure for provisioning."""
        # mock_filters is patched but not used in this test
        _ = mock_filters  # Acknowledge unused parameter
        # Create realistic Google Groups data structure
        test_groups = google_group_factory(2, domain="company.com")
        members1 = google_member_factory(2, prefix="user1-", domain="company.com")
        members2 = google_member_factory(2, prefix="user2-", domain="company.com")
        users1 = google_user_factory(2, prefix="user1-", domain="company.com")
        users2 = google_user_factory(2, prefix="user2-", domain="company.com")

        # Ensure email consistency
        for i, (member, user) in enumerate(zip(members1, users1)):
            member["email"] = user["primaryEmail"]
        for i, (member, user) in enumerate(zip(members2, users2)):
            member["email"] = user["primaryEmail"]

        # Create groups with flattened member structure (as returned by list_groups_with_members)
        expected_groups = []
        for i, group in enumerate(test_groups):
            group_members = members1 if i == 0 else members2
            group_users = users1 if i == 0 else users2

            flattened_members = []
            for member, user in zip(group_members, group_users):
                flattened_member = {**member}
                flattened_member["user_details"] = user
                # Flatten user details for legacy compatibility
                for k, v in user.items():
                    if k not in flattened_member:
                        flattened_member[k] = v
                flattened_members.append(flattened_member)

            group["members"] = flattened_members
            expected_groups.append(group)

        mock_google_list_groups_with_members.return_value = expected_groups

        response = groups.get_groups_from_integration("google_groups")

        # Validate response structure
        assert len(response) == 2

        for group in response:
            # Group-level validation
            assert "id" in group
            assert "name" in group
            assert "email" in group
            assert "description" in group
            assert "directMembersCount" in group
            assert "members" in group

            # Members validation
            for member in group["members"]:
                # Original member fields
                assert "kind" in member
                assert "email" in member
                assert "role" in member
                assert "type" in member
                assert "status" in member
                assert "id" in member

                # User details nested structure
                assert "user_details" in member
                user_details = member["user_details"]
                assert "id" in user_details
                assert "primaryEmail" in user_details
                assert "name" in user_details
                assert "suspended" in user_details
                assert "emails" in user_details

                # Flattened user fields for legacy compatibility
                assert "primaryEmail" in member
                assert "name" in member
                assert "suspended" in member
                assert "emails" in member

                # Verify no key conflicts (member role should not be overwritten)
                assert member["role"] in [
                    "MEMBER",
                    "MANAGER",
                    "OWNER",
                ]  # Google Directory roles
                if "role" in user_details:
                    assert (
                        user_details["role"] != member["role"]
                    )  # Different role contexts

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_google_vs_aws_structure_compatibility(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
        google_groups_with_legacy_structure,
        aws_groups_w_users,
    ):
        """Test that both Google and AWS group structures work with provisioning logic."""
        # Test Google structure
        google_groups = google_groups_with_legacy_structure(
            n_groups=1, n_members_per_group=2
        )
        mock_google_list_groups_with_members.return_value = google_groups

        google_response = groups.get_groups_from_integration("google_groups")

        # Test AWS structure
        aws_groups = aws_groups_w_users(n_groups=1, n_users=2)
        mock_aws_list_groups_with_memberships.return_value = aws_groups

        aws_response = groups.get_groups_from_integration("aws_identity_center")

        # Both should return valid structures for downstream processing
        assert len(google_response) == 1
        assert len(aws_response) == 1

        # Google structure validation
        google_group = google_response[0]
        assert "name" in google_group  # group_display_key
        assert "members" in google_group  # members key
        for member in google_group["members"]:
            assert "primaryEmail" in member  # members_display_key

        # AWS structure validation
        aws_group = aws_response[0]
        assert "DisplayName" in aws_group  # group_display_key
        assert "GroupMemberships" in aws_group  # members key
        for membership in aws_group["GroupMemberships"]:
            # AWS has nested structure for user info
            assert "MemberId" in membership


class TestLogGroups:
    """Test the log_groups function with new data structures."""

    @patch("modules.provisioning.groups_next.logger")
    @patch("modules.provisioning.groups_next.filters")
    def test_log_groups_google_structure(
        self,
        mock_filters,
        mock_logger,
        google_groups_with_legacy_structure,
    ):
        """Test logging Google Groups with proper structure."""
        # Setup test data
        google_groups = google_groups_with_legacy_structure(
            n_groups=2, n_members_per_group=3
        )

        # Mock the nested value getter
        mock_filters.get_nested_value.side_effect = lambda obj, key: obj.get(key)

        # Call log_groups with Google structure
        groups.log_groups(
            google_groups,
            group_display_key="name",
            members="members",
            members_display_key="primaryEmail",
            integration_name="Google",
        )

        # Verify summary logging
        mock_logger.info.assert_any_call(
            "log_groups_summary",
            integration_name="Google",
            groups_count=2,
        )

        # Verify group-level logging
        for group in google_groups:
            mock_logger.info.assert_any_call(
                "log_group_members",
                integration_name="Google",
                group_name=group["name"],
                members_count=len(group["members"]),
            )

        # Verify member-level logging
        expected_member_calls = []
        for group in google_groups:
            for member in group["members"]:
                expected_member_calls.append(
                    call(
                        "log_group_member",
                        integration_name="Google",
                        group_name=group["name"],
                        member_name=member["primaryEmail"],
                    )
                )

        # Check that all expected member log calls were made
        for expected_call in expected_member_calls:
            mock_logger.info.assert_any_call(
                *expected_call.args, **expected_call.kwargs
            )

    @patch("modules.provisioning.groups_next.logger")
    @patch("modules.provisioning.groups_next.filters")
    def test_log_groups_missing_keys_warnings(
        self,
        mock_filters,
        mock_logger,
        google_groups_with_legacy_structure,
    ):
        """Test that missing key warnings are logged appropriately."""
        # mock_filters is patched but not used in this test
        _ = mock_filters  # Acknowledge unused parameter
        google_groups = google_groups_with_legacy_structure(
            n_groups=1, n_members_per_group=1
        )

        # Test missing group_display_key
        groups.log_groups(
            google_groups,
            group_display_key=None,
            members="members",
            members_display_key="primaryEmail",
            integration_name="Google",
        )

        mock_logger.warning.assert_any_call(
            "log_groups_missing_display_key",
            integration_name="Google",
            missing_key="group_display_key",
        )

        # Test missing members key
        groups.log_groups(
            google_groups,
            group_display_key="name",
            members=None,
            members_display_key="primaryEmail",
            integration_name="Google",
        )

        mock_logger.warning.assert_any_call(
            "log_groups_missing_members_key",
            integration_name="Google",
            missing_key="members",
        )

        # Test missing members_display_key
        groups.log_groups(
            google_groups,
            group_display_key="name",
            members="members",
            members_display_key=None,
            integration_name="Google",
        )

        mock_logger.warning.assert_any_call(
            "log_groups_missing_display_key",
            integration_name="Google",
            missing_key="members_display_key",
        )

    @patch("modules.provisioning.groups_next.logger")
    @patch("modules.provisioning.groups_next.filters")
    def test_log_groups_empty_groups(
        self,
        mock_filters,
        mock_logger,
    ):
        """Test logging behavior with empty groups list."""
        # mock_filters is patched but not used in this test
        _ = mock_filters  # Acknowledge unused parameter
        groups.log_groups(
            [],
            group_display_key="name",
            members="members",
            members_display_key="primaryEmail",
            integration_name="Google",
        )

        mock_logger.info.assert_any_call(
            "log_groups_summary",
            integration_name="Google",
            groups_count=0,
        )

    @patch("modules.provisioning.groups_next.logger")
    @patch("modules.provisioning.groups_next.filters")
    def test_log_groups_group_without_members(
        self,
        mock_filters,
        mock_logger,
        google_group_factory,
    ):
        """Test logging behavior for groups without members."""
        # mock_filters is patched but not used in this test directly but used by log_groups
        # Create group without members
        groups_data = google_group_factory(1)
        # Don't add members key or set it to empty
        groups_data[0]["members"] = []

        mock_filters.get_nested_value.side_effect = lambda obj, key: obj.get(key)

        groups.log_groups(
            groups_data,
            group_display_key="name",
            members="members",
            members_display_key="primaryEmail",
            integration_name="Google",
        )

        # Should log that group has no members (using log_group_no_members for empty list)
        mock_logger.info.assert_any_call(
            "log_group_no_members",
            integration_name="Google",
            group_name=groups_data[0]["name"],
        )


class TestProvisioningArchitectureValidation:
    """Test current provisioning architecture patterns and validate improvements."""

    @patch("modules.provisioning.groups_next.filters")
    @patch(
        "modules.provisioning.groups_next.identity_store.list_groups_with_memberships"
    )
    @patch(
        "modules.provisioning.groups_next.google_directory_next.list_groups_with_members"
    )
    def test_integration_source_pattern_scalability(
        self,
        mock_google_list_groups_with_members,
        mock_aws_list_groups_with_memberships,
        mock_filters,
    ):
        """Test current integration source pattern and identify scalability issues."""
        # mock_filters is patched but not used in this test
        _ = mock_filters  # Acknowledge unused parameter
        # Test the match-case pattern for different integration sources

        # Test valid sources
        valid_sources = ["google_groups", "aws_identity_center"]
        for source in valid_sources:
            mock_google_list_groups_with_members.return_value = []
            mock_aws_list_groups_with_memberships.return_value = []

            result = groups.get_groups_from_integration(source)
            assert result == []

        # Test invalid source (should return empty list)
        result = groups.get_groups_from_integration("invalid_source")
        assert result == []

        # Test case sensitivity
        result = groups.get_groups_from_integration("Google_Groups")  # Wrong case
        assert result == []

    def test_data_structure_inconsistencies(
        self,
        google_groups_with_legacy_structure,
        aws_groups_w_users,
    ):
        """Identify data structure inconsistencies between providers."""
        # Get sample data from both providers
        google_groups = google_groups_with_legacy_structure(
            n_groups=1, n_members_per_group=1
        )
        aws_groups = aws_groups_w_users(n_groups=1, n_users=1)

        google_group = google_groups[0]
        aws_group = aws_groups[0]

        # Document the structural differences that make the architecture brittle

        # Group-level differences
        google_group_keys = set(google_group.keys())
        aws_group_keys = set(aws_group.keys())

        # These differences require different handling logic
        assert "name" in google_group_keys  # Google uses "name"
        assert "DisplayName" in aws_group_keys  # AWS uses "DisplayName"

        # Members structure differences
        google_members_key = "members"
        aws_members_key = "GroupMemberships"

        assert google_members_key in google_group
        assert aws_members_key in aws_group

        # Member detail structure differences
        google_member = google_group[google_members_key][0]
        aws_membership = aws_group[aws_members_key][0]

        # Google has flattened user details
        assert "primaryEmail" in google_member
        assert "name" in google_member

        # AWS has nested user details in MemberId
        assert "MemberId" in aws_membership
        assert "UserName" in aws_membership["MemberId"]

        # This demonstrates why the current approach is fragile
        # - Different key names for same concepts
        # - Different nesting levels
        # - Different member identification methods
        # - Hard-coded string mappings in the provisioning logic
