"""Quick smoke tests for google_service_next and google_directory_next.

This script is intentionally standalone and uses local mocks from tests.factory_helpers
and simple monkeypatching to avoid requiring real Google credentials.

Run with:

python3 scripts/google_smoke_test.py

It will print a short report and exit with code 0 on success.
"""

# This script intentionally performs imports after executing load_dotenv() to ensure
# environment variables are available for `core.config` before it is imported.
# It's a small standalone utility used for local smoke tests; skip flake8 checks.
# flake8: noqa

import os  # noqa: E402
import json
import argparse
import sys

from dotenv import load_dotenv

# Load .env early so core.config (settings) picks up values before modules import
load_dotenv()

# When pytest imports this module during test collection we should skip by
# default so CI / normal test runs don't attempt live or env-backed smoke
# tests. To enable these tests in CI or locally, set RUN_SMOKE_TESTS=1 in the
# environment. Keep the module runnable as a script (python ./tests/google_smoke_test.py)
# by only calling pytest.skip when pytest is the importer.
import sys
import os

if "pytest" in sys.modules and not os.environ.get("RUN_SMOKE_TESTS"):
    import pytest as _pytest

    _pytest.skip(
        "Skipping google smoke tests by default. Set RUN_SMOKE_TESTS=1 to enable.",
        allow_module_level=True,
    )


from core.config import settings  # noqa: E402
from integrations.google_workspace import google_directory_next as gdn  # noqa: E402
from integrations.google_workspace.schemas import User  # noqa: E402
from models.integrations import (
    IntegrationResponse,
    build_success_response,
)  # noqa: E402
from tests.factories.google import (
    make_google_groups,
    make_google_members,
    make_google_users,
)  # noqa: E402


def _validate_integration_response(resp, expected_model=None):
    assert isinstance(
        resp, IntegrationResponse
    ), f"Not an IntegrationResponse: {type(resp)}"
    if not resp.success:
        raise RuntimeError(f"Integration call failed: {resp.error}")
    if expected_model is not None:
        # allow both single dict and list
        data = resp.data
        if isinstance(data, list):
            for item in data:
                expected_model.model_validate(item)
        elif isinstance(data, dict):
            expected_model.model_validate(data)


def test_get_user(domain: str):
    # use project/domain-aware default for mocked users
    users = make_google_users(1, prefix="svc-", domain=domain)
    # monkeypatch execute_google_api_call to return success

    def fake_execute(*args, **kwargs):
        return build_success_response(users[0], "get_user", "google")

    # If live mode is enabled, do not patch execute_google_api_call
    if not _LIVE:
        gdn.execute_google_api_call = fake_execute
        resp = gdn.get_user(users[0]["primaryEmail"])
    else:
        # In live mode, query a known admin/test user instead of the synthetic svc- user
        live_user = os.environ.get("TEST_GOOGLE_USER") or getattr(
            getattr(settings, "google_workspace", {}), "SRE_BOT_EMAIL", None
        )
        if not live_user:
            print(
                "ERROR: No TEST_GOOGLE_USER env var or settings.google_workspace.SRE_BOT_EMAIL configured for live get_user.",
                file=sys.stderr,
            )
            raise SystemExit(4)
        resp = gdn.get_user(live_user)

    # If live mode and 403 returned, print remediation steps and exit non-zero
    if _LIVE and not resp.success:
        err = resp.error or {}
        code = str(err.get("error_code")) if err.get("error_code") is not None else None
        msg = err.get("message", "")
        if code == "403" or "Not Authorized" in msg or "not authorized" in msg.lower():
            print(
                "ERROR: Google Admin Directory returned 403 Forbidden.", file=sys.stderr
            )
            print(
                "This usually means the service account or impersonation lacks Admin SDK permissions or domain-wide delegation is not configured.",
                file=sys.stderr,
            )
            print("Remediation steps:", file=sys.stderr)
            print(
                "  1) Ensure the service account JSON referenced by GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is correct and accessible.",
                file=sys.stderr,
            )
            print(
                "  2) In Google Cloud IAM, enable domain-wide delegation for the service account and note the client ID.",
                file=sys.stderr,
            )
            print(
                "  3) In Google Workspace Admin Console -> Security -> API Controls -> Domain-wide Delegation, add the client ID and grant the following scopes:",
                file=sys.stderr,
            )
            print(
                "       - https://www.googleapis.com/auth/admin.directory.user.readonly",
                file=sys.stderr,
            )
            print(
                "       - https://www.googleapis.com/auth/admin.directory.group.readonly",
                file=sys.stderr,
            )
            print(
                "       - https://www.googleapis.com/auth/admin.directory.group.member.readonly",
                file=sys.stderr,
            )
            print(
                "  4) Ensure the service account is impersonating a super-admin (SRE_BOT_EMAIL in settings) when making Admin API calls.",
                file=sys.stderr,
            )
            print(
                "  5) Verify Admin SDK APIs are enabled in the Cloud project.",
                file=sys.stderr,
            )
            print("Full error: ", err, file=sys.stderr)
            raise SystemExit(2)

    _validate_integration_response(resp, expected_model=User)
    print("get_user: OK")


def test_list_groups_with_members(domain: str):
    groups = make_google_groups(2, prefix="g-", domain=domain)
    users = make_google_users(3, prefix="u-", domain=domain)
    members = make_google_members(3, prefix="u-", domain=domain)

    # Mock list_groups to return groups
    def fake_list_groups(**kwargs):

        return build_success_response(groups, "list_groups", "google")

    # Mock get_batch_group_members to return mapping
    def fake_get_batch_group_members(group_keys, **kwargs):

        return build_success_response(
            {k: members for k in group_keys}, "get_batch_group_members", "google"
        )

    # Mock get_batch_users to return mapping
    def fake_get_batch_users(user_keys, **kwargs):

        return build_success_response(
            {u["primaryEmail"]: u for u in users}, "get_batch_users", "google"
        )

    if not _LIVE:
        gdn.list_groups = fake_list_groups
        gdn.get_batch_group_members = fake_get_batch_group_members
        gdn.get_batch_users = fake_get_batch_users

    resp = gdn.list_groups_with_members()

    # If live mode and 403 returned, give remediation guidance and exit non-zero
    if _LIVE and not resp.success:
        err = resp.error or {}
        code = str(err.get("error_code")) if err.get("error_code") is not None else None
        msg = err.get("message", "")
        if code == "403" or "Not Authorized" in msg or "not authorized" in msg.lower():
            print(
                "ERROR: Google Admin Directory returned 403 Forbidden while listing groups/members.",
                file=sys.stderr,
            )
            print("Likely causes and remediation:", file=sys.stderr)
            print(
                "  - Domain-wide delegation not configured for the service account client ID.",
                file=sys.stderr,
            )
            print(
                "  - Admin Console scopes for Admin SDK not granted to the delegation client ID.",
                file=sys.stderr,
            )
            print(
                "  - The impersonated user (SRE_BOT_EMAIL) is not an admin or lacks sufficient privileges.",
                file=sys.stderr,
            )
            print("Suggested scopes to grant:", file=sys.stderr)
            print(
                "  https://www.googleapis.com/auth/admin.directory.user.readonly",
                file=sys.stderr,
            )
            print(
                "  https://www.googleapis.com/auth/admin.directory.group.readonly",
                file=sys.stderr,
            )
            print(
                "  https://www.googleapis.com/auth/admin.directory.group.member.readonly",
                file=sys.stderr,
            )
            print("Full error:", err, file=sys.stderr)
            raise SystemExit(2)

    # validate and assert assembled structure
    _validate_integration_response(resp)

    resp = gdn.list_groups_with_members()
    _validate_integration_response(resp)

    # Validate assembled structure (list of groups with members)
    data = resp.data
    assert isinstance(data, list)
    for g in data:
        # ensure members key exists and is a list
        assert "members" in g and isinstance(g["members"], list)
        # validate each member has an email
        for m in g["members"]:
            assert "email" in m
    print("list_groups_with_members: OK")

    # After successful validation, produce a JSON report listing group emails
    # that contain members whose email domains do not match the allowed domain.
    data = resp.data or []
    # Build a mapping of group_email -> list of external member emails
    external_groups = {}
    for g in data:
        members = g.get("members", []) if isinstance(g, dict) else []
        grp_email = g.get("email") if isinstance(g, dict) else None
        if not grp_email:
            continue
        externals = []
        for m in members:
            if not isinstance(m, dict):
                continue
            email = m.get("email")
            if not email or "@" not in email:
                continue
            domain = email.split("@", 1)[1].lower()
            if domain != ALLOWED_DOMAIN.lower():
                externals.append(email)
        if externals:
            # Deduplicate while preserving order and sort for deterministic output
            # Use dict.fromkeys to deduplicate while preserving first-seen order
            deduped = list(dict.fromkeys(externals))
            external_groups[grp_email] = sorted(deduped)

    report = {
        "allowed_domain": ALLOWED_DOMAIN,
        # external_groups is now a mapping: group_email -> [external_member_emails]
        "external_groups": external_groups,
    }
    report_path = os.path.join(os.getcwd(), "google_external_members_report.json")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"External members report written to {report_path}")
    except Exception as e:
        print("Failed to write external members report:", e, file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google smoke tests")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run real API calls (requires credentials in env)",
    )
    parser.add_argument(
        "--domain",
        help="Domain to use for mocked users/groups (defaults to project setting or cds-snc.ca)",
    )
    args = parser.parse_args()

    # Validate live mode requirements
    _LIVE = bool(args.live)
    # Determine domain for mocked data: CLI flag -> settings -> fallback
    settings_domain = getattr(
        getattr(settings, "google_workspace", {}), "GOOGLE_WORKSPACE_DOMAIN", None
    )
    # Only allow the project's canonical domain. Reject any other domain (e.g. servicecanada.gc.ca)
    ALLOWED_DOMAIN = "cds-snc.ca"
    _DOMAIN = args.domain or settings_domain or ALLOWED_DOMAIN

    # Safety: ensure the configured domain (settings or CLI) matches the allowed project domain
    if settings_domain and settings_domain != ALLOWED_DOMAIN:
        print(
            f"ERROR: Project setting GOOGLE_WORKSPACE_DOMAIN='{settings_domain}' is not allowed. Only '{ALLOWED_DOMAIN}' is supported.",
            file=sys.stderr,
        )
        print(
            "The servicecanada.gc.ca domain is managed by an external IdP and must not be used here. Update project settings to use the cds-snc.ca domain.",
            file=sys.stderr,
        )
        raise SystemExit(3)

    if args.domain and args.domain != ALLOWED_DOMAIN:
        print(
            f"ERROR: Provided --domain '{args.domain}' is not allowed. Only '{ALLOWED_DOMAIN}' may be used.",
            file=sys.stderr,
        )
        raise SystemExit(3)
    if _LIVE:
        # Ensure expected google workspace credentials/settings exist
        gcp_key = getattr(
            settings.google_workspace, "GCP_SRE_SERVICE_ACCOUNT_KEY_FILE", None
        )
        if not gcp_key:
            # Allow JSON path via env var for convenience
            gcp_key_env = os.environ.get("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE")
            if not gcp_key_env:
                raise SystemExit(
                    "Live mode requested but GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is not set in settings or env"
                )
    else:
        # default: mocked mode
        pass

    # pass resolved domain into tests so mocks match org constraints
    test_get_user(_DOMAIN)
    test_list_groups_with_members(_DOMAIN)
    print("All smoke tests passed")
