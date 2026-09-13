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

from spyc.git.changes import LineChanges
from spyc.gutters import ChangeGutter
from spyc.widgets.code_theme import code_theme
from views import ViewApp, open_file

THEME = code_theme(True)


def test_each_kind_of_change_has_its_own_mark_and_color():
    gutter = ChangeGutter(LineChanges(added=frozenset({1}), modified=frozenset({2}), deleted=frozenset({3})))
    rendered = [gutter.render(row, False, THEME) for row in range(4)]
    assert [text.plain for text in rendered] == ["▎ ", "▎ ", "▔ ", "  "]
    assert [text.style for text in rendered[:3]] == [Style(color="green"), Style(color="yellow"), Style(color="red")]


def test_the_column_is_two_cells_wide():
    assert ChangeGutter(LineChanges()).width == 2


async def test_the_code_view_shows_the_column_only_once_it_has_changes(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a = 1\nb = 2\n")
        before = view.virtual_size.width
        assert view.render_line(0).text.startswith("   1 a = 1")
        view.set_changes(LineChanges(added=frozenset({2})))
        assert view.render_line(0).text.startswith("   1   a = 1")
        assert view.render_line(1).text.startswith("   2 ▎ b = 2")
        assert view.virtual_size.width == before + 2
        view.set_changes(None)
        assert view.render_line(1).text.startswith("   2 b = 2")


async def test_the_column_stays_when_another_file_is_shown(tmp_path):
    from spyc.document import load_document
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a\n")
        view.set_changes(LineChanges(added=frozenset({1})))
        (tmp_path / "b.txt").write_text("b\n")
        view.show(load_document(tmp_path / "b.txt"))
        assert view.render_line(0).text.startswith("   1   b")


async def test_a_deletion_at_the_end_of_the_file_is_marked_on_its_last_line(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a\nb\n")
        view.set_changes(LineChanges(deleted=frozenset({3})))
        assert view.render_line(1).text.startswith("   2 ▔ b")
