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


from spyc.cells import cell_of_char, char_at_cell, expand_tabs, line_cells


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
