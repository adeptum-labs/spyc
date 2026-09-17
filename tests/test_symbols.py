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

from spyc.languages import LANGUAGES, LANGUAGES_BY_ID
from spyc.symbols import Symbol, symbols_of

SAMPLES = {
    "python": ("class A:\n    def m(self): pass\n\ndef f(): pass\n", {("A", 1), ("m", 2), ("f", 4)}),
    "java": ("class A { void m() {} }\ninterface I {}\n", {("A", 1), ("m", 1), ("I", 2)}),
    "kotlin": ("class A { fun m() {} }\nfun f() {}\nobject O\ninterface I\n", {("A", 1), ("m", 1), ("f", 2), ("O", 3), ("I", 4)}),
    "go": ("package main\nfunc f() {}\ntype T struct{}\nfunc (t T) m() {}\n", {("f", 2), ("T", 3), ("m", 4)}),
    "rust": ("fn f() {}\nstruct S;\nimpl S { fn m() {} }\ntrait Tr {}\n", {("f", 1), ("S", 2), ("m", 3), ("Tr", 4)}),
    "javascript": ("function f() {}\nclass A { m() {} }\nconst g = () => 1;\n", {("f", 1), ("A", 2), ("m", 2), ("g", 3)}),
    "typescript": ("interface I {}\nfunction f() {}\nclass A { m() {} }\ntype T = string;\nenum E {}\n",
                   {("I", 1), ("f", 2), ("A", 3), ("m", 3), ("T", 4), ("E", 5)}),
    "tsx": ("function F() { return <div/>; }\ntype P = {};\n", {("F", 1), ("P", 2)}),
    "c": ("int f(void) { return 0; }\nstruct S { int x; };\n", {("f", 1), ("S", 2)}),
    "cpp": ("class A { void m(); };\nvoid f() {}\n", {("A", 1), ("m", 1), ("f", 2)}),
    "bash": ("f() { echo; }\nfunction g { :; }\n", {("f", 1), ("g", 2)}),
    "markdown": ("# Title\n\ntext\n## Section\n```\n# not a heading\n```\n### Deep ###\n", {("Title", 1), ("Section", 4), ("Deep", 8)}),
}


def found(language_id, text):
    return {(symbol.name, symbol.line) for symbol in symbols_of(text, LANGUAGES_BY_ID[language_id])}


@pytest.mark.parametrize("language_id", sorted(SAMPLES))
def test_definitions_are_found_by_name_and_line(language_id):
    text, expected = SAMPLES[language_id]
    assert found(language_id, text) == expected


def test_every_language_with_a_grammar_and_tags_has_a_sample():
    tagged = {language.id for language in LANGUAGES if language.tags} | {"markdown"}
    assert tagged == set(SAMPLES)


def test_kinds_come_without_the_query_prefix_and_are_sorted_by_position():
    symbols = symbols_of("class A:\n    def m(self): pass\n", LANGUAGES_BY_ID["python"])
    assert symbols == [Symbol("A", "class", 1, 6), Symbol("m", "function", 2, 8)]


def test_a_method_that_is_also_matched_as_a_function_is_listed_once_as_the_method():
    symbols = symbols_of("struct S;\nimpl S { fn m() {} }\n", LANGUAGES_BY_ID["rust"])
    assert [(symbol.name, symbol.kind) for symbol in symbols if symbol.name == "m"] == [("m", "method")]


def test_columns_count_characters_not_bytes():
    (symbol,) = symbols_of("# é\ndef éa(): pass\n", LANGUAGES_BY_ID["python"])
    assert (symbol.name, symbol.line, symbol.column) == ("éa", 2, 4)


def test_headings_have_their_level_as_the_kind():
    symbols = symbols_of("# One\n### Three\n", LANGUAGES_BY_ID["markdown"])
    assert [(symbol.kind, symbol.name) for symbol in symbols] == [("h1", "One"), ("h3", "Three")]


def test_languages_without_tags_and_unknown_files_have_no_symbols():
    assert symbols_of("a = 1\n", LANGUAGES_BY_ID["yaml"]) == []
    assert symbols_of("def f(): pass\n", None) == []


def test_broken_source_still_gives_the_definitions_that_parse():
    assert ("g", 3) in found("python", "def (:\n\ndef g(): pass\n")
