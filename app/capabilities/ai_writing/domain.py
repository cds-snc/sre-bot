"""Template-fill values and the rules that read a model's JSON answer.

A template is an ordered list of sections, each a heading with its instructions, plus optional
fields filled in the same answer. The model answers with one JSON object keyed by heading or
label. Models do not reliably emit bare JSON, so reading is forgiving: code fences and prose
around the object are ignored, list and object values are flattened into text, keys are matched
to headings despite numbering, case or punctuation drift, and the complete pairs of an object
cut off mid-answer are salvaged. ``extract_json_object`` is the strict first stage on its own,
for a caller that refuses any partial or malformed answer.
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_FENCED = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_PAIR = re.compile(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"')


@dataclass(frozen=True)
class TemplateSection:
    """One section to fill: its heading and the caller's instructions for it."""

    heading: str
    instructions: str = ""


@dataclass(frozen=True)
class TemplateField:
    """One short value filled in the same answer as the sections, with optional instructions."""

    label: str
    instructions: str = ""


@dataclass(frozen=True)
class TemplateAnswer:
    """The answer for one requested heading or label; ``text`` is ``""`` when unanswered."""

    key: str
    text: str


@dataclass(frozen=True)
class FilledTemplate:
    """One answer per requested section and field, in request order.

    ``truncated`` says the model's answer was cut off and only its complete pairs were kept: an
    unanswered section is then an artefact of the cutoff, not the model's judgement.
    """

    sections: tuple[TemplateAnswer, ...]
    fields: tuple[TemplateAnswer, ...]
    truncated: bool


@dataclass(frozen=True)
class AnswerMatch:
    """Shape of how a model's answer keys met the requested keys, for logging only."""

    key_count: int
    unmatched_key_count: int
    blank_key_count: int
    blank_requested: tuple[str, ...]


def extract_json_object(raw: str) -> dict[str, object] | None:
    """Return the first complete JSON object in ``raw``, or ``None`` when there is none.

    Prose and code fences around the object are tolerated; a truncated object, a non-object
    value or malformed JSON gives ``None``. Values are returned as decoded, never coerced.
    """
    start = raw.find("{")
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(raw, start)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def parse_answers(raw: str) -> tuple[dict[str, str] | None, bool]:
    """Read the model output into ``(answers, truncated)``.

    A complete object gives its non-empty answers and ``truncated`` false. Otherwise the complete
    ``"key": "value"`` pairs that did arrive are salvaged and ``truncated`` is true. ``answers``
    is ``None`` only when nothing usable was recovered.
    """
    text = raw.strip()
    fenced = _FENCED.search(text)
    if fenced:
        text = fenced.group(1).strip()

    parsed = extract_json_object(text)
    if parsed is not None:
        return {str(key): answer for key, value in parsed.items() if (answer := coerce_answer(value))}, False

    return _salvage_pairs(text) or None, True


def coerce_answer(value: object) -> str:
    """Normalise one JSON value into text, or ``""`` if unusable.

    Asking for one item per line tempts a model into a JSON array instead of a newline-joined
    string, so lists are joined back into lines, and object entries are flattened in field order.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(line for item in value if (line := coerce_answer(item).strip()))
    if isinstance(value, dict):
        return " ".join(str(item).strip() for item in value.values() if str(item).strip())
    return ""


def _salvage_pairs(text: str) -> dict[str, str]:
    """Recover the complete ``"key": "value"`` pairs of an answer that does not parse."""
    pairs: dict[str, str] = {}
    for raw_key, raw_value in _PAIR.findall(text):
        try:
            key = json.loads(f'"{raw_key}"')
            value = json.loads(f'"{raw_value}"')
        except ValueError:
            continue
        pairs[key] = value
    return pairs


def normalize_heading(text: str) -> str:
    """Reduce a heading to a comparable form: no numbering, case or punctuation."""
    without_numbering = re.sub(r"^\s*\d+\s*[.)\-:]\s*", "", text)
    alphanumeric = re.sub(r"[^a-z0-9 ]+", " ", without_numbering.lower())
    return re.sub(r"\s+", " ", alphanumeric).strip()


def match_answer(key: str, answers: Mapping[str, str]) -> str:
    """Find the answer for ``key``, tolerating drift: exact first, then normalised.

    Models rarely echo a heading byte-for-byte: they drop numbering, change case or add
    punctuation. When two answer keys normalise alike, the later one wins.
    """
    exact = (answers.get(key) or "").strip()
    if exact:
        return exact
    lookup = {normalize_heading(answer_key): value for answer_key, value in answers.items()}
    return (lookup.get(normalize_heading(key)) or "").strip()


def fill(
    answers: Mapping[str, str],
    sections: Sequence[TemplateSection],
    fields: Sequence[TemplateField],
    *,
    truncated: bool,
) -> FilledTemplate:
    """Pair every requested section and field with its answer, in request order."""
    return FilledTemplate(
        sections=tuple(TemplateAnswer(s.heading, match_answer(s.heading, answers)) for s in sections),
        fields=tuple(TemplateAnswer(f.label, match_answer(f.label, answers)) for f in fields),
        truncated=truncated,
    )


def describe_match(answers: Mapping[str, str], filled: FilledTemplate) -> AnswerMatch:
    """Count the answer keys that matched no requested key, and name the requested sections left blank."""
    requested = {normalize_heading(answer.key) for answer in (*filled.sections, *filled.fields)}
    return AnswerMatch(
        key_count=len(answers),
        unmatched_key_count=sum(1 for key in answers if normalize_heading(key) not in requested),
        blank_key_count=sum(1 for value in answers.values() if not value.strip()),
        blank_requested=tuple(answer.key for answer in filled.sections if not answer.text),
    )
