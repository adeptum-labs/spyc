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


from spyc.languages import LANGUAGES_BY_ID
from spyc.syntax.grammars import load_grammar
from spyc.syntax.tree_sitter_highlighter import TreeSitterHighlighter

PYTHON, PYTHON_QUERY = load_grammar(LANGUAGES_BY_ID["python"])


def highlight(text, query=PYTHON_QUERY):
    lines = text.count("\n") + 1
    return [[(span.start, span.end, span.capture) for span in line]
            for line in TreeSitterHighlighter(text, PYTHON, query).spans(0, lines)]


def test_first_pattern_wins_for_the_same_node():
    assert highlight("x = 1\n", "(integer) @first\n(integer) @second\n")[0] == [(4, 5, "first")]


def test_inner_node_wins_over_the_node_around_it():
    assert highlight("x = 1\n", "(assignment) @outer\n(integer) @inner\n")[0] == [(0, 4, "outer"), (4, 5, "inner")]


def test_columns_count_characters_not_bytes():
    assert [span for span in highlight("s = 'é' + 1\n")[0] if span[2] == "number"] == [(10, 11, "number")]


def test_multi_line_nodes_are_clipped_to_each_line():
    lines = highlight("s = '''a\nbb'''\n", "(string) @string\n")
    assert lines[0] == [(4, 8, "string")]
    assert lines[1] == [(0, 5, "string")]


def test_match_predicates_are_honoured():
    query = '((identifier) @constant (#match? @constant "^[A-Z]+$"))\n'
    assert highlight("MAX = 1\nmax = 2\n", query)[:2] == [[(0, 3, "constant")], []]


def test_helper_captures_and_lines_past_the_end_yield_nothing():
    highlighter = TreeSitterHighlighter("x = 1\n", PYTHON, "(integer) @_helper\n")
    assert highlighter.spans(0, 200) == [[] for _ in range(200)]


def test_ranges_across_block_boundaries_match_a_single_pass():
    text = "".join(f"value_{number} = {number}\n" for number in range(300))
    whole = TreeSitterHighlighter(text, PYTHON, PYTHON_QUERY).spans(0, 300)
    fresh = TreeSitterHighlighter(text, PYTHON, PYTHON_QUERY)
    assert fresh.spans(130, 135) == whole[130:135]
    assert fresh.spans(62, 66) == whole[62:66]
    assert fresh.spans(127, 129) == whole[127:129]


def test_broken_source_still_highlights_what_parses():
    lines = highlight("def (:\nx = 1\n")
    assert any(capture.startswith("number") for _, _, capture in lines[1])
