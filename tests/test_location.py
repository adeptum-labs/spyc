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

from spyc.core.location import Location, parse_location, split_line_suffix


@pytest.mark.parametrize("text, expected", [
    ("app.py:40", ("app.py", 40)), ("app.py", ("app.py", None)), ("app.py:", ("app.py", None)),
    ("dir/x.py:7:3", ("dir/x.py", 7)), ("a:b", ("a:b", None)), ("", ("", None)),
])
def test_a_line_suffix_is_split_off(text, expected):
    assert split_line_suffix(text) == expected


def test_an_existing_path_is_taken_literally():
    assert parse_location("weird:3", exists=lambda path: path == "weird:3") == Location("weird:3", None)


def test_a_missing_path_with_a_suffix_gives_path_and_line():
    assert parse_location("a.py:3", exists=lambda path: False) == Location("a.py", 3)
