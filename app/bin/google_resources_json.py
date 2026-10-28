"""Print a production ``.env`` text's ``GOOGLE_RESOURCES`` value as compact JSON, read the way the app reads it.

``app/bin/entry.sh`` concatenates the SSM blobs into ``.env``; pydantic-settings reads that file through
python-dotenv, which removes the quoting and escapes, and ``GoogleResourcesConfig`` then strips one more pair of
outer quotes and parses the JSON. A plain ``sed`` over the blob line skips the dotenv step, so this helper repeats
both steps exactly and prints the mapping for ``jq``.

Usage: the blobs on stdin, in entry.sh order (``bin/deploy-checks.zsh pre google_ids`` and the TASK-111.10.3
put-parameter loop). Never prints a value on error. Delete it with the ``google_ids`` check once TASK-111.10.3 is
Done.
"""

import io
import json
import sys

from dotenv import dotenv_values


def google_resources(env_text: str) -> dict[str, object]:
    """The parsed GOOGLE_RESOURCES mapping, or ValueError naming what is wrong (never the value)."""
    raw = dotenv_values(stream=io.StringIO(env_text)).get("GOOGLE_RESOURCES")
    if not raw:
        raise ValueError("no GOOGLE_RESOURCES line")
    text = raw.strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "'\"":
        text = text[1:-1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"GOOGLE_RESOURCES is not JSON after dotenv parsing ({error.msg}, char {error.pos})") from None
    if not isinstance(parsed, dict):
        raise ValueError("GOOGLE_RESOURCES is not a JSON object")
    return parsed


def main() -> None:
    try:
        print(json.dumps(google_resources(sys.stdin.read()), separators=(",", ":")))
    except ValueError as error:
        print(f"google_resources_json: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
