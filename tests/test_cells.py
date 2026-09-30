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

import spyc.core.cells
from spyc.core.cells import cell_of_char, char_at_cell, expand_tabs, fit_cells, line_cells, widest_cells


def test_ascii_columns_are_cells():
    assert cell_of_char("abc", 2) == 2
    assert char_at_cell("abc", 2) == 2


def test_tabs_expand_to_the_next_stop():
    assert cell_of_char("\tx", 1) == 4
    assert cell_of_char("a\tb", 2) == 4
    assert char_at_cell("\tx", 2) == 0
    assert char_at_cell("\tx", 4) == 1


def test_wide_characters_take_two_cells():
    assert cell_of_char("日本x", 2) == 4
    assert char_at_cell("日本x", 3) == 1
    assert line_cells("😀a") == 3


def test_positions_past_the_end():
    assert cell_of_char("ab", 2) == 2
    assert char_at_cell("ab", 10) == 2


def test_expand_tabs_maps_every_character_to_its_start():
    assert expand_tabs("a\tb") == ("a   b", [0, 1, 4, 5])


def test_expand_tabs_is_the_identity_without_tabs():
    text, starts = expand_tabs("日本")
    assert text == "日本" and list(starts) == [0, 1, 2]


def test_tab_stops_follow_wide_characters():
    assert expand_tabs("日\tx")[0] == "日  x"


def test_the_widest_line_is_measured_in_cells_not_characters():
    assert widest_cells(["a" * 50, "\t" * 5 + "b" * 40]) == 60
    assert widest_cells(["a" * 30, "日" * 20]) == 40
    assert widest_cells([]) == 0


@pytest.mark.parametrize("line", [
    "".join("é\t日x" [index % 4] for index in range(300)),
    "x" * 100 + "日" * 100 + "\t" * 20 + "y" * 100,
])
def test_long_lines_agree_with_the_plain_walk(line, monkeypatch):
    expected = [cell_of_char(line, column) for column in range(len(line) + 3)]
    expected_chars = [char_at_cell(line, cell) for cell in range(expected[-1] + 3)]
    monkeypatch.setattr(spyc.core.cells, "CHECKPOINT", 8)
    spyc.core.cells._checkpoints.cache_clear()
    assert [cell_of_char(line, column) for column in range(len(line) + 3)] == expected
    assert [char_at_cell(line, cell) for cell in range(expected[-1] + 3)] == expected_chars


def test_positions_deep_in_a_huge_non_ascii_line_are_found_quickly():
    line = "x" * 600_000 + "é" + "y" * 600_000
    line_cells(line)
    started = time.perf_counter()
    for _ in range(200):
        cell_of_char(line, 1_100_000)
        char_at_cell(line, 1_100_000)
    assert time.perf_counter() - started < 1.0


@pytest.mark.parametrize("text, width, expected", [
    ("abc", 5, "abc  "), ("abcdef", 4, "abcd"), ("张三丰", 8, "张三丰  "), ("张三丰", 5, "张三 "), ("", 3, "   ")])
def test_text_is_fitted_to_an_exact_number_of_cells(text, width, expected):
    from rich.cells import cell_len
    assert fit_cells(text, width) == expected and cell_len(expected) == width
