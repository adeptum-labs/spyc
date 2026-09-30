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


import time

import pytest

from spyc.core.languages import LANGUAGES, LANGUAGES_BY_ID
from spyc.symbols import Symbol, enclosing_definition, symbols_of

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


def headings(text):
    return [(symbol.name, symbol.kind, symbol.line, symbol.column) for symbol in symbols_of(text, LANGUAGES_BY_ID["markdown"])]


def test_a_longer_fence_is_closed_only_by_a_fence_at_least_as_long_and_of_its_own_kind():
    text = "````\n```\n# inside\n```\n~~~~\n# still inside\n````\n# Out\n"
    assert headings(text) == [("Out", "h1", 8, 2)]


def test_a_fence_holding_a_heading_like_line_is_not_closed_by_a_fence_with_text_after_it():
    assert headings("```\n```python\n# inside\n```\n# Out\n") == [("Out", "h1", 5, 2)]


def test_a_heading_may_be_indented_by_up_to_three_spaces():
    assert headings("   # Three\n    # Four\n") == [("Three", "h1", 1, 5)]


def test_an_empty_heading_and_a_hashtag_are_not_outline_entries():
    assert headings("#\n# \n## ##\n#hashtag\n") == []


def test_the_closing_hashes_of_a_heading_are_not_part_of_its_title():
    assert headings("## Title ##  \n# C#\n# a #b\n") == [("Title", "h2", 1, 3), ("C#", "h1", 2, 2), ("a #b", "h1", 3, 2)]


def test_a_heading_line_of_many_blanks_is_read_in_linear_time():
    started = time.perf_counter()
    headings("# a" + " " * 20_000 + "x\n")
    assert time.perf_counter() - started < 1


def test_a_very_long_line_with_many_definitions_is_read_quickly():
    text = "".join(f"function f{index}(){{}}" for index in range(60_000))
    started = time.perf_counter()
    assert len(symbols_of(text, LANGUAGES_BY_ID["javascript"])) == 60_000
    assert time.perf_counter() - started < 3


def enclosing(language_id, text, line):
    symbol = enclosing_definition(text, LANGUAGES_BY_ID[language_id], line)
    return None if symbol is None else (symbol.name, symbol.line)


def test_the_innermost_class_around_a_line_is_the_enclosing_definition():
    text = "class Outer:\n    class Inner:\n        def m(self):\n            pass\n\n    def n(self): pass\n"
    assert enclosing("python", text, 4) == ("Inner", 2)
    assert enclosing("python", text, 6) == ("Outer", 1)


def test_a_line_of_the_class_header_is_inside_the_class():
    assert enclosing("java", "class A {\n  class B {}\n}\n", 1) == ("A", 1)


def test_a_java_inner_class_is_found_before_its_outer_class():
    assert enclosing("java", "class A {\n  class B {\n    void m() {}\n  }\n}\n", 3) == ("B", 2)


def test_a_line_outside_every_class_has_no_enclosing_definition():
    assert enclosing("python", "def f():\n    pass\n\nclass A:\n    pass\n", 2) is None
    assert enclosing("python", "class A:\n    pass\n\nx = 1\n", 4) is None


def test_functions_and_headings_are_not_enclosing_definitions():
    assert enclosing("python", "def f():\n    return 1\n", 2) is None
    assert enclosing("markdown", "# Title\n\ntext\n", 3) is None


def test_a_language_without_tags_has_no_enclosing_definition():
    assert enclosing_definition("x", None, 1) is None


def test_the_enclosing_definition_names_its_column_in_characters():
    assert enclosing_definition("class Å:\n    pass\n", LANGUAGES_BY_ID["python"], 2) == Symbol("Å", "class", 1, 6)
