"""Tests for the DCS Lua table parser."""

import pytest

from afterburner.parsers.lua_table import LuaParseError, loads

# ------------------------------------------------------------------
# Basic types
# ------------------------------------------------------------------


def test_empty_table():
    assert loads("t = {}") == {}


def test_string_value():
    assert loads('t =\n{\n["key"] =\n"value",\n}') == {"key": "value"}


def test_single_quoted_string():
    assert loads("t =\n{\n['key'] =\n'value',\n}") == {"key": "value"}


def test_integer():
    assert loads('t =\n{\n["n"] =\n42,\n}') == {"n": 42}


def test_negative_integer():
    assert loads('t =\n{\n["n"] =\n-5,\n}') == {"n": -5}


def test_float():
    result = loads('t =\n{\n["x"] =\n-100000.0,\n}')
    assert result["x"] == pytest.approx(-100000.0)


def test_scientific_notation():
    result = loads('t =\n{\n["v"] =\n1.5e+3,\n}')
    assert result["v"] == pytest.approx(1500.0)


def test_boolean_true():
    assert loads('t =\n{\n["flag"] =\ntrue,\n}') == {"flag": True}


def test_boolean_false():
    assert loads('t =\n{\n["flag"] =\nfalse,\n}') == {"flag": False}


def test_nil_value():
    assert loads('t =\n{\n["x"] =\nnil,\n}') == {"x": None}


# ------------------------------------------------------------------
# Array conversion
# ------------------------------------------------------------------


def test_integer_keys_become_list():
    result = loads('t =\n{\n[1] =\n"a",\n[2] =\n"b",\n[3] =\n"c",\n}')
    assert result == ["a", "b", "c"]


def test_non_consecutive_keys_stay_dict():
    result = loads('t =\n{\n[1] =\n"a",\n[3] =\n"c",\n}')
    assert isinstance(result, dict)
    assert result[1] == "a"
    assert result[3] == "c"


# ------------------------------------------------------------------
# Nesting and DCS-style whitespace
# ------------------------------------------------------------------


def test_nested_tables():
    text = """\
mission =
{
["coalition"] =
{
["blue"] =
{
["name"] =
"USA",
},
},
}"""
    result = loads(text)
    assert result["coalition"]["blue"]["name"] == "USA"


def test_array_of_dicts():
    text = """\
data =
{
[1] =
{
["id"] =
1,
["name"] =
"Alpha",
},
[2] =
{
["id"] =
2,
["name"] =
"Bravo",
},
}"""
    result = loads(text)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["name"] == "Alpha"
    assert result[1]["id"] == 2


# ------------------------------------------------------------------
# Long strings
# ------------------------------------------------------------------


def test_long_string_value():
    text = """\
t =
{
["script"] =
[[
local x = 1
]],
}"""
    result = loads(text)
    assert "x = 1" in result["script"]


def test_long_string_level1():
    text = 't =\n{\n["s"] =\n[=[hello]=],\n}'
    result = loads(text)
    assert result["s"] == "hello"


# ------------------------------------------------------------------
# Comments
# ------------------------------------------------------------------


def test_line_comment_skipped():
    text = """\
-- top-level comment
t =
{
["key"] = -- inline
"value", -- trailing
}"""
    assert loads(text) == {"key": "value"}


def test_long_comment_skipped():
    text = """\
--[[
  block comment
]]
t =
{
["key"] =
"value",
}"""
    assert loads(text) == {"key": "value"}


# ------------------------------------------------------------------
# String escape sequences
# ------------------------------------------------------------------


def test_escaped_quote_in_string():
    text = 't =\n{\n["k"] =\n"say \\"hi\\"",\n}'
    result = loads(text)
    assert result["k"] == 'say "hi"'


def test_escaped_newline_in_string():
    text = 't =\n{\n["k"] =\n"line1\\nline2",\n}'
    assert loads(text)["k"] == "line1\nline2"


# ------------------------------------------------------------------
# Error cases
# ------------------------------------------------------------------


def test_unterminated_string_raises():
    with pytest.raises(LuaParseError):
        loads('t = { ["key"] = "unterminated }')


def test_unterminated_table_raises():
    with pytest.raises(LuaParseError):
        loads('t = { ["key"] = "value"')


def test_bad_number_raises():
    with pytest.raises(LuaParseError):
        loads('t = { ["n"] = @invalid }')


# ------------------------------------------------------------------
# Trailing comma tolerance (DCS always emits them)
# ------------------------------------------------------------------


def test_trailing_comma():
    text = 't =\n{\n["a"] =\n1,\n["b"] =\n2,\n}'
    assert loads(text) == {"a": 1, "b": 2}


def test_no_trailing_comma():
    text = 't =\n{\n["a"] =\n1\n}'
    assert loads(text) == {"a": 1}
