#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""One-way, idempotent sync of Backlog.md tasks to GitHub issues.

The backlog (backlog/tasks/*.md) is the source of truth. Each synced issue
carries a hidden ``<!-- backlog-sync: task-N -->`` marker in its body; the
marker is the durable key between a task and its issue. Issues without a
marker (community-filed) are never touched.

Behaviour per task:
  - no marker issue exists            -> create (skipped if the task is already Done)
  - issue exists, rendered content    -> update title/body/labels/milestone
    differs from desired
  - task Done / completed / archived  -> close the issue
  - task active but issue closed      -> reopen
  - everything matches                -> skip

Default mode is a dry run that prints the plan without writing anything.
Pass --apply to execute. Read-only gh calls happen in both modes.

Usage:
    uv run --script bin/backlog_issue_sync.py                 # dry run, all tasks
    uv run --script bin/backlog_issue_sync.py --task task-1   # scope to specific tasks
    uv run --script bin/backlog_issue_sync.py --apply         # do it
    uv run --script bin/backlog_issue_sync.py --apply --prune # also close orphaned marker issues
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKLOG_DIR = REPO_ROOT / "backlog"

MARKER_RE = re.compile(r"<!-- backlog-sync: (task-[\w.-]+) -->")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)

SYNC_LABEL = "backlog"
LABEL_COLORS = {
    SYNC_LABEL: "5319e7",
    "priority: high": "d93f0b",
    "priority: medium": "fbca04",
    "priority: low": "c2e0c6",
    "status: in-progress": "1d76db",
}
DEFAULT_LABEL_COLOR = "ededed"


@dataclass
class Task:
    id: str
    title: str
    status: str
    path: Path
    labels: list[str] = field(default_factory=list)
    priority: str = ""
    milestone: str = ""
    dependencies: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    description: str = ""
    acceptance_criteria: str = ""
    definition_of_done: str = ""
    terminal: bool = False  # lives in completed/ or archive/

    @property
    def desired_closed(self) -> bool:
        return self.terminal or self.status.strip().lower() == "done"


def gh(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["gh", *args],
        cwd=REPO_ROOT,
        input=input_text,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def gh_json(*args: str):
    out = gh(*args)
    return json.loads(out) if out else []


def extract_section(body: str, begin: str, end: str) -> str:
    match = re.search(re.escape(begin) + r"(.*?)" + re.escape(end), body, re.S)
    return match.group(1).strip() if match else ""


def strip_item_indexes(text: str) -> str:
    """Backlog numbers AC/DoD items as '- [ ] #1 ...'; '#1' would autolink to
    an unrelated issue on GitHub, so drop the index."""
    return re.sub(r"^(\s*- \[[ xX]\]) #\d+\s+", r"\1 ", text, flags=re.M)


def parse_task(path: Path, terminal: bool) -> Task | None:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return None
    meta = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    task_id = str(meta.get("id", "")).lower()
    if not task_id.startswith("task-"):
        return None
    return Task(
        id=task_id,
        title=str(meta.get("title", "")).strip(),
        status=str(meta.get("status", "")),
        path=path,
        labels=[str(label) for label in meta.get("labels") or []],
        priority=str(meta.get("priority") or ""),
        milestone=str(meta.get("milestone") or ""),
        dependencies=[str(dep).lower() for dep in meta.get("dependencies") or []],
        references=[str(ref) for ref in meta.get("references") or []],
        description=extract_section(
            body, "<!-- SECTION:DESCRIPTION:BEGIN -->", "<!-- SECTION:DESCRIPTION:END -->"
        ),
        acceptance_criteria=extract_section(body, "<!-- AC:BEGIN -->", "<!-- AC:END -->"),
        definition_of_done=extract_section(body, "<!-- DOD:BEGIN -->", "<!-- DOD:END -->"),
        terminal=terminal,
    )


def load_tasks() -> dict[str, Task]:
    tasks: dict[str, Task] = {}
    sources = [
        (BACKLOG_DIR / "tasks", False),
        (BACKLOG_DIR / "completed", True),
        (BACKLOG_DIR / "archive" / "tasks", True),
    ]
    for directory, terminal in sources:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            task = parse_task(path, terminal)
            if task:
                tasks[task.id] = task
    return tasks


def load_milestone_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    directory = BACKLOG_DIR / "milestones"
    if not directory.is_dir():
        return titles
    for path in directory.glob("*.md"):
        match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
        if not match:
            continue
        meta = yaml.safe_load(match.group(1)) or {}
        if meta.get("id") and meta.get("title"):
            titles[str(meta["id"]).lower()] = str(meta["title"]).strip()
    return titles


def task_sort_key(task_id: str):
    match = re.search(r"(\d+)", task_id)
    return (int(match.group(1)) if match else 0, task_id)


def desired_labels(task: Task) -> set[str]:
    labels = set(task.labels) | {SYNC_LABEL}
    if task.priority:
        labels.add(f"priority: {task.priority}")
    if task.status.strip().lower() == "in progress":
        labels.add("status: in-progress")
    return labels


def render_body(task: Task, issue_by_task: dict[str, int], nwo: str) -> str:
    blob = f"https://github.com/{nwo}/blob/main/"
    rel_path = task.path.relative_to(REPO_ROOT).as_posix()
    lines = [
        "> [!NOTE]",
        f"> This issue mirrors [`{task.id}`]({blob}{quote(rel_path)}) in this repository's "
        "[Backlog.md](https://github.com/MrLesk/Backlog.md) backlog, which is the source of "
        "truth for planned work.",
        "> Comments are welcome and read by maintainers; the issue body is overwritten on "
        "every sync.",
        "",
        "## Description",
        "",
        task.description or "_No description provided._",
    ]
    if task.acceptance_criteria:
        lines += ["", "## Acceptance Criteria", "", strip_item_indexes(task.acceptance_criteria)]
    if task.definition_of_done:
        lines += ["", "## Definition of Done", "", strip_item_indexes(task.definition_of_done)]
    if task.dependencies:
        lines += ["", "## Dependencies", ""]
        for dep in task.dependencies:
            number = issue_by_task.get(dep)
            lines.append(f"- #{number} (`{dep}`)" if number else f"- `{dep}` (not yet synced)")
    references = [ref for ref in task.references if f"github.com/{nwo}/issues/" not in ref]
    if references:
        lines += ["", "## References", ""]
        for ref in references:
            if ref.startswith("http"):
                lines.append(f"- {ref}")
            elif (REPO_ROOT / ref).exists():
                lines.append(f"- [{ref}]({blob}{quote(ref)})")
            else:
                lines.append(f"- `{ref}`")
    lines += ["", f"<!-- backlog-sync: {task.id} -->"]
    return "\n".join(lines) + "\n"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def ensure_labels(needed: set[str], apply: bool) -> list[str]:
    existing = {label["name"] for label in gh_json("label", "list", "--limit", "300", "--json", "name")}
    missing = sorted(needed - existing)
    for name in missing:
        if apply:
            gh(
                "label", "create", name,
                "--color", LABEL_COLORS.get(name, DEFAULT_LABEL_COLOR),
                "--description", "Managed by backlog issue sync",
            )
    return missing


def ensure_milestones(needed: set[str], apply: bool) -> list[str]:
    existing = {
        milestone["title"]
        for milestone in gh_json("api", "repos/{owner}/{repo}/milestones?state=all&per_page=100")
    }
    missing = sorted(needed - existing)
    for title in missing:
        if apply:
            gh("api", "-X", "POST", "repos/{owner}/{repo}/milestones", "-f", f"title={title}")
    return missing


def write_back_reference(task: Task, issue_url: str) -> None:
    """Append the issue URL to the task's references via the backlog CLI.

    `backlog task edit --ref` REPLACES the reference list, so every existing
    reference must be passed alongside the new one.
    """
    args = ["task", "edit", task.id]
    for ref in [*task.references, issue_url]:
        args += ["--ref", ref]
    result = subprocess.run(["backlog", *args, "--plain"], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  warning: could not write reference back to {task.id}: {result.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="execute the plan (default: dry run)")
    parser.add_argument("--task", action="append", default=[], metavar="TASK_ID",
                        help="limit sync to specific task ids (repeatable)")
    parser.add_argument("--prune", action="store_true",
                        help="close marker issues whose task no longer exists")
    parser.add_argument("--throttle", type=float, default=2.0,
                        help="seconds to sleep between mutating calls (default: 2)")
    args = parser.parse_args()

    if args.prune and args.task:
        parser.error("--prune cannot be combined with --task (orphan detection needs the full task set)")

    nwo = gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    all_tasks = load_tasks()
    milestone_titles = load_milestone_titles()

    if args.task:
        wanted = {t.lower() for t in args.task}
        unknown = wanted - all_tasks.keys()
        if unknown:
            parser.error(f"unknown task ids: {', '.join(sorted(unknown))}")
        selected = {tid: all_tasks[tid] for tid in wanted}
    else:
        selected = all_tasks

    issues = gh_json("issue", "list", "--state", "all", "--limit", "1000",
                     "--json", "number,title,body,state,labels,milestone")
    issue_for_task: dict[str, dict] = {}
    unmanaged_open = 0
    for issue in issues:
        marker = MARKER_RE.search(issue.get("body") or "")
        if marker:
            issue_for_task[marker.group(1)] = issue
        elif issue["state"] == "OPEN":
            unmanaged_open += 1
    issue_number_by_task = {tid: issue["number"] for tid, issue in issue_for_task.items()}

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[{mode}] {nwo}: {len(selected)} task(s) selected, "
          f"{len(issue_for_task)} synced issue(s) found, {unmanaged_open} unmanaged open issue(s) (ignored)\n")

    to_process = [selected[tid] for tid in sorted(selected, key=task_sort_key)]

    needed_labels = set().union(*(desired_labels(task) for task in to_process)) if to_process else set()
    needed_milestones = {
        milestone_titles[task.milestone]
        for task in to_process
        if task.milestone and task.milestone in milestone_titles
    }
    for name in ensure_labels(needed_labels, args.apply):
        print(f"LABEL     create '{name}'")
    for title in ensure_milestones(needed_milestones, args.apply):
        print(f"MILESTONE create '{title}'")

    def throttle():
        if args.apply:
            time.sleep(args.throttle)

    counts = {"create": 0, "update": 0, "close": 0, "reopen": 0, "skip": 0, "prune": 0}

    # Pass 1: create missing issues (in task order, so dependency links to
    # lower-numbered tasks resolve immediately).
    for task in to_process:
        if task.id in issue_number_by_task or task.desired_closed:
            continue
        body = render_body(task, issue_number_by_task, nwo)
        milestone_title = milestone_titles.get(task.milestone, "")
        print(f"CREATE    {task.id}: {task.title[:70]}")
        counts["create"] += 1
        if not args.apply:
            continue
        create_args = ["issue", "create", "--title", task.title, "--body-file", "-"]
        for label in sorted(desired_labels(task)):
            create_args += ["--label", label]
        if milestone_title:
            create_args += ["--milestone", milestone_title]
        url = gh(*create_args, input_text=body)
        number = int(url.rstrip("/").rsplit("/", 1)[1])
        issue_number_by_task[task.id] = number
        issue_for_task[task.id] = {
            "number": number, "title": task.title, "body": body, "state": "OPEN",
            "labels": [{"name": label} for label in desired_labels(task)],
            "milestone": {"title": milestone_title} if milestone_title else None,
        }
        print(f"          -> {url}")
        write_back_reference(task, url)
        throttle()

    # Labels this sync owns and may remove when no longer desired: anything a
    # backlog task declares, plus the sync's own namespaces.
    managed_labels = set().union(*(desired_labels(task) for task in all_tasks.values())) if all_tasks else set()

    # Pass 2: converge existing issues (including ones just created, whose
    # dependency links may have resolved later in pass 1).
    for task in to_process:
        issue = issue_for_task.get(task.id)
        if issue is None:
            if task.desired_closed:
                print(f"SKIP      {task.id}: already done, never synced — not creating")
                counts["skip"] += 1
            continue
        number = issue["number"]
        desired_body = render_body(task, issue_number_by_task, nwo)
        desired = desired_labels(task)
        current_labels = {label["name"] for label in issue.get("labels") or []}
        current_milestone = (issue.get("milestone") or {}).get("title") or ""
        wanted_milestone = milestone_titles.get(task.milestone, "")
        add_labels = sorted(desired - current_labels)
        remove_labels = sorted((current_labels & managed_labels) - desired)
        content_differs = (
            normalize(issue.get("body") or "") != normalize(desired_body)
            or issue.get("title", "") != task.title
            or add_labels or remove_labels
            or current_milestone != wanted_milestone
        )

        if content_differs:
            print(f"UPDATE    #{number} {task.id}")
            counts["update"] += 1
            if args.apply:
                edit_args = ["issue", "edit", str(number), "--title", task.title, "--body-file", "-"]
                for label in add_labels:
                    edit_args += ["--add-label", label]
                for label in remove_labels:
                    edit_args += ["--remove-label", label]
                if wanted_milestone and wanted_milestone != current_milestone:
                    edit_args += ["--milestone", wanted_milestone]
                elif current_milestone and not wanted_milestone:
                    edit_args += ["--remove-milestone"]
                gh(*edit_args, input_text=desired_body)
                throttle()

        is_closed = issue["state"] == "CLOSED"
        if task.desired_closed and not is_closed:
            print(f"CLOSE     #{number} {task.id} (task is done)")
            counts["close"] += 1
            if args.apply:
                gh("issue", "close", str(number), "--comment",
                   f"Closed by backlog sync: `{task.id}` is done.")
                throttle()
        elif not task.desired_closed and is_closed:
            print(f"REOPEN    #{number} {task.id} (task is active in the backlog)")
            counts["reopen"] += 1
            if args.apply:
                gh("issue", "reopen", str(number), "--comment",
                   f"Reopened by backlog sync: `{task.id}` is active in the backlog.")
                throttle()
        elif not content_differs:
            counts["skip"] += 1

    if args.prune:
        for task_id, issue in sorted(issue_for_task.items()):
            if task_id not in all_tasks and issue["state"] == "OPEN":
                print(f"PRUNE     #{issue['number']} ({task_id} no longer exists in the backlog)")
                counts["prune"] += 1
                if args.apply:
                    gh("issue", "close", str(issue["number"]), "--comment",
                       f"Closed by backlog sync: `{task_id}` was removed from the backlog.")
                    throttle()

    print(f"\nSummary: {counts['create']} create, {counts['update']} update, {counts['close']} close, "
          f"{counts['reopen']} reopen, {counts['prune']} prune, {counts['skip']} unchanged")
    if not args.apply and any(counts[k] for k in ("create", "update", "close", "reopen", "prune")):
        print("Dry run — re-run with --apply to execute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
