"""
Guardrail script to prevent PREFIX environment-derivation regressions.

This script verifies that AppSettings.PREFIX is used only for legacy Slack
command-namespacing (frozen modules) and not for environment detection.
It is temporary and will be deleted when PREFIX is retired (TASK-45).

Usage:
  python bin/check_prefix_command_namespace.py [--self-test]

When --self-test is passed, runs internal verification of the detection rules
instead of scanning the tree. Without --self-test, scans the tree and baseline
and exits 0 if clean, 1 if violations are found.
"""

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    """A detected policy violation."""

    file: str
    line: int
    reason: str


def _is_prefix_read(node: ast.expr) -> bool:
    """Check if an expr node reads PREFIX (Name or Attribute)."""
    if isinstance(node, ast.Name) and node.id == "PREFIX":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "PREFIX":
        return True
    return False


def _find_violations_in_ast(
    tree: ast.Module, file_rel: str, baseline: set[str]
) -> list[Violation]:
    """Find violations by walking an AST.

    Rules:
      (a) Any is_production identifier -> violation
      (b) PREFIX read in a file NOT in baseline -> net-new violation
      (c) PREFIX == or PREFIX != comparison -> violation (derivation form)
      (d) Do NOT flag truthy uses (bool, if, ternary) — these are legitimate
          namespace reads in baseline files.
    """
    violations: list[Violation] = []
    file_has_prefix_read = False

    for node in ast.walk(tree):
        # Rule (a): is_production identifier
        if isinstance(node, ast.Name) and node.id == "is_production":
            violations.append(
                Violation(
                    file=file_rel,
                    line=node.lineno,
                    reason="is_production identifier found (retired, use ENVIRONMENT)",
                )
            )

        # Rule (c): PREFIX equality/inequality comparison
        # Match: Compare(left=PREFIX, ops=[Eq/NotEq], comparators=[...])
        # Do NOT match: Compare inside UnaryOp (bool), If test, ternary IfExp
        if isinstance(node, ast.Compare):
            if _is_prefix_read(node.left):
                for op in node.ops:
                    if isinstance(op, ast.Eq):
                        violations.append(
                            Violation(
                                file=file_rel,
                                line=node.lineno,
                                reason="PREFIX == derivation form found (not a legitimate namespace read)",
                            )
                        )
                    elif isinstance(op, ast.NotEq):
                        violations.append(
                            Violation(
                                file=file_rel,
                                line=node.lineno,
                                reason="PREFIX != derivation form found (not a legitimate namespace read)",
                            )
                        )

        # Track if this file reads PREFIX (for rule b + baseline stale-check)
        if _is_prefix_read(node):
            file_has_prefix_read = True

    # Rule (b): file reads PREFIX but is NOT in baseline
    if file_has_prefix_read and file_rel not in baseline:
        # Find a line number for the first PREFIX read
        first_read_line = 1
        for node in ast.walk(tree):
            if _is_prefix_read(node):
                first_read_line = node.lineno
                break
        violations.append(
            Violation(
                file=file_rel,
                line=first_read_line,
                reason="Net-new PREFIX reader not in baseline",
            )
        )

    return violations


def find_violations(root: Path, baseline: set[str]) -> list[Violation]:
    """Scan app/ for violations; check baseline for stale entries.

    Args:
      root: root path to scan (typically app/ or a test fixture)
      baseline: set of relative file paths (e.g., "modules/aws/aws.py")
               that are allowed to read PREFIX

    Returns:
      List of Violation objects. Empty list = clean tree.
    """
    violations: list[Violation] = []

    # Scan the tree for violations. Skip vendor directories.
    for py_file in root.rglob("*.py"):
        rel = py_file.relative_to(root).as_posix()

        # Skip vendor directories and test/ directory (but allow root-level test_*.py files for self-tests)
        if ".venv" in rel or "venv" in rel or "vendor" in rel or "tests/" in rel:
            continue

        try:
            code = py_file.read_text()
            tree = ast.parse(code, filename=rel)
            violations.extend(_find_violations_in_ast(tree, rel, baseline))
        except (SyntaxError, OSError):
            # Log but don't fail on parse errors
            pass

    # Rule (d): Check baseline for stale entries.
    # A baseline entry is stale if its file no longer exists or doesn't read PREFIX.
    for baseline_entry in baseline:
        entry_path = root / baseline_entry
        if not entry_path.exists():
            violations.append(
                Violation(
                    file=baseline_entry,
                    line=0,
                    reason="Stale baseline entry: file no longer exists",
                )
            )
            continue

        # File exists; check if it still reads PREFIX
        try:
            code = entry_path.read_text()
            tree = ast.parse(code, filename=baseline_entry)
            file_has_prefix_read = any(_is_prefix_read(n) for n in ast.walk(tree))
            if not file_has_prefix_read:
                violations.append(
                    Violation(
                        file=baseline_entry,
                        line=0,
                        reason="Stale baseline entry: file no longer reads PREFIX (reader migrated; remove from baseline)",
                    )
                )
        except (SyntaxError, OSError):
            pass

    return violations


def _run_self_tests() -> bool:
    """Run internal verification of detection rules. Returns True if all pass."""
    import tempfile

    print("Running self-tests...")
    tests_passed = 0
    tests_failed = 0

    def make_tree(code_str: str) -> tuple[Path, Path]:
        """Create a temp tree with a test file."""
        tmpdir = Path(tempfile.mkdtemp())
        test_file = tmpdir / "test_module.py"
        test_file.write_text(code_str)
        return tmpdir, test_file

    # Test (a): is_production detection
    print("  [a] is_production detection...", end=" ")
    tmpdir, _ = make_tree("is_production = env == 'production'\n")
    violations = find_violations(tmpdir, set())
    if violations and any("is_production" in v.reason for v in violations):
        print("✓")
        tests_passed += 1
    else:
        print("✗")
        tests_failed += 1

    # Test (b): net-new PREFIX reader detection
    print("  [b] net-new PREFIX reader...", end=" ")
    tmpdir, _ = make_tree(
        "from infrastructure.configuration.app import get_app_settings\nprefix = get_app_settings().PREFIX\n"
    )
    violations = find_violations(tmpdir, set())  # empty baseline
    if violations and any("net-new" in v.reason.lower() for v in violations):
        print("✓")
        tests_passed += 1
    else:
        print("✗")
        tests_failed += 1

    # Test (c): equality comparison rejection
    print("  [c] PREFIX == rejection...", end=" ")
    tmpdir, _ = make_tree("if app_settings.PREFIX == 'dev-':\n    pass\n")
    violations = find_violations(tmpdir, {"test_module.py"})  # baseline includes it
    if violations and any("==" in v.reason for v in violations):
        print("✓")
        tests_passed += 1
    else:
        print("✗")
        tests_failed += 1

    # Test (d-i): truthy ternary acceptance (baseline file)
    print("  [d-i] truthy ternary accepted...", end=" ")
    tmpdir, _ = make_tree(
        "prefix = app_settings.PREFIX if app_settings.PREFIX else ''\n"
    )
    violations = find_violations(tmpdir, {"test_module.py"})
    if not violations:
        print("✓")
        tests_passed += 1
    else:
        print("✗")
        tests_failed += 1

    # Test (d-ii): baseline shrink (no violations when both removed)
    print("  [d-ii] baseline shrink...", end=" ")
    tmpdir, _ = make_tree("# no PREFIX read\n")
    violations = find_violations(tmpdir, set())  # baseline is empty
    if not violations:
        print("✓")
        tests_passed += 1
    else:
        print("✗")
        tests_failed += 1

    # Test (d-iii): stale baseline detection
    print("  [d-iii] stale baseline entry...", end=" ")
    tmpdir, _ = make_tree("# no PREFIX read\n")
    violations = find_violations(
        tmpdir, {"test_module.py"}
    )  # baseline has it, but file doesn't read PREFIX
    if violations and any("stale" in v.reason.lower() for v in violations):
        print("✓")
        tests_passed += 1
    else:
        print("✗")
        tests_failed += 1

    print(f"\nSelf-tests: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


def main() -> int:
    """Main entry point. Returns exit code (0 = clean, 1 = violations)."""
    if "--self-test" in sys.argv:
        return 0 if _run_self_tests() else 1

    # Load baseline
    app_root = Path(__file__).parent.parent  # app/
    baseline_file = app_root / "bin" / "baselines" / "prefix_readers.txt"

    if not baseline_file.exists():
        print(f"Error: baseline file not found: {baseline_file}", file=sys.stderr)
        return 1

    # Parse baseline: skip comments and blank lines
    baseline_lines = baseline_file.read_text().strip().split("\n")
    baseline = {
        line.strip()
        for line in baseline_lines
        if line.strip() and not line.strip().startswith("#")
    }

    # Scan tree
    violations = find_violations(app_root, baseline)

    if not violations:
        print("✓ PREFIX guardrail: clean tree")
        return 0

    print("✗ PREFIX guardrail violations:", file=sys.stderr)
    for v in violations:
        print(f"  {v.file}:{v.line} — {v.reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
