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


from pathlib import Path

import pytest

from spyc.editor import editor_command

FILE = Path("/p/a.py")


@pytest.mark.parametrize("editor, expected", [
    ("vim", ["vim", "+42", "/p/a.py"]),
    ("nvim", ["nvim", "+42", "/p/a.py"]),
    ("nano", ["nano", "+42", "/p/a.py"]),
    ("emacs -nw", ["emacs", "-nw", "+42", "/p/a.py"]),
    ("/usr/bin/vim", ["/usr/bin/vim", "+42", "/p/a.py"]),
    ("hx", ["hx", "/p/a.py:42"]),
    ("micro", ["micro", "/p/a.py:42"]),
    ("subl", ["subl", "/p/a.py:42"]),
    ("code -w", ["code", "-w", "--goto", "/p/a.py:42"]),
    ("kate", ["kate", "-l", "42", "/p/a.py"]),
    ("idea", ["idea", "--line", "42", "/p/a.py"]),
    ("myeditor", ["myeditor", "/p/a.py"]),
    ('"/opt/my editor/vim" -u NONE', ["/opt/my editor/vim", "-u", "NONE", "+42", "/p/a.py"]),
])
def test_the_line_is_passed_the_way_the_editor_takes_it(editor, expected):
    assert editor_command(FILE, 42, {"EDITOR": editor}) == expected


def test_visual_wins_over_editor():
    assert editor_command(FILE, 1, {"VISUAL": "vim", "EDITOR": "nano"})[0] == "vim"


def test_blank_settings_are_ignored():
    assert editor_command(FILE, 1, {"VISUAL": "  ", "EDITOR": "nano"})[0] == "nano"


def test_without_a_setting_the_first_installed_editor_is_used():
    installed = {"vim": "/usr/bin/vim", "vi": "/usr/bin/vi"}
    assert editor_command(FILE, 3, {}, which=installed.get) == ["vim", "+3", "/p/a.py"]


def test_no_editor_at_all_gives_none():
    assert editor_command(FILE, 3, {}, which=lambda name: None) is None


def test_an_unparsable_setting_gives_none():
    assert editor_command(FILE, 3, {"EDITOR": "vim 'unclosed"}) is None


def test_lines_below_one_become_one():
    assert editor_command(FILE, 0, {"EDITOR": "vim"}) == ["vim", "+1", "/p/a.py"]
