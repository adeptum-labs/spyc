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

from spyc.syntax.theme import SyntaxTheme

BLUE, RED = Style(color="blue"), Style(color="red")


def test_exact_capture_wins_over_its_parent():
    theme = SyntaxTheme({"function": BLUE, "function.method": RED})
    assert theme.style_for("function.method") == RED


def test_capture_falls_back_to_the_nearest_dotted_parent():
    assert SyntaxTheme({"function": BLUE}).style_for("function.method.call") == BLUE


def test_editor_style_names_are_translated():
    assert SyntaxTheme({"keyword": BLUE}).style_for("conditional") == BLUE
    assert SyntaxTheme({"variable.parameter": RED}).style_for("parameter") == RED


def test_unknown_capture_has_no_style():
    assert SyntaxTheme({"keyword": BLUE}).style_for("spell") is None
