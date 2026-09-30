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


from spyc.core.status import status_line


def test_position_is_one_based():
    assert status_line("src/a.py", "Python", 42, 8, 120) == "src/a.py · Python · 43:9 of 120"


def test_a_file_without_a_language_is_plain_text():
    assert status_line("notes", None, 0, 0, 3) == "notes · Plain text · 1:1 of 3"


def test_extra_text_is_appended():
    assert status_line("a.py", "Python", 0, 0, 1, "2/17").endswith(" · 2/17")


def test_no_file_no_status():
    assert status_line(None, None, 0, 0, 0) == ""
