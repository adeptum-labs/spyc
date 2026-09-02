# spyc is a terminal viewer for browsing code bases.
# Copyright © 2026 Adam Waldenberg, Adeptum AB, Org.nr 559494-1824.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Website: https://www.adeptum.se
# Contact: info@adeptum.se


import pytest
from tree_sitter import Query

from spyc.languages import LANGUAGES, LANGUAGES_BY_ID
from spyc.syntax.factory import make_highlighter
from spyc.syntax.grammars import load_grammar

GRAMMAR_LANGUAGES = [language for language in LANGUAGES if language.grammar]
SAMPLES = {
    "bash": ('echo "hi"', '"hi"', "string"),
    "c": ("int main() { return 0; }", "return", "keyword"),
    "cpp": ("class A { public: int x; };", "class", "keyword"),
    "css": ("a { color: red; }", "color", "property"),
    "go": ("package main\nfunc main() {}\n", "func", "keyword"),
    "html": ('<div class="a">x</div>', "div", "tag"),
    "java": ("class A { void f() {} }", "class", "keyword"),
    "javascript": ('const x = "a";', "const", "keyword"),
    "json": ('{"a": 1}', "1", "number"),
    "kotlin": ("fun main() { val x = 1 }", "fun", "keyword"),
    "python": ("def f():\n    return 1\n", "def", "keyword"),
    "rust": ("fn main() { let x = 1; }", "fn", "keyword"),
    "scss": (".a { color: red; }", "color", "property"),
    "sql": ("SELECT * FROM t;", "SELECT", "keyword"),
    "toml": ("[a]\nb = 1\n", "1", "number"),
    "tsx": ("const a = <b/>;", "const", "keyword"),
    "typescript": ("let x: number = 1;", "let", "keyword"),
    "xml": ('<a b="cc"/>', "cc", "string"),
    "yaml": ('a: "b"\n', '"b"', "string"),
}


def capture_at(highlighter, text, needle):
    offset = text.index(needle)
    row, column = text.count("\n", 0, offset), offset - (text.rfind("\n", 0, offset) + 1)
    covering = [span for span in highlighter.spans(row, row + 1)[0] if span.start <= column < span.end]
    return covering[0].capture.split(".")[0] if covering else None


def test_every_grammar_language_has_a_sample():
    assert {language.id for language in GRAMMAR_LANGUAGES} == set(SAMPLES)


@pytest.mark.parametrize("language", GRAMMAR_LANGUAGES, ids=lambda language: language.id)
def test_grammar_loads_and_its_query_compiles(language):
    ts_language, query_source = load_grammar(language)
    Query(ts_language, query_source)


@pytest.mark.parametrize("language_id", sorted(SAMPLES))
def test_sample_source_is_highlighted(language_id):
    text, needle, expected = SAMPLES[language_id]
    highlighter = make_highlighter(LANGUAGES_BY_ID[language_id], text)
    assert capture_at(highlighter, text, needle) == expected


def test_language_without_a_grammar_uses_pygments():
    text = "key = value\n"
    assert capture_at(make_highlighter(LANGUAGES_BY_ID["properties"], text), text, "value") is not None


def test_no_language_means_no_highlighting():
    assert make_highlighter(None, "def f(): pass\n").spans(0, 1) == [[]]


def test_a_broken_grammar_falls_back_to_pygments(monkeypatch):
    monkeypatch.setattr("spyc.syntax.factory.load_grammar", lambda language: None)
    text = "def f(): pass\n"
    assert capture_at(make_highlighter(LANGUAGES_BY_ID["python"], text), text, "def") == "keyword"
