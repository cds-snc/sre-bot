"""Behavior tests for the PREFIX guardrail baseline file."""

from pathlib import Path


def test_prefix_readers_baseline_has_no_active_readers():
    """The baseline file should contain only comments and blank lines."""
    baseline = Path("bin/baselines/prefix_readers.txt")

    lines = baseline.read_text().splitlines()
    active_entries = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]

    assert active_entries == []
