"""Behaviour tests for bin/entry.sh, the container entrypoint.

The script is run with /bin/sh in a temporary working directory. `aws` and
`uvicorn` are replaced by stub scripts placed first on PATH: the `aws` stub
prints a fixed KEY=value line or exits non-zero, and the `uvicorn` stub records
that it ran. The assertions read the exit status, the stub's marker file and the
.env file the script writes, which is what the container start depends on.
"""

import shutil
import subprocess
from pathlib import Path

ENTRY_SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "entry.sh"
SH = shutil.which("sh") or "/bin/sh"


def _write_stub(directory: Path, name: str, body: str) -> None:
    stub = directory / name
    stub.write_text(f"#!/bin/sh\n{body}\n")
    stub.chmod(0o755)


def _run_entry(tmp_path: Path, aws_body: str) -> subprocess.CompletedProcess[str]:
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _write_stub(stubs, "aws", aws_body)
    _write_stub(stubs, "uvicorn", f'echo "$@" > "{tmp_path}/uvicorn-started"')
    return subprocess.run(  # noqa: S603 -- fixed interpreter and script path under test
        [SH, str(ENTRY_SCRIPT)],
        cwd=tmp_path,
        env={"PATH": f"{stubs}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_entry_script_stops_when_a_parameter_read_fails(tmp_path):
    """A failed SSM read stops the script with a non-zero status before uvicorn starts."""
    result = _run_entry(tmp_path, "exit 1")

    assert result.returncode != 0
    assert not (tmp_path / "uvicorn-started").exists()


def test_entry_script_writes_env_and_starts_uvicorn_when_reads_succeed(tmp_path):
    """Both parameter reads land in .env and the script then hands over to uvicorn."""
    result = _run_entry(tmp_path, "echo EXAMPLE_KEY=value")

    assert result.returncode == 0
    assert (tmp_path / ".env").read_text() == "EXAMPLE_KEY=value\nEXAMPLE_KEY=value\n"
    assert (tmp_path / "uvicorn-started").read_text().startswith("main:server_app")
