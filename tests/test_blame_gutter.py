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


from spyc.git.blame import NOT_COMMITTED, BlameLine
from spyc.gutters import BlameGutter
from spyc.widgets.code_theme import code_theme
from spyc.widgets.code_view import CodeView
from views import ViewApp, open_file

A, B = "a" * 40, "b" * 40
NOW = 1_700_100_000
THEME = code_theme(True)
BLAME = [
    BlameLine(1, A, "Ada Lovelace", 1_700_000_000, "First"),
    BlameLine(2, A, "Ada Lovelace", 1_700_000_000, "First"),
    BlameLine(3, B, "Bob", 1_600_000_000, "Old"),
    BlameLine(4, NOT_COMMITTED, "Not Committed Yet", NOW - 5, "Edit")]
FIRST_ROW = f"aaaaaaa {'Ada Love':<8} {'1d':>4} "


def test_a_commit_is_named_once_for_a_run_of_its_lines():
    gutter = BlameGutter(BLAME, NOW)
    assert gutter.width == 22
    assert [gutter.render(row, False, THEME).plain for row in range(4)] == [
        FIRST_ROW, " " * 22, f"bbbbbbb {'Bob':<8} {'3y':>4} ", "(uncommitted)".ljust(22)]


def test_recent_and_old_changes_have_different_colors_and_unknown_rows_are_blank():
    gutter = BlameGutter(BLAME, NOW)
    assert gutter.render(0, False, THEME).style != gutter.render(2, False, THEME).style
    assert gutter.render(9, False, THEME).plain == " " * 22


async def test_the_code_view_shows_the_blame_column_left_of_the_line_numbers(tmp_path):
    async with ViewApp().run_test(size=(100, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"one\ntwo\nthree\nfour\n")
        view.set_blame(BLAME, NOW)
        assert view.render_line(0).text.startswith(FIRST_ROW + "   1 one")
        view.set_blame(None)
        assert view.render_line(0).text.startswith("   1 one")


async def test_enter_names_the_commit_of_the_line_and_uncommitted_lines_name_none(tmp_path):
    hashes = []

    class BlameApp(ViewApp):
        def on_code_view_open_commit(self, message):
            hashes.append(message.hash)

    async with BlameApp().run_test(size=(100, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"one\ntwo\nthree\nfour\n")
        await pilot.press("enter")
        assert hashes == []
        view.set_blame(BLAME, NOW)
        await pilot.press("enter", "down", "down", "enter", "down", "enter")
        await pilot.pause()
        assert hashes == [A, B, None]


async def test_the_blame_column_stays_when_another_file_is_shown(tmp_path):
    from spyc.document import load_document
    async with ViewApp().run_test(size=(100, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"one\n")
        view.set_blame(BLAME, NOW)
        (tmp_path / "b.txt").write_text("two\n")
        view.show(load_document(tmp_path / "b.txt"))
        assert view.render_line(0).text.startswith(" " * 22 + "   1 two")


def test_every_row_is_exactly_as_wide_as_the_column_whatever_the_name_and_the_age():
    from rich.cells import cell_len
    lines = [BlameLine(1, A, "张三丰", NOW - 340 * 86400, "S"), BlameLine(2, B, "Émile Zola-Longname", NOW - 364 * 86400, "S")]
    gutter = BlameGutter(lines, NOW)
    rendered = [gutter.render(row, False, THEME).plain for row in range(2)]
    assert [cell_len(text) for text in rendered] == [22, 22]
    assert "11mo" in rendered[0] and "12mo" in rendered[1]
