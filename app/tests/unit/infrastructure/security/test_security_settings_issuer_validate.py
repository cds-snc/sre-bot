"""Boot validation of the [security] table and its issuer entries.

Each test copies the checked-in base and ci files to a temporary directory,
appends a [security] table to the ci file and installs that pair, so the slice
validates a real file. The .env file and every SECURITY__ variable are kept out.
Failures must raise ConfigurationError naming the file, the table and the key,
and for an issuer entry the issuer, so a bad reviewed file fails boot instead
of leaving an issuer silently unusable.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files
from infrastructure.security.settings import SecuritySettings
from server.configuration import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

_VALID_ENTRY = """
[[security.issuers]]
issuer = "https://issuer.example.com"
jwks_uri = "https://issuer.example.com/.well-known/jwks.json"
algorithms = ["RS256"]
audience = "sre-bot"
"""


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No SECURITY__ variable reaches the slice, so only the files are validated."""
    for field in SecuritySettings.model_fields:
        monkeypatch.delenv(f"SECURITY__{field.upper()}", raising=False)
    yield


def _install_ci_with(tmp_path: Path, extra: str) -> Path:
    for name in ("base.toml", "ci.toml"):
        (tmp_path / name).write_text((CONFIG_DIR / name).read_text())
    ci_file = tmp_path / "ci.toml"
    with ci_file.open("a") as file:
        file.write(extra)
    install_configuration_files(load_configuration_files("ci", tmp_path))
    return ci_file


def test_valid_issuer_entry_resolves_to_the_issuer_map(tmp_path: Path) -> None:
    """An array-of-tables entry becomes the issuer map the JWT readers use, keyed by the issuer."""
    _install_ci_with(tmp_path, _VALID_ENTRY)

    settings = SecuritySettings(_env_file=None)

    assert settings.issuer_config == {
        "https://issuer.example.com": {
            "jwks_uri": "https://issuer.example.com/.well-known/jwks.json",
            "algorithms": ["RS256"],
            "audience": "sre-bot",
        }
    }


def test_several_issuer_entries_are_all_kept(tmp_path: Path) -> None:
    """Each [[security.issuers]] block adds one trusted issuer."""
    second = _VALID_ENTRY.replace("issuer.example.com", "second.example.com")
    _install_ci_with(tmp_path, _VALID_ENTRY + second)

    settings = SecuritySettings(_env_file=None)

    assert set(settings.issuer_config) == {"https://issuer.example.com", "https://second.example.com"}


def test_absent_algorithms_keep_the_rs256_default(tmp_path: Path) -> None:
    """An entry without algorithms verifies with RS256, as the JWT validator always defaulted."""
    _install_ci_with(tmp_path, _VALID_ENTRY.replace('algorithms = ["RS256"]\n', ""))

    settings = SecuritySettings(_env_file=None)

    assert settings.issuer_config["https://issuer.example.com"]["algorithms"] == ["RS256"]


def test_loopback_http_jwks_uri_is_accepted(tmp_path: Path) -> None:
    """The local token server of bin/dev-token.py serves its keys over http on the loopback address."""
    entry = _VALID_ENTRY.replace(
        'jwks_uri = "https://issuer.example.com/.well-known/jwks.json"',
        'jwks_uri = "http://127.0.0.1:8001/.well-known/jwks.json"',
    )
    _install_ci_with(tmp_path, entry)

    settings = SecuritySettings(_env_file=None)

    assert settings.issuer_config["https://issuer.example.com"]["jwks_uri"].startswith("http://127.0.0.1")


def test_unknown_security_key_fails_naming_file_table_and_key(tmp_path: Path) -> None:
    """A misspelled key in [security] fails boot naming the file, the table and the key."""
    ci_file = _install_ci_with(tmp_path, "\n[security]\ncors_allowed_origin = []\n")

    with pytest.raises(ConfigurationError, match=rf"{ci_file}: \[security\] cors_allowed_origin"):
        SecuritySettings(_env_file=None)


def test_wildcard_origin_in_the_file_fails_naming_the_key(tmp_path: Path) -> None:
    """A wildcard origin written in a configuration file fails boot naming the list."""
    _install_ci_with(tmp_path, '\n[security]\ncors_allowed_origins = ["*"]\n')

    with pytest.raises(ConfigurationError, match=r"\[security\] cors_allowed_origins"):
        SecuritySettings(_env_file=None)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('audience = "sre-bot"\n', "", "audience"),
        ('audience = "sre-bot"', 'audience = ""', "audience"),
        ('algorithms = ["RS256"]', "algorithms = []", "algorithms"),
        ('algorithms = ["RS256"]', 'algorithms = ["HS256"]', "HS256"),
        ('algorithms = ["RS256"]', 'algorithms = ["RS256", "none"]', "none"),
        (
            'jwks_uri = "https://issuer.example.com/.well-known/jwks.json"',
            'jwks_uri = "http://issuer.example.com/.well-known/jwks.json"',
            "jwks_uri",
        ),
        ('jwks_uri = "https://issuer.example.com/.well-known/jwks.json"\n', "", "jwks_uri"),
        ('audience = "sre-bot"', 'audience = "sre-bot"\nrefresh = 60', "refresh"),
    ],
)
def test_invalid_issuer_entry_fails_naming_the_issuers_key(tmp_path: Path, old: str, new: str, message: str) -> None:
    """A missing audience, an empty or symmetric algorithm list, a plain-http or missing jwks_uri,
    or an unknown entry key fails boot naming [security] issuers and the offending key."""
    _install_ci_with(tmp_path, _VALID_ENTRY.replace(old, new))

    with pytest.raises(ConfigurationError, match=r"\[security\] issuers") as error:
        SecuritySettings(_env_file=None)

    assert message in str(error.value)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('audience = "sre-bot"', 'audience = ""'),
        ('algorithms = ["RS256"]', 'algorithms = ["HS256"]'),
        (
            'jwks_uri = "https://issuer.example.com/.well-known/jwks.json"',
            'jwks_uri = "http://issuer.example.com/.well-known/jwks.json"',
        ),
    ],
)
def test_invalid_issuer_entry_error_names_the_issuer(tmp_path: Path, old: str, new: str) -> None:
    """The error names which issuer is at fault, so a file with several entries points at one."""
    _install_ci_with(tmp_path, _VALID_ENTRY.replace(old, new))

    with pytest.raises(ConfigurationError, match="https://issuer.example.com"):
        SecuritySettings(_env_file=None)


def test_duplicate_issuer_fails_naming_it(tmp_path: Path) -> None:
    """Two entries for the same issuer are ambiguous and fail boot naming the issuer."""
    _install_ci_with(tmp_path, _VALID_ENTRY + _VALID_ENTRY)

    with pytest.raises(ConfigurationError, match="https://issuer.example.com"):
        SecuritySettings(_env_file=None)


def test_issuers_that_are_not_a_list_fail_naming_the_key(tmp_path: Path) -> None:
    """A scalar where the issuer list belongs fails boot instead of meaning no issuers."""
    _install_ci_with(tmp_path, '\n[security]\nissuers = "https://issuer.example.com"\n')

    with pytest.raises(ConfigurationError, match=r"\[security\] issuers"):
        SecuritySettings(_env_file=None)
