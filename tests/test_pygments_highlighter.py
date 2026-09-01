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


from spyc.syntax.pygments_highlighter import PygmentsHighlighter
from spyc.syntax.spans import PlainHighlighter


def base(spans):
    return [(span.start, span.end, span.capture.split(".")[0]) for span in spans]


def test_tokens_become_spans_with_character_columns():
    highlighter = PygmentsHighlighter("x = 'ä'  # c\n", "python")
    assert base(highlighter.spans(0, 1)[0]) == [(2, 3, "operator"), (4, 7, "string"), (9, 12, "comment")]


def test_multi_line_tokens_are_split_per_line():
    highlighter = PygmentsHighlighter('s = """a\nbb"""\n', "python")
    lines = highlighter.spans(0, 2)
    assert base(lines[0])[-1] == (4, 8, "string")
    assert base(lines[1]) == [(0, 5, "string")]


def test_lines_past_the_end_are_empty_and_blank_lines_are_kept():
    highlighter = PygmentsHighlighter("\n\nx = 1\n", "python")
    lines = highlighter.spans(0, 6)
    assert lines[0] == [] and lines[1] == [] and lines[5] == []
    assert base(lines[2])[-1] == (4, 5, "number")


def test_unknown_lexer_yields_no_spans():
    assert PygmentsHighlighter("a b", "no-such-lexer").spans(0, 1) == [[]]


def test_plain_highlighter_has_no_spans():
    assert PlainHighlighter().spans(3, 5) == [[], []]
