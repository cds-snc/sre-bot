"""Unit tests for the Google Workspace tenant entry's boot rules.

Each test installs its own files and sets only the variables it needs
(``google_slice_env``, ``install_google_files``); building the slice makes no
network call. The tenant entry is read from GOOGLE_WORKSPACE__TENANT__<FIELD>: a
customer id needs a credential source, chosen in order: the federation audience with
the service-account email (AWS federation), the key (whose account must match a set
email), the email alone (application default credentials); any tenant value set
without a customer id fails; the customer id is the real one, never blank or the
my_customer alias (the id is opaque: Google documents no format). Failures are read
from the ConfigurationError message, which must name the variable, and the
rendered traceback is searched for the key, the customer id and the delegated
user's values, which must never appear.
"""

import traceback
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from integrations.google_workspace.settings import GoogleWorkspaceSettings
from tests.factories.google_service_account import CLIENT_EMAIL, private_key_body, service_account_key
from tests.unit.integrations.google_workspace.conftest import install_google_files

pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("google_slice_env")]

KEY = service_account_key()
CUSTOMER = "C0tenant0001"
DELEGATED_USER = "delegated-user-0001@example.com"
CUSTOMER_NAME = "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID"
KEY_NAME = "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY"
DELEGATED_NAME = "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL"
EMAIL_NAME = "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL"
AUDIENCE_NAME = "GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE"
NAMES = {"KEY": KEY_NAME, "EMAIL": EMAIL_NAME, "AUDIENCE": AUDIENCE_NAME}
SERVICE_ACCOUNT = "sre-bot@cdssnc.iam.gserviceaccount.com"
AUDIENCE = "//iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/sre-bot/providers/aws-ecs"


def _build_error() -> str:
    with pytest.raises(ConfigurationError) as caught:
        GoogleWorkspaceSettings()
    rendered = "".join(traceback.format_exception(caught.value))
    for value in (KEY, private_key_body(), DELEGATED_USER, CUSTOMER):
        assert value not in rendered
    return str(caught.value)


def test_customer_id_without_a_credential_fails_naming_every_way_to_set_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tenant is unusable without a credential, so boot fails naming the three ways to give it one."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(DELEGATED_NAME, DELEGATED_USER)

    message = _build_error()

    assert f"{CUSTOMER_NAME} is set without a credential" in message
    for name in (AUDIENCE_NAME, EMAIL_NAME, KEY_NAME):
        assert name in message


@pytest.mark.parametrize(
    ("variables", "authentication"),
    [
        ({"AUDIENCE": AUDIENCE, "EMAIL": SERVICE_ACCOUNT}, "aws_federation"),
        ({"KEY": KEY}, "key"),
        ({"KEY": KEY, "EMAIL": CLIENT_EMAIL}, "key"),
        ({"EMAIL": SERVICE_ACCOUNT}, "application_default"),
        ({"AUDIENCE": AUDIENCE, "EMAIL": SERVICE_ACCOUNT, "KEY": KEY}, "aws_federation"),
        ({"AUDIENCE": AUDIENCE, "EMAIL": SERVICE_ACCOUNT, "KEY": "{not a key"}, "aws_federation"),
    ],
)
def test_the_credential_source_follows_the_selection_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variables: dict[str, str], authentication: str
) -> None:
    """The audience wins over a key, which stays during the cutover and is not even parsed; the email alone is ADC."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
    for short, value in variables.items():
        monkeypatch.setenv(NAMES[short], value)

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert tenant.authentication == authentication


def test_an_audience_without_the_email_fails_naming_the_email(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Federation has no account to impersonate without the email."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(AUDIENCE_NAME, AUDIENCE)

    assert f"{AUDIENCE_NAME} is set but {EMAIL_NAME} is not" in _build_error()


@pytest.mark.parametrize(
    "audience",
    [
        "set-outside-terraform",
        "//iam.googleapis.com/projects/cdssnc/locations/global/workloadIdentityPools/sre-bot/providers/aws-ecs",
        "//iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/sre-bot/providers/aws",
        "https://iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/sre-bot/providers/aws-ecs",
    ],
)
def test_an_audience_of_the_wrong_shape_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, audience: str) -> None:
    """The terraform placeholder, a project id instead of its number or a too-short provider id fail at boot, not at the first call."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(AUDIENCE_NAME, audience)
    monkeypatch.setenv(EMAIL_NAME, SERVICE_ACCOUNT)
    monkeypatch.setenv("AWS_REGION", "ca-central-1")

    assert f"{AUDIENCE_NAME} is not a workload identity provider audience" in _build_error()


def test_federation_without_an_aws_region_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The region signs the AWS request Google verifies, so its absence fails boot instead of every call."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(AUDIENCE_NAME, AUDIENCE)
    monkeypatch.setenv(EMAIL_NAME, SERVICE_ACCOUNT)
    for name in ("AWS_REGION", "AWS_DEFAULT_REGION", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-aws-config"))

    assert f"{AUDIENCE_NAME} is set but no AWS region is configured (AWS_REGION)" in _build_error()


def test_a_key_for_another_account_than_the_email_fails_naming_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The email set before the cutover must be the key's own account, so federation impersonates the same identity."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(KEY_NAME, KEY)
    monkeypatch.setenv(EMAIL_NAME, SERVICE_ACCOUNT)

    message = _build_error()

    assert f"{EMAIL_NAME} does not name the account of {KEY_NAME}" in message
    assert CLIENT_EMAIL not in message


@pytest.mark.parametrize("email", ["sre-bot", "  "])
def test_an_email_that_is_not_an_address_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, email: str) -> None:
    """A bare name or a blank is not an account to impersonate."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(EMAIL_NAME, email)

    assert EMAIL_NAME in _build_error()


@pytest.mark.parametrize("name", [KEY_NAME, DELEGATED_NAME, EMAIL_NAME, AUDIENCE_NAME])
def test_a_tenant_value_without_the_customer_id_fails_naming_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A key or delegated user with no customer id is a half configuration, so boot fails naming the variable."""
    install_google_files(tmp_path)
    monkeypatch.setenv(
        name, {DELEGATED_NAME: DELEGATED_USER, EMAIL_NAME: SERVICE_ACCOUNT, AUDIENCE_NAME: AUDIENCE}.get(name, KEY)
    )

    assert f"{name} is set but {CUSTOMER_NAME} is not" in _build_error()


def test_empty_tenant_variables_count_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank variables, as the test run sets them, are absent: no tenant and no failure."""
    install_google_files(tmp_path)
    for name in (CUSTOMER_NAME, KEY_NAME, DELEGATED_NAME):
        monkeypatch.setenv(name, "")

    assert GoogleWorkspaceSettings().tenant is None


def test_an_empty_delegated_user_with_a_tenant_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank delegated user beside a configured tenant is no delegated user, not an empty subject."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(KEY_NAME, KEY)
    monkeypatch.setenv(DELEGATED_NAME, "")

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert tenant.delegated_user_email is None


def test_an_empty_key_with_a_customer_id_fails_naming_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank key is no key: the tenant fails rather than building a half tenant."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(KEY_NAME, "")

    assert KEY_NAME in _build_error()


@pytest.mark.parametrize("customer_id", ["  ", "my_customer"])
def test_a_blank_or_alias_customer_id_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, customer_id: str) -> None:
    """Whitespace and the my_customer alias are not a tenant id, so boot fails naming the variable."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, customer_id)
    monkeypatch.setenv(KEY_NAME, KEY)

    assert CUSTOMER_NAME in _build_error()


def test_the_customer_id_is_stripped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Surrounding whitespace is not part of the id the directory calls send."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, f" {CUSTOMER} ")
    monkeypatch.setenv(KEY_NAME, KEY)

    tenant = GoogleWorkspaceSettings().tenant

    assert tenant is not None
    assert tenant.customer_id == CUSTOMER


@pytest.mark.parametrize(
    "files",
    [
        "[google_workspace]\nunknown = 1\n",
        "[google_workspace]\n[google_workspace.tenant]\nunknown = 1\n",
    ],
)
def test_an_unknown_key_fails(tmp_path: Path, files: str) -> None:
    """A misspelt key in the table or the tenant entry fails boot instead of being ignored."""
    install_google_files(tmp_path, base=files)

    assert "unknown" in _build_error()


def test_the_repr_hides_every_tenant_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Logging the slice or its tenant never prints the credential or the non-public values."""
    install_google_files(tmp_path)
    monkeypatch.setenv(CUSTOMER_NAME, CUSTOMER)
    monkeypatch.setenv(KEY_NAME, KEY)
    monkeypatch.setenv(DELEGATED_NAME, DELEGATED_USER)

    settings = GoogleWorkspaceSettings()

    for text in (repr(settings), repr(settings.tenant), str(settings)):
        for value in (KEY, CUSTOMER, DELEGATED_USER):
            assert value not in text
