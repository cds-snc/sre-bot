---
name: python-314-baseline
description: Authoritative CPython 3.14 syntax and stdlib baseline for this repo. Use whenever code looks like invalid Python, before "fixing" unfamiliar syntax, when adding type annotations, or when a linter/model flags except-clauses, annotations, generics, or t-strings.
---

# Python 3.14 Baseline

This repository targets **CPython 3.14** (`app/.python-version` = `3.14`,
`requires-python = ">=3.14"`, mypy `python_version = "3.14"`).

Verify before doubting: `cd app && uv run python -V`.

## Do Not "Fix" These — They Are Valid 3.14

### PEP 758 — parenthesis-free multiple exception types

```python
except ValueError, TypeError:        # valid; identical to except (ValueError, TypeError):
except* ValueError, TypeError:       # valid for exception groups
except (ValueError, TypeError) as exc:   # parens still REQUIRED with `as`
```

This is **not** the removed Python 2 `except Exception, name:` form. Do not
rewrite it, do not report it as a syntax error, do not "investigate why it parses".

### PEP 649/749 — lazy annotation evaluation

- Annotations are evaluated lazily by default.
- `from __future__ import annotations` is **unnecessary and itself deprecated** —
  remove it from new code, do not add it.
- String-quoted forward references are no longer required.
- Introspect annotations with `annotationlib`, not `typing.get_type_hints` hacks.

### PEP 750 — t-strings

`t'...'` produces a `string.templatelib.Template`, not a `str`. Use for
structured interpolation where the consumer needs the parts.

### PEP 765 — control flow in `finally`

`return` / `break` / `continue` leaving a `finally` block emits `SyntaxWarning`.
Restructure rather than suppress.

### Also available (3.12 / 3.13)

- PEP 695 — `type Alias = ...` and `def f[T](x: T) -> T: ...`
- PEP 696 — type-parameter defaults
- PEP 701 — unrestricted f-string nesting and quoting
- `warnings.deprecated` decorator
- PEP 734 — `concurrent.interpreters`
- PEP 784 — `compression.zstd`

## Typing Gotcha

`typing.Union` and `types.UnionType` are the **same runtime type** in 3.14.
Compare unions with `==`, never `is`.

## Removed in 3.14 — Do Not Use

| Removed | Replacement |
| --- | --- |
| `asyncio` child watchers | default event loop child handling |
| implicit loop creation in `asyncio.get_event_loop()` | `asyncio.run` / `get_running_loop` |
| `ast.Num`, `ast.Str`, `ast.Bytes` | `ast.Constant` |
| `pkgutil.get_loader` | `importlib.util.find_spec` |
| `sqlite3.version` | `sqlite3.sqlite_version` |

## Resolution Order When Unsure

1. Check this file.
2. Run it: `cd app && uv run python -c '<snippet>'`.
3. Check [What's new in Python 3.14](https://docs.python.org/3/whatsnew/3.14.html)
   or the specific PEP ([758](https://peps.python.org/pep-0758/),
   [649](https://peps.python.org/pep-0649/), [750](https://peps.python.org/pep-0750/)).

Never resolve from training-data recall — models trained before 3.14 consistently
misjudge PEP 758 and PEP 649 syntax as errors.
