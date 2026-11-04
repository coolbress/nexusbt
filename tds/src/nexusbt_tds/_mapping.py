"""`read_mapping(text)`: a mapping file as JSON, else as the YAML subset TDS 9.5 names (#257).

The subset: block `key: value` nested by indentation, `- ` list items, the flow forms `{a: b}`
and `[a, b]`, single- and double-quoted strings and `#` comments. A plain value is text, never
a number or a boolean. Anything else (anchors, tags, block scalars) is a `ValueError` naming the
line: the person writes that part as JSON instead. Kept beside pyarrow-only (spec 2.3).
"""

from __future__ import annotations

import json
from typing import Any

_UNSUPPORTED = tuple("&*!|>%@`")


def read_mapping(text: str) -> Any:
    text = text.removeprefix("﻿")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        if text.lstrip()[:1] == "{":  # meant as JSON: JSON's own error, not a YAML one
            raise ValueError(f"line {exc.lineno}: not JSON ({exc.msg})") from None
    lines = []
    for n, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise _error(n, "a tab in the indentation")
        body = _strip_comment(raw, n).rstrip()
        if body.strip():
            lines.append((n, len(body) - len(body.lstrip()), body.strip()))
    if not lines:
        return None  # YAML's empty document; the caller says what it needed
    value, end = _block(lines, 0, lines[0][1])
    if end < len(lines):
        raise _error(lines[end][0], "indentation does not match the lines above")
    return value


def _error(n: int, what: str) -> ValueError:
    return ValueError(f"line {n}: {what}; write this part as JSON")


def _strip_comment(raw: str, n: int) -> str:
    quote = None
    for i, ch in enumerate(raw):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "\"'" and (i == 0 or raw[i - 1] in " :[{,-"):
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            return raw[:i]
    if quote:
        raise _error(n, "a quote is not closed")
    return raw


def _block(lines: list[tuple[int, int, str]], i: int, indent: int) -> tuple[Any, int]:
    """The block starting at `lines[i]`, whose lines sit at `indent`; returns the next index."""
    is_list = _item(lines[i][2])
    out: Any = [] if is_list else {}
    while i < len(lines) and lines[i][1] == indent:
        n, _, body = lines[i]
        if is_list != _item(body):
            if is_list:  # `key:` then its `- ` items at the key's own indent: the list ends
                break
            raise _error(n, "list items and keys mixed at one level")
        if is_list:
            rest = body[1:].lstrip()
            if rest and _split(rest, n) is not None:  # `- key: v`: a block at the key's column
                lines[i] = (n, indent + len(body) - len(rest), rest)
                item, i = _block(lines, i, lines[i][1])
            elif rest:
                item, i = _scalar(rest, n), i + 1
            elif i + 1 < len(lines) and lines[i + 1][1] > indent:  # `-` then a nested block
                item, i = _block(lines, i + 1, lines[i + 1][1])
            else:
                item, i = None, i + 1
            out.append(item)
            continue
        split = _split(body, n)
        if split is None:
            raise _error(n, "not a `key: value` line")
        key, rest = split
        if key in out:
            raise _error(n, f"key {key!r} given twice")
        i += 1
        if rest:
            out[key] = _scalar(rest, n)
        elif i < len(lines) and (lines[i][1] > indent or _item(lines[i][2])):
            out[key], i = _block(lines, i, lines[i][1])
        else:
            out[key] = None
    return out, i


def _item(body: str) -> bool:
    return body == "-" or body.startswith("- ")


def _split(body: str, n: int) -> tuple[str, str] | None:
    """`key: rest` at the first `:` outside quotes that ends the line or has a space after it."""
    if body[0] in "{[":
        return None
    key, end = _token(body, 0, n, ":")
    if end < len(body) and body[end] == ":" and body[end + 1 : end + 2] in ("", " "):
        return key, body[end + 1 :].strip()
    return None


def _scalar(text: str, n: int) -> Any:
    """A block value: a flow form or a quoted string, else the whole rest of the line as text."""
    if text[0] not in "{[\"'":
        _reject_unsupported(text, 0, n)
        return text
    value, end = _flow(text, 0, n)
    if text[end:].strip():
        raise _error(n, f"unexpected {text[end:].strip()!r}")
    return value


def _flow(text: str, i: int, n: int) -> tuple[Any, int]:
    i = _skip(text, i)
    if text[i : i + 1] not in ("{", "["):
        return _token(text, i, n, ",]}")
    close = "}" if text[i] == "{" else "]"
    out: dict[str, Any] | list[Any] = {} if close == "}" else []
    i += 1
    while True:
        i = _skip(text, i)
        if text[i : i + 1] == close:
            return out, i + 1
        if isinstance(out, dict):
            key, i = _token(text, i, n, ":,}")
            if text[i : i + 1] != ":":
                raise _error(n, f"no `:` after {key!r}")
            if key in out:
                raise _error(n, f"key {key!r} given twice")
            out[key], i = _flow(text, i + 1, n)
        else:
            item, i = _flow(text, i, n)
            out.append(item)
        i = _skip(text, i)
        if text[i : i + 1] == ",":
            i += 1
        elif text[i : i + 1] != close:
            raise _error(n, f"no `,` or `{close}` in {text!r}")


def _token(text: str, i: int, n: int, stops: str) -> tuple[str, int]:
    """A quoted or plain string at `i`; a plain one ends at a stop (`:` only before a space)."""
    i = _skip(text, i)
    if text[i : i + 1] == '"':
        end = i + 1
        while end < len(text) and text[end] != '"':
            end += 2 if text[end] == "\\" else 1
        if end >= len(text):
            raise _error(n, "a quote is not closed")
        try:
            return json.loads(text[i : end + 1]), end + 1
        except json.JSONDecodeError as exc:
            raise _error(n, f"a double-quoted string JSON does not read ({exc.msg})") from None
    if text[i : i + 1] == "'":
        end = i + 1
        while (end := text.find("'", end)) != -1 and text[end + 1 : end + 2] == "'":
            end += 2
        if end == -1:  # pragma: no cover (`_strip_comment` refused an unclosed quote first)
            raise _error(n, "a quote is not closed")
        return text[i + 1 : end].replace("''", "'"), end + 1
    _reject_unsupported(text, i, n)
    start = i
    while i < len(text) and text[i] not in stops.replace(":", ""):
        if text[i] == ":" and ":" in stops and text[i + 1 : i + 2] in ("", " ", ",", "]", "}"):
            break
        i += 1
    if not text[start:i].strip():
        raise _error(n, "an empty value")
    return text[start:i].strip(), i


def _reject_unsupported(text: str, i: int, n: int) -> None:
    """Anchors, aliases, tags, block scalars, directives, nested `- ` and `? ` keys."""
    if text[i : i + 1] in _UNSUPPORTED or text[i : i + 2] in ("- ", "? ") or text[i:] == "-":
        raise _error(n, f"{text[i:]!r} is outside the YAML forms read here")


def _skip(text: str, i: int) -> int:
    while i < len(text) and text[i] == " ":
        i += 1
    return i
