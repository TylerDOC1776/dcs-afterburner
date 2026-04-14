"""
Parse DCS Lua table literals into Python dicts/lists.

DCS mission files use a restricted subset of Lua: data-only tables with
string keys, integer keys, string values, number values, and booleans.
No functions, closures, or metatables appear in the parseable files.

Top-level files are assignments:  name = { ... }
We discard the name and return the table value.
"""

from __future__ import annotations

import re
from typing import Any

_NUMBER_RE = re.compile(
    r"-?(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)"
)


class LuaParseError(Exception):
    pass


def loads(text: str) -> Any:
    """Parse a DCS Lua table file and return the Python equivalent."""
    return _Parser(text).parse_file()


class _Parser:
    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0
        self._len = len(text)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def parse_file(self) -> Any:
        """Strip a leading `name =` assignment and return the value."""
        self._skip()
        if self._pos < self._len and (
            self._text[self._pos].isalpha() or self._text[self._pos] == "_"
        ):
            self._consume_identifier()
            self._skip()
            if self._pos < self._len and self._text[self._pos] == "=":
                # Guard against == (shouldn't appear at file scope, but be safe)
                if self._pos + 1 < self._len and self._text[self._pos + 1] != "=":
                    self._pos += 1
                    self._skip()
        return self._parse_value()

    # ------------------------------------------------------------------
    # Value dispatch
    # ------------------------------------------------------------------

    def _parse_value(self) -> Any:
        self._skip()
        if self._pos >= self._len:
            raise LuaParseError("Unexpected end of input")

        c = self._text[self._pos]

        if c == "{":
            return self._parse_table()
        if c in ('"', "'"):
            return self._parse_quoted_string()
        if (
            c == "["
            and self._pos + 1 < self._len
            and self._text[self._pos + 1] in ("[", "=")
        ):
            return self._parse_long_string()
        if (
            c == "-"
            or c.isdigit()
            or (
                c == "."
                and self._pos + 1 < self._len
                and self._text[self._pos + 1].isdigit()
            )
        ):
            return self._parse_number()
        if self._text[self._pos : self._pos + 4] == "true":
            self._pos += 4
            return True
        if self._text[self._pos : self._pos + 5] == "false":
            self._pos += 5
            return False
        if self._text[self._pos : self._pos + 3] == "nil":
            self._pos += 3
            return None
        # Bare identifier as value (rare in DCS tables but handle it)
        return self._consume_identifier()

    # ------------------------------------------------------------------
    # Table parser
    # ------------------------------------------------------------------

    def _parse_table(self) -> dict | list:
        self._pos += 1  # skip {
        items: dict[Any, Any] = {}
        auto_idx = 1

        while True:
            self._skip()
            if self._pos >= self._len:
                raise LuaParseError("Unterminated table")
            if self._text[self._pos] == "}":
                self._pos += 1
                break

            key, value = self._parse_field()
            if key is None:
                items[auto_idx] = value
                auto_idx += 1
            else:
                items[key] = value

            self._skip()
            if self._pos < self._len and self._text[self._pos] in ",;":
                self._pos += 1

        # Convert to list when all keys are consecutive ints starting at 1
        if items and all(isinstance(k, int) for k in items):
            keys = sorted(items)
            if keys == list(range(1, len(keys) + 1)):
                return [items[k] for k in keys]

        return items

    def _parse_field(self) -> tuple[Any, Any]:
        self._skip()
        c = self._text[self._pos]

        if c == "[":
            next_c = self._text[self._pos + 1] if self._pos + 1 < self._len else ""

            if next_c in ('"', "'"):
                # ["key"] or ['key']
                self._pos += 1  # skip [
                key = self._parse_quoted_string()
                self._skip()
                if self._pos >= self._len or self._text[self._pos] != "]":
                    raise LuaParseError(
                        f"Expected ']' after string key at pos {self._pos}"
                    )
                self._pos += 1  # skip ]
                self._skip()
                if self._pos >= self._len or self._text[self._pos] != "=":
                    raise LuaParseError(f"Expected '=' after key at pos {self._pos}")
                self._pos += 1  # skip =
                return key, self._parse_value()

            if next_c in ("[", "="):
                # [[long string]] as positional value — not a key in DCS tables
                return None, self._parse_value()

            # [number] key
            self._pos += 1  # skip [
            key = self._parse_number()
            self._skip()
            if self._pos >= self._len or self._text[self._pos] != "]":
                raise LuaParseError(
                    f"Expected ']' after numeric key at pos {self._pos}"
                )
            self._pos += 1  # skip ]
            self._skip()
            if self._pos >= self._len or self._text[self._pos] != "=":
                raise LuaParseError(f"Expected '=' after key at pos {self._pos}")
            self._pos += 1  # skip =
            return key, self._parse_value()

        if c.isalpha() or c == "_":
            ident = self._consume_identifier()
            self._skip()
            if self._pos < self._len and self._text[self._pos] == "=":
                # Guard against == comparison operator
                if self._pos + 1 < self._len and self._text[self._pos + 1] == "=":
                    return None, self._bare_keyword(ident)
                self._pos += 1  # skip =
                return ident, self._parse_value()
            return None, self._bare_keyword(ident)

        # Positional value
        return None, self._parse_value()

    def _bare_keyword(self, ident: str) -> Any:
        if ident == "true":
            return True
        if ident == "false":
            return False
        if ident == "nil":
            return None
        return ident

    # ------------------------------------------------------------------
    # Terminals
    # ------------------------------------------------------------------

    def _parse_quoted_string(self) -> str:
        quote = self._text[self._pos]
        self._pos += 1
        parts: list[str] = []

        while self._pos < self._len:
            c = self._text[self._pos]
            if c == quote:
                self._pos += 1
                return "".join(parts)
            if c == "\\":
                self._pos += 1
                if self._pos >= self._len:
                    raise LuaParseError("Unterminated escape sequence")
                esc = self._text[self._pos]
                self._pos += 1
                if esc == "n":
                    parts.append("\n")
                elif esc == "t":
                    parts.append("\t")
                elif esc == "r":
                    parts.append("\r")
                elif esc in ("\\", '"', "'"):
                    parts.append(esc)
                elif esc.isdigit():
                    digits = esc
                    while (
                        self._pos < self._len
                        and self._text[self._pos].isdigit()
                        and len(digits) < 3
                    ):
                        digits += self._text[self._pos]
                        self._pos += 1
                    parts.append(chr(int(digits)))
                else:
                    parts.append(esc)
            else:
                parts.append(c)
                self._pos += 1

        raise LuaParseError("Unterminated string literal")

    def _parse_long_string(self) -> str:
        """Parse [[...]] or [=[...]=] long strings. pos must be at the first [."""
        if self._pos >= self._len or self._text[self._pos] != "[":
            raise LuaParseError(f"Expected '[' at pos {self._pos}")
        self._pos += 1  # skip first [

        level = 0
        while self._pos < self._len and self._text[self._pos] == "=":
            level += 1
            self._pos += 1

        if self._pos >= self._len or self._text[self._pos] != "[":
            raise LuaParseError(
                f"Malformed long string (expected second '[') at pos {self._pos}"
            )
        self._pos += 1  # skip second [

        # Skip the immediately following newline (Lua convention)
        if self._pos < self._len and self._text[self._pos] == "\n":
            self._pos += 1
        elif (
            self._pos + 1 < self._len
            and self._text[self._pos : self._pos + 2] == "\r\n"
        ):
            self._pos += 2

        close = "]" + "=" * level + "]"
        end = self._text.find(close, self._pos)
        if end == -1:
            raise LuaParseError(f"Unterminated long string (level {level})")
        result = self._text[self._pos : end]
        self._pos = end + len(close)
        return result

    def _parse_number(self) -> int | float:
        m = _NUMBER_RE.match(self._text, self._pos)
        if not m:
            raise LuaParseError(
                f"Expected number at pos {self._pos}: {self._text[self._pos : self._pos + 20]!r}"
            )
        self._pos = m.end()
        s = m.group()
        if "0x" in s.lower():
            return int(s, 16)
        if "." in s or "e" in s.lower():
            return float(s)
        return int(s)

    def _consume_identifier(self) -> str:
        start = self._pos
        while self._pos < self._len and (
            self._text[self._pos].isalnum() or self._text[self._pos] == "_"
        ):
            self._pos += 1
        if self._pos == start:
            raise LuaParseError(
                f"Expected identifier at pos {self._pos}: {self._text[self._pos : self._pos + 10]!r}"
            )
        return self._text[start : self._pos]

    # ------------------------------------------------------------------
    # Whitespace + comment skipper
    # ------------------------------------------------------------------

    def _skip(self) -> None:
        while self._pos < self._len:
            c = self._text[self._pos]

            if c in " \t\n\r":
                self._pos += 1
                continue

            if self._text[self._pos : self._pos + 2] == "--":
                j = self._pos + 2
                # Long comment: --[=*[
                if j < self._len and self._text[j] == "[":
                    k = j + 1
                    eq_count = 0
                    while k < self._len and self._text[k] == "=":
                        eq_count += 1
                        k += 1
                    if k < self._len and self._text[k] == "[":
                        self._pos = k + 1
                        close = "]" + "=" * eq_count + "]"
                        end = self._text.find(close, self._pos)
                        if end == -1:
                            raise LuaParseError("Unterminated long comment")
                        self._pos = end + len(close)
                        continue
                # Line comment: -- to newline
                self._pos = j
                while self._pos < self._len and self._text[self._pos] != "\n":
                    self._pos += 1
                continue

            break
