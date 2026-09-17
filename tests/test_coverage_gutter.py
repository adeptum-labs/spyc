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

from spyc.coverage.model import CoverageLine
from spyc.document import load_document
from spyc.gutters import CoverageGutter
from spyc.widgets.code_theme import code_theme
from views import ViewApp, open_file

THEME = code_theme(True)
LINES = {1: CoverageLine(3), 2: CoverageLine(0), 3: CoverageLine(1, partial=True)}


def test_each_state_of_a_line_has_its_own_mark_and_color_and_other_lines_have_none():
    gutter = CoverageGutter(LINES)
    rendered = [gutter.render(row, False, THEME) for row in range(4)]
    assert [text.plain for text in rendered] == ["● ", "○ ", "◐ ", "  "]
    assert [text.style for text in rendered[:3]] == [Style(color="green"), Style(color="red"), Style(color="yellow")]


def test_the_column_is_two_cells_wide():
    assert CoverageGutter({}).width == 2


async def test_the_code_view_shows_the_column_after_the_change_marks_once_it_has_coverage(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a = 1\nb = 2\nc = 3\n")
        before = view.virtual_size.width
        view.set_coverage(LINES)
        assert view.render_line(0).text.startswith("   1 ● a = 1")
        assert view.render_line(1).text.startswith("   2 ○ b = 2")
        assert view.virtual_size.width == before + 2
        view.set_coverage(None)
        assert view.render_line(0).text.startswith("   1 a = 1")


async def test_the_column_stays_empty_but_present_when_another_file_is_shown(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a\n")
        view.set_coverage(LINES)
        (tmp_path / "b.txt").write_text("b\n")
        view.show(load_document(tmp_path / "b.txt"))
        assert view.render_line(0).text.startswith("   1   b")
        assert view.coverage == {}
