"""Unit tests: the edge check models the WAF AuthorizedEndpoints byte match and reports every drift.

Inputs are synthetic routes and allow-list entries, so each case pins one rule of the matcher or
one message the CI check prints; the real route table is covered by
test_server_edge_allow_list_routes.
"""

import pytest

from tests.unit.server.edge_allow_list import (
    EdgeEntry,
    MountedRoute,
    authentication_violations,
    edge_violations,
    entry_allows,
    is_allowed,
)

API_PREFIX = EdgeEntry("/api/v1/", "STARTS_WITH")


def _route(path: str, kind: str = "api", authenticated: bool = False) -> MountedRoute:
    return MountedRoute(path=path, methods=("GET",), kind=kind, authenticated=authenticated)


def test_exactly_matches_only_the_identical_path() -> None:
    entry = EdgeEntry("/health", "EXACTLY")
    assert entry_allows(entry, "/health")
    assert not entry_allows(entry, "/health/")
    assert not entry_allows(entry, "/healthz")


def test_exactly_never_matches_a_templated_route() -> None:
    assert not entry_allows(EdgeEntry("/hook/{webhook_id}", "EXACTLY"), "/hook/{webhook_id}")


def test_starts_with_matches_the_literal_head_of_a_templated_route() -> None:
    assert entry_allows(EdgeEntry("/hook", "STARTS_WITH"), "/hook/{webhook_id}")


def test_api_prefix_does_not_cover_a_sibling_version_or_the_bare_prefix() -> None:
    assert is_allowed("/api/v1/access/requests", [API_PREFIX])
    assert not is_allowed("/api/v10/x", [API_PREFIX])
    assert not is_allowed("/api/v1", [API_PREFIX])


def test_matching_is_case_sensitive() -> None:
    assert not is_allowed("/Health", [EdgeEntry("/health", "EXACTLY")])


def test_unsupported_constraint_raises() -> None:
    with pytest.raises(ValueError, match="CONTAINS"):
        entry_allows(EdgeEntry("/x", "CONTAINS"), "/x")


def test_a_new_route_outside_the_allow_list_is_reported_with_the_file_to_edit() -> None:
    problems = edge_violations([_route("/api/v2/x")], [API_PREFIX, EdgeEntry("/api/v2/y", "EXACTLY")], {}, {})
    assert any(
        "GET /api/v2/x is blocked at the edge" in problem and "authorized_endpoints.json" in problem for problem in problems
    )


def test_a_route_listed_internal_may_stay_blocked() -> None:
    assert edge_violations([_route("/api/v1/x"), _route("/metrics")], [API_PREFIX], {"/metrics": "scraped in the VPC"}, {}) == []


def test_an_internal_route_the_edge_allows_is_reported() -> None:
    problems = edge_violations([_route("/api/v1/x")], [API_PREFIX], {"/api/v1/x": "reason"}, {})
    assert problems == [
        "GET /api/v1/x is listed intentionally internal but the edge allows it: fix authorized_endpoints.json or the list"
    ]


def test_an_internal_entry_with_no_mounted_route_is_reported() -> None:
    problems = edge_violations([_route("/api/v1/x")], [API_PREFIX], {"/gone": "reason"}, {})
    assert problems == ["intentionally internal /gone is not a mounted route: remove it"]


def test_an_allow_list_entry_matching_no_route_is_reported_unless_alb_served() -> None:
    entries = [API_PREFIX, EdgeEntry("/auth/me", "EXACTLY"), EdgeEntry("/.well-known/security.txt", "EXACTLY")]
    problems = edge_violations([_route("/api/v1/x")], entries, {}, {"/.well-known/security.txt": "ALB fixed response"})
    assert problems == ["allow-list entry EXACTLY /auth/me matches no mounted route: remove it"]


def test_an_unmodelled_route_type_is_reported() -> None:
    problems = edge_violations([_route("/static", kind="Mount")], [EdgeEntry("/static", "STARTS_WITH")], {}, {})
    assert problems[0] == "GET /static: route type Mount is not modelled by the edge check"


def test_an_unauthenticated_route_under_the_prefix_is_reported() -> None:
    routes = [_route("/api/v1/open"), _route("/api/v1/closed", authenticated=True), _route("/version")]
    problems = authentication_violations(routes, "/api/v1/", {})
    assert problems == ["GET /api/v1/open has no get_current_user dependency: authenticate it or record it as public by decision"]


def test_a_public_by_decision_route_passes_and_a_stale_one_is_reported() -> None:
    routes = [_route("/api/v1/hook/{webhook_id}")]
    assert authentication_violations(routes, "/api/v1/", {"/api/v1/hook/{webhook_id}": "webhook tier"}) == []
    stale = authentication_violations([], "/api/v1/", {"/api/v1/hook/{webhook_id}": "webhook tier"})
    assert stale == ["public-by-decision /api/v1/hook/{webhook_id} is not a mounted route under /api/v1/: remove it"]
