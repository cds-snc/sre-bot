"""Contract tests for how the production container starts and what the task definition sets.

The Dockerfile and the task-definition template are read as text and parsed; nothing is built
or rendered by terraform. The container starts uvicorn directly in exec form, so no script fetches
SSM parameters into a .env file, and the image ships neither the AWS CLI nor entry.sh. The
template sets only the platform-provided environment names; every other value comes from the
configuration files or a /sre-bot/* secret.
"""

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCKERFILE = REPO_ROOT / "Dockerfile"
TEMPLATE = REPO_ROOT / "terraform" / "templates" / "sre-bot.json.tpl"
APP_BIN = REPO_ROOT / "app" / "bin"


def _entrypoint() -> list[str]:
    lines = [line for line in DOCKERFILE.read_text(encoding="utf-8").splitlines() if line.startswith("ENTRYPOINT")]
    assert len(lines) == 1
    return json.loads(lines[0].removeprefix("ENTRYPOINT").strip())


def test_the_container_starts_uvicorn_in_exec_form() -> None:
    """Exec form makes uvicorn PID 1, so ECS's SIGTERM reaches it directly."""
    assert _entrypoint() == ["uvicorn", "--factory", "main:create_app", "--host=0.0.0.0"]


def test_the_image_installs_no_aws_cli_and_ships_no_entry_script() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert not re.search(r"awscli|aws-cli|AWSCLI_VERSION", dockerfile, re.IGNORECASE)
    assert "entry.sh" not in dockerfile
    assert not (APP_BIN / "entry.sh").exists()
    assert not (REPO_ROOT / "aws-cli-pubkey.asc").exists()


@pytest.mark.parametrize("path", [DOCKERFILE, *sorted(APP_BIN.glob("*.sh"))], ids=lambda path: path.name)
def test_nothing_in_the_image_fetches_an_ssm_parameter(path: Path) -> None:
    assert "get-parameter" not in path.read_text(encoding="utf-8")


def test_the_template_sets_only_the_platform_provided_environment_names() -> None:
    """Template placeholders are JSON-quoted or JSON-encoded, so a stand-in value per placeholder parses."""
    rendered = re.sub(r'"\$\{[^}]+\}"', '"x"', TEMPLATE.read_text(encoding="utf-8"))
    rendered = re.sub(r"\$\{[^}]+\}", "[]", rendered)

    container = json.loads(rendered)[0]

    assert sorted(entry["name"] for entry in container["environment"]) == ["ENVIRONMENT", "FORWARDED_ALLOW_IPS"]
