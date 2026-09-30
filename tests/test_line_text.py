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


from rich.style import Style

from spyc.syntax.spans import Span
from spyc.syntax.theme import CodeTheme, SyntaxTheme
from spyc.widgets.line_text import build_line

THEME = CodeTheme(
    syntax=SyntaxTheme({"number": Style(color="red")}), base=Style(color="white"),
    cursor_line=Style(bgcolor="blue"), cursor=Style(reverse=True), match=Style(bgcolor="yellow"),
    current_match=Style(bgcolor="orange1"), gutter=Style(dim=True), gutter_cursor=Style(bold=True))


def styles(text):
    return [(span.start, span.end, span.style) for span in text.spans]


def test_tabs_are_expanded_and_spans_follow_the_characters():
    text = build_line("\tx = 1", [Span(5, 6, "number")], THEME)
    assert text.plain == "    x = 1"
    assert styles(text) == [(8, 9, Style(color="red"))]


def test_captures_without_a_style_are_skipped():
    assert build_line("x", [Span(0, 1, "spell")], THEME).spans == []


def test_base_style_depends_on_the_cursor_row():
    assert build_line("x", [], THEME).style == THEME.base
    assert build_line("x", [], THEME, is_cursor_row=True).style == THEME.cursor_line


def test_cursor_marks_one_character():
    assert styles(build_line("abc", [], THEME, cursor_column=1)) == [(1, 2, THEME.cursor)]


def test_cursor_past_the_end_is_a_visible_cell():
    text = build_line("abc", [], THEME, cursor_column=3)
    assert text.plain == "abc " and styles(text) == [(3, 4, THEME.cursor)]


def test_cursor_on_a_wide_character_uses_character_indices():
    assert styles(build_line("日x", [], THEME, cursor_column=1)) == [(1, 2, THEME.cursor)]


def test_current_match_differs_from_other_matches():
    text = build_line("aa aa", [], THEME, matches=[(0, 2), (3, 5)], current_match=(3, 5))
    assert styles(text) == [(0, 2, THEME.match), (3, 5, THEME.current_match)]


def test_spans_reaching_past_the_end_of_the_line_are_clipped():
    text = build_line("ab", [Span(1, 9, "number"), Span(5, 6, "number")], THEME)
    assert styles(text) == [(1, 2, Style(color="red"))]
