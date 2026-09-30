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


from spyc.widgets.code_theme import code_theme
from spyc.widgets.gutters import LineNumberGutter


def test_line_number_gutter_grows_with_the_line_count():
    assert LineNumberGutter(5).width == 5
    assert LineNumberGutter(12345).width == 7


def test_line_numbers_are_right_aligned_and_one_based():
    assert LineNumberGutter(5).render(0, False, code_theme(True)).plain == "   1 "
    assert LineNumberGutter(100).render(41, False, code_theme(True)).plain == "  42 "
