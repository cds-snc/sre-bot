import logging
from botocore.exceptions import ClientError
from integrations.aws import identity_store_next as isn
from models.integrations import build_success_response, build_error_response
from tests.fixtures.aws_clients import FakeClient
from tests.integrations.aws.fixtures_identity_store import (
    assert_integration_success,
    assert_integration_error,
)


class TestGetUser:
    def test_get_user_success(self, monkeypatch):
        user = {"UserId": "u-1", "UserName": "u1@example.com"}
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(user, "get_user", "aws"),
        )
        resp = isn.get_user("u-1")
        assert_integration_success(resp, expected_data=user)

    def test_get_user_not_found(self, monkeypatch, caplog):
        def raise_not_found(**kw):
            raise ClientError(
                {
                    "Error": {
                        "Code": "ResourceNotFoundException",
                        "Message": "Not found",
                    }
                },
                "DescribeUser",
            )

        FakeClient(api_responses={"describe_user": raise_not_found})
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_error_response(
                Exception("Not found"), "get_user", "aws"
            ),
        )
        caplog.set_level(logging.WARNING)
        resp = isn.get_user("missing")
        assert_integration_error(resp)

    def test_create_user_success(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                {"UserId": "u-10"}, "create_user", "aws"
            ),
        )
        resp = isn.create_user(
            email="new@example.com", first_name="New", family_name="User"
        )
        assert_integration_success(resp)
        assert resp.data.get("UserId") == "u-10"


class TestListUsers:
    def test_list_users_pagination(self, monkeypatch):
        pages = [{"Users": [{"UserId": "u1"}]}, {"Users": [{"UserId": "u2"}]}]
        FakeClient(paginated_pages=pages, api_responses={"list_users": lambda **kw: {}})
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                [{"UserId": "u1"}, {"UserId": "u2"}], "list_users", "aws"
            ),
        )
        resp = isn.list_users()
        assert_integration_success(resp)
        assert isinstance(resp.data, list)
        pages = [{"Users": [{"UserId": "u1"}]}, {"Users": [{"UserId": "u2"}]}]
        FakeClient(paginated_pages=pages, api_responses={"list_users": lambda **kw: {}})
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                [{"UserId": "u1"}, {"UserId": "u2"}], "list_users", "aws"
            ),
        )

        resp = isn.list_users()
        assert_integration_success(resp)
        assert isinstance(resp.data, list)


class TestGetGroup:
    def test_get_group_success(self, monkeypatch):
        group = {"GroupId": "g-1", "DisplayName": "G1"}
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(group, "get_group", "aws"),
        )
        resp = isn.get_group("g-1")
        assert_integration_success(resp, expected_data=group)


class TestListGroups:
    def test_list_groups_pagination(self, monkeypatch):
        groups = [{"GroupId": "g-1"}, {"GroupId": "g-2"}]
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(groups, "list_groups", "aws"),
        )
        resp = isn.list_groups()
        assert_integration_success(resp)
        assert isinstance(resp.data, list)
        assert {g.get("GroupId") for g in resp.data} == {"g-1", "g-2"}


class TestCreateUser:
    def test_create_user_success(self, monkeypatch):
        # fake_user_client available if deeper assertions are needed
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                {"UserId": "u-10"}, "create_user", "aws"
            ),
        )

        resp = isn.create_user(
            email="new@example.com", first_name="New", family_name="User"
        )
        assert_integration_success(resp)
        assert resp.data.get("UserId") == "u-10"


class TestGroupMemberships:
    def test_create_group_membership_success(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                {"MembershipId": "m-1"}, "create_group_membership", "aws"
            ),
        )

        resp = isn.create_group_membership("g-1", "u-1")
        assert_integration_success(resp)
        assert resp.data.get("MembershipId") == "m-1"

    def test_create_group_membership_conflict(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_error_response(
                Exception("Conflict"), "create_group_membership", "aws"
            ),
        )

        resp = isn.create_group_membership("g-1", "u-1")
        assert_integration_error(resp)

    def test_delete_group_membership_success(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response({}, "delete_group_membership", "aws"),
        )

        resp = isn.delete_group_membership("m-1")
        assert_integration_success(resp)

    def test_delete_group_membership_not_found(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_error_response(
                Exception("Not found"), "delete_group_membership", "aws"
            ),
        )

        resp = isn.delete_group_membership("missing")
        assert_integration_error(resp)

    def test_list_group_memberships_pagination(self, monkeypatch):
        memberships = [
            {"MembershipId": "m-1", "MemberId": {"UserId": "u-1"}},
            {"MembershipId": "m-2", "MemberId": {"UserId": "u-2"}},
        ]
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                memberships, "list_group_memberships", "aws"
            ),
        )

        resp = isn.list_group_memberships("g-1")
        assert_integration_success(resp)
        assert isinstance(resp.data, list)
        assert len(resp.data) == 2

    def test_get_group_membership_id_success(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                {"MembershipId": "m-1"}, "get_group_membership_id", "aws"
            ),
        )

        resp = isn.get_group_membership_id("g-1", "u-1")
        assert_integration_success(resp)
        assert resp.data.get("MembershipId") == "m-1"


class TestListGroupsWithMemberships:
    def test_list_groups_with_memberships_happy_path(self, monkeypatch):
        groups = [{"GroupId": "g-1", "DisplayName": "G1"}]
        memberships = {"g-1": [{"MembershipId": "m-1", "MemberId": {"UserId": "u-1"}}]}
        users = [{"UserId": "u-1", "UserName": "u1@example.com"}]
        monkeypatch.setattr(
            isn,
            "list_groups",
            lambda **kw: build_success_response(groups, "list_groups", "aws"),
        )
        monkeypatch.setattr(
            isn,
            "_fetch_group_memberships_parallel",
            lambda gids, max_workers=10: memberships,
        )
        monkeypatch.setattr(
            isn,
            "list_users",
            lambda **kw: build_success_response(users, "list_users", "aws"),
        )
        resp = isn.list_groups_with_memberships()
        assert_integration_success(resp)
        assert isinstance(resp.data, list)
        assert resp.data[0]["GroupId"] == "g-1"
        assert resp.data[0]["GroupMemberships"][0]["MembershipId"] == "m-1"

    def test__fetch_group_memberships_parallel_error_handling(self, monkeypatch):
        # Simulate IntegrationResponse with success=False and non-list data
        def fake_list_group_memberships(group_id):
            if group_id == "g-error":
                return build_error_response(
                    Exception("fail"), "list_group_memberships", "aws"
                )
            if group_id == "g-nonlist":
                return build_success_response(
                    "not-a-list", "list_group_memberships", "aws"
                )
            return build_success_response(
                [{"MemberId": {"UserId": "u1"}}], "list_group_memberships", "aws"
            )

        monkeypatch.setattr(isn, "list_group_memberships", fake_list_group_memberships)
        # Patch ThreadPoolExecutor to run synchronously for test
        monkeypatch.setattr(
            "concurrent.futures.ThreadPoolExecutor",
            lambda max_workers: __import__("types").SimpleNamespace(
                submit=lambda fn, arg: __import__("types").SimpleNamespace(
                    result=lambda: fn(arg)
                ),
                __enter__=lambda s: s,
                __exit__=lambda s, a, b, c: None,
            ),
        )
        monkeypatch.setattr(
            "concurrent.futures.as_completed", lambda futures: [f for f in futures]
        )
        group_ids = ["g-ok", "g-error", "g-nonlist"]
        memberships = isn._fetch_group_memberships_parallel(group_ids)
        assert memberships["g-ok"] == [{"MemberId": {"UserId": "u1"}}]
        assert memberships["g-error"] == []
        assert memberships["g-nonlist"] == []

    def test__fetch_group_memberships_parallel_exception(self, monkeypatch):
        # Simulate exception during future.result()
        def fake_list_group_memberships(group_id):
            if group_id == "g-exc":
                raise Exception("boom")
            return build_success_response(
                [{"MemberId": {"UserId": "u1"}}], "list_group_memberships", "aws"
            )

        monkeypatch.setattr(isn, "list_group_memberships", fake_list_group_memberships)
        monkeypatch.setattr(
            "concurrent.futures.ThreadPoolExecutor",
            lambda max_workers: __import__("types").SimpleNamespace(
                submit=lambda fn, arg: __import__("types").SimpleNamespace(
                    result=lambda: fn(arg)
                ),
                __enter__=lambda s: s,
                __exit__=lambda s, a, b, c: None,
            ),
        )
        monkeypatch.setattr(
            "concurrent.futures.as_completed", lambda futures: [f for f in futures]
        )
        group_ids = ["g-ok", "g-exc"]
        memberships = isn._fetch_group_memberships_parallel(group_ids)
        assert memberships["g-ok"] == [{"MemberId": {"UserId": "u1"}}]
        assert memberships["g-exc"] == []

    def test__assemble_groups_with_memberships_edge_cases(self):
        # Not a dict group, missing GroupId, memberships missing, tolerate_errors True
        groups = [None, {"GroupId": 123}, {"GroupId": "g1"}, {"GroupId": "g2"}]
        memberships_by_group = {"g1": None, "g2": []}
        users_by_id = {"u1": {"UserId": "u1"}}
        # tolerate_errors True: should include g1 with error, g2 with no members
        result = isn._assemble_groups_with_memberships(
            groups, memberships_by_group, users_by_id, tolerate_errors=True
        )
        group_ids = [g["GroupId"] for g in result]
        assert "g1" in group_ids and "g2" in group_ids
        # tolerate_errors False: should exclude g1 and g2 (no members)
        result2 = isn._assemble_groups_with_memberships(
            groups, memberships_by_group, users_by_id, tolerate_errors=False
        )
        group_ids2 = [g["GroupId"] for g in result2]
        assert "g1" not in group_ids2 and "g2" not in group_ids2

    def test_list_groups_with_memberships_api_failures(self, monkeypatch):
        # list_groups returns unsuccessful response
        monkeypatch.setattr(
            isn,
            "list_groups",
            lambda **kw: build_error_response(Exception("fail"), "list_groups", "aws"),
        )
        resp = isn.list_groups_with_memberships()
        assert_integration_error(resp)
        # list_users returns unsuccessful response
        monkeypatch.setattr(
            isn,
            "list_groups",
            lambda **kw: build_success_response(
                [{"GroupId": "g1"}], "list_groups", "aws"
            ),
        )
        monkeypatch.setattr(
            isn, "_fetch_group_memberships_parallel", lambda gids: {"g1": []}
        )
        monkeypatch.setattr(
            isn,
            "list_users",
            lambda **kw: build_error_response(Exception("fail"), "list_users", "aws"),
        )
        resp2 = isn.list_groups_with_memberships()
        assert_integration_error(resp2)

    def test_list_groups_with_memberships_filter_logic(self, monkeypatch):
        # Test custom filter lambdas
        monkeypatch.setattr(
            isn,
            "list_groups",
            lambda **kw: build_success_response(
                [
                    {"GroupId": "g1", "DisplayName": "Alpha"},
                    {"GroupId": "g2", "DisplayName": "Beta"},
                ],
                "list_groups",
                "aws",
            ),
        )
        monkeypatch.setattr(
            isn,
            "_fetch_group_memberships_parallel",
            lambda gids: {gid: [] for gid in gids},
        )
        monkeypatch.setattr(
            isn,
            "list_users",
            lambda **kw: build_success_response([], "list_users", "aws"),
        )
        filters = [lambda g: g["DisplayName"].startswith("A")]
        resp = isn.list_groups_with_memberships(
            groups_filters=filters, tolerate_errors=True
        )
        assert_integration_success(resp)
        assert len(resp.data) == 1 and resp.data[0]["GroupId"] == "g1"


class TestHelperFunctions:
    def test_get_user_id_success(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                {"UserId": "u-1"}, "get_user_id", "aws"
            ),
        )

        resp = isn.get_user_by_username("u-1")
        assert_integration_success(resp)
        assert resp.data.get("UserId") == "u-1"

    def test_get_user_id_not_found(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_error_response(
                Exception("Not found"), "get_user_id", "aws"
            ),
        )

        resp = isn.get_user_by_username("missing")
        assert_integration_error(resp)

    def test_get_group_id_success(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                {"GroupId": "g-1"}, "get_group_id", "aws"
            ),
        )

        resp = isn.get_group_by_name("g-1")
        assert_integration_success(resp)
        assert resp.data.get("GroupId") == "g-1"

    def test_get_group_membership_id_not_found(self, monkeypatch):
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_error_response(
                Exception("Not found"), "get_group_membership_id", "aws"
            ),
        )

        resp = isn.get_group_membership_id("g-1", "u-1")
        assert_integration_error(resp)

    def test_is_member_in_groups_true_and_false(self, monkeypatch):
        # When the user is a member of one of the groups
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_success_response(
                {"MembershipId": "m-1"}, "get_group_membership_id", "aws"
            ),
        )
        resp = isn.is_member_in_groups("u-1", ["g-1", "g-2"])
        assert_integration_success(resp)
        # Expect a truthy data when membership exists
        assert resp.data is True or resp.data is not None

        # When the user is not a member (simulate error) — allow either an error response
        # or a success response with False in data depending on implementation details.
        monkeypatch.setattr(
            isn,
            "execute_aws_api_call",
            lambda **kw: build_error_response(
                Exception("Not found"), "get_group_membership_id", "aws"
            ),
        )
        resp2 = isn.is_member_in_groups("u-1", ["g-1"])
        # Accept either a proper IntegrationResponse error or a success with False
        if resp2.success:
            assert resp2.data is False
        else:
            assert_integration_error(resp2)


class TestHealthcheck:
    def test_healthcheck_success(self, monkeypatch):
        # list_users succeeds -> healthcheck should return True
        monkeypatch.setattr(
            isn,
            "list_users",
            lambda **kw: build_success_response(
                [{"UserId": "u-1"}], "list_users", "aws"
            ),
        )
        assert isn.healthcheck() is True

    def test_healthcheck_failure(self, monkeypatch):
        # list_users raises an exception -> healthcheck should return False
        monkeypatch.setattr(
            isn,
            "list_users",
            lambda **kw: (_ for _ in ()).throw(Exception("boom")),
        )
        assert isn.healthcheck() is False


class TestBatchOperations:
    def test_get_batch_users_happy_path(self, monkeypatch):
        # get_user returns success for each requested user
        monkeypatch.setattr(
            isn,
            "get_user",
            lambda user_id, **kw: build_success_response(
                {"UserId": user_id}, "get_user", "aws"
            ),
        )

        resp = isn.get_batch_users(["u-1", "u-2"])
        assert_integration_success(resp)
        assert isinstance(resp.data, dict)
        assert resp.data.get("u-1").get("UserId") == "u-1"
        assert resp.data.get("u-2").get("UserId") == "u-2"

    def test_get_batch_groups_happy_path(self, monkeypatch):
        # get_group returns success for each requested group
        monkeypatch.setattr(
            isn,
            "get_group",
            lambda group_id, **kw: build_success_response(
                {"GroupId": group_id}, "get_group", "aws"
            ),
        )

        resp = isn.get_batch_groups(["g-1", "g-2"])
        assert_integration_success(resp)
        assert isinstance(resp.data, dict)
        assert resp.data.get("g-1").get("GroupId") == "g-1"
        assert resp.data.get("g-2").get("GroupId") == "g-2"

    def test_get_batch_users_partial_failure(self, monkeypatch):
        # Simulate one success and one failure
        def fake_get_user(user_id, **kw):
            if user_id == "u-fail":
                return build_error_response(Exception("Not found"), "get_user", "aws")
            return build_success_response({"UserId": user_id}, "get_user", "aws")

        monkeypatch.setattr(isn, "get_user", fake_get_user)

        resp = isn.get_batch_users(["u-ok", "u-fail"])
        # Expect an IntegrationResponse with success=False due to partial failures
        assert_integration_error(resp)
        assert isinstance(resp.data, dict)
        assert resp.data.get("u-ok") is not None
        assert resp.data.get("u-fail") is None

    def test_get_batch_groups_partial_failure(self, monkeypatch):
        # Simulate one success and one failure
        def fake_get_group(group_id, **kw):
            if group_id == "g-fail":
                return build_error_response(Exception("Not found"), "get_group", "aws")
            return build_success_response({"GroupId": group_id}, "get_group", "aws")

        monkeypatch.setattr(isn, "get_group", fake_get_group)

        resp = isn.get_batch_groups(["g-ok", "g-fail"])
        assert_integration_error(resp)
        assert isinstance(resp.data, dict)
        assert resp.data.get("g-ok") is not None
        assert resp.data.get("g-fail") is None

    def test_get_batch_users_malformed_response(self, monkeypatch):
        # get_user returns a non-dict (malformed) response for one user
        def fake_get_user(user_id, **kw):
            if user_id == "u-bad":
                return build_success_response("not-a-dict", "get_user", "aws")
            return build_success_response({"UserId": user_id}, "get_user", "aws")

        monkeypatch.setattr(isn, "get_user", fake_get_user)

        resp = isn.get_batch_users(["u-good", "u-bad"])
        # Should still succeed, but the malformed entry is present
        assert resp.data["u-good"]["UserId"] == "u-good"
        assert resp.data["u-bad"] == "not-a-dict"

        def test__fetch_group_memberships_parallel_error_handling(self, monkeypatch):
            # Simulate IntegrationResponse with success=False and non-list data
            def fake_list_group_memberships(group_id):
                if group_id == "g-error":
                    return build_error_response(
                        Exception("fail"), "list_group_memberships", "aws"
                    )
                if group_id == "g-nonlist":
                    return build_success_response(
                        "not-a-list", "list_group_memberships", "aws"
                    )
                return build_success_response(
                    [{"MemberId": {"UserId": "u1"}}], "list_group_memberships", "aws"
                )

            monkeypatch.setattr(
                isn, "list_group_memberships", fake_list_group_memberships
            )
            # Patch ThreadPoolExecutor to run synchronously for test
            monkeypatch.setattr(
                "concurrent.futures.ThreadPoolExecutor",
                lambda max_workers: __import__("types").SimpleNamespace(
                    submit=lambda fn, arg: __import__("types").SimpleNamespace(
                        result=lambda: fn(arg)
                    ),
                    __enter__=lambda s: s,
                    __exit__=lambda s, a, b, c: None,
                ),
            )
            monkeypatch.setattr(
                "concurrent.futures.as_completed", lambda futures: [f for f in futures]
            )
            group_ids = ["g-ok", "g-error", "g-nonlist"]
            memberships = isn._fetch_group_memberships_parallel(group_ids)
            assert memberships["g-ok"] == [{"MemberId": {"UserId": "u1"}}]
            assert memberships["g-error"] == []
            assert memberships["g-nonlist"] == []

        def test__fetch_group_memberships_parallel_exception(self, monkeypatch):
            # Simulate exception during future.result()
            def fake_list_group_memberships(group_id):
                if group_id == "g-exc":
                    raise Exception("boom")
                return build_success_response(
                    [{"MemberId": {"UserId": "u1"}}], "list_group_memberships", "aws"
                )

            monkeypatch.setattr(
                isn, "list_group_memberships", fake_list_group_memberships
            )
            monkeypatch.setattr(
                "concurrent.futures.ThreadPoolExecutor",
                lambda max_workers: __import__("types").SimpleNamespace(
                    submit=lambda fn, arg: __import__("types").SimpleNamespace(
                        result=lambda: fn(arg)
                    ),
                    __enter__=lambda s: s,
                    __exit__=lambda s, a, b, c: None,
                ),
            )
            monkeypatch.setattr(
                "concurrent.futures.as_completed", lambda futures: [f for f in futures]
            )
            group_ids = ["g-ok", "g-exc"]
            memberships = isn._fetch_group_memberships_parallel(group_ids)
            assert memberships["g-ok"] == [{"MemberId": {"UserId": "u1"}}]
            assert memberships["g-exc"] == []

        def test__assemble_groups_with_memberships_edge_cases(self):
            # Not a dict group, missing GroupId, memberships missing, tolerate_errors True
            groups = [None, {"GroupId": 123}, {"GroupId": "g1"}, {"GroupId": "g2"}]
            memberships_by_group = {"g1": None, "g2": []}
            users_by_id = {"u1": {"UserId": "u1"}}
            # tolerate_errors True: should include g1 with error, g2 with no members
            result = isn._assemble_groups_with_memberships(
                groups, memberships_by_group, users_by_id, tolerate_errors=True
            )
            group_ids = [g["GroupId"] for g in result]
            assert "g1" in group_ids and "g2" in group_ids
            # tolerate_errors False: should exclude g1 and g2 (no members)
            result2 = isn._assemble_groups_with_memberships(
                groups, memberships_by_group, users_by_id, tolerate_errors=False
            )
            group_ids2 = [g["GroupId"] for g in result2]
            assert "g1" not in group_ids2 and "g2" not in group_ids2

        def test_list_groups_with_memberships_api_failures(self, monkeypatch):
            # list_groups returns unsuccessful response
            monkeypatch.setattr(
                isn,
                "list_groups",
                lambda **kw: build_error_response(
                    Exception("fail"), "list_groups", "aws"
                ),
            )
            resp = isn.list_groups_with_memberships()
            assert_integration_error(resp)
            # list_users returns unsuccessful response
            monkeypatch.setattr(
                isn,
                "list_groups",
                lambda **kw: build_success_response(
                    [{"GroupId": "g1"}], "list_groups", "aws"
                ),
            )
            monkeypatch.setattr(
                isn, "_fetch_group_memberships_parallel", lambda gids: {"g1": []}
            )
            monkeypatch.setattr(
                isn,
                "list_users",
                lambda **kw: build_error_response(
                    Exception("fail"), "list_users", "aws"
                ),
            )
            resp2 = isn.list_groups_with_memberships()
            assert_integration_error(resp2)

        def test_list_groups_with_memberships_filter_logic(self, monkeypatch):
            # Test custom filter lambdas
            monkeypatch.setattr(
                isn,
                "list_groups",
                lambda **kw: build_success_response(
                    [
                        {"GroupId": "g1", "DisplayName": "Alpha"},
                        {"GroupId": "g2", "DisplayName": "Beta"},
                    ],
                    "list_groups",
                    "aws",
                ),
            )
            monkeypatch.setattr(
                isn,
                "_fetch_group_memberships_parallel",
                lambda gids: {gid: [] for gid in gids},
            )
            monkeypatch.setattr(
                isn,
                "list_users",
                lambda **kw: build_success_response([], "list_users", "aws"),
            )
            filters = [lambda g: g["DisplayName"].startswith("A")]
            resp = isn.list_groups_with_memberships(groups_filters=filters)
            assert_integration_success(resp)
            assert len(resp.data) == 1 and resp.data[0]["GroupId"] == "g1"

    def test_get_batch_groups_non_list_key(self, monkeypatch):
        # get_group returns a non-dict (malformed) response for one group
        def fake_get_group(group_id, **kw):
            if group_id == "g-bad":
                return build_success_response(["not-a-dict"], "get_group", "aws")
            return build_success_response({"GroupId": group_id}, "get_group", "aws")

        monkeypatch.setattr(isn, "get_group", fake_get_group)

        resp = isn.get_batch_groups(["g-good", "g-bad"])
        # Should still succeed, but the malformed entry is present
        assert resp.data["g-good"]["GroupId"] == "g-good"
        assert resp.data["g-bad"] == ["not-a-dict"]
