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


from textual.app import App

from spyc.git.diff import Diff, DiffLine, FileDiff
from spyc.git.diff_rows import DiffRow, rows_of
from spyc.widgets.diff_view import DiffView

FIRST = FileDiff("a.txt", "a.txt", "modified", [
    DiffLine("hunk", "@@ -1,3 +1,3 @@", None, 1),
    DiffLine("context", "one", 1, 1),
    DiffLine("delete", "two", 2, None),
    DiffLine("add", "TWO", None, 2),
    DiffLine("context", "three", 3, 3)], additions=1, deletions=1)
SECOND = FileDiff("b.txt", "b.txt", "added", [
    DiffLine("hunk", "@@ -0,0 +1 @@", None, 1), DiffLine("add", "\x1b[2Jnew", None, 1)], additions=1)
ROWS = rows_of("Subject\n\nBody", Diff([FIRST, SECOND]))
# message 0-3, file 4, hunk 5, context 6, delete 7, add 8, context 9, blank 10, file 11


class DiffApp(App):
    def __init__(self, rows=ROWS):
        super().__init__()
        self.rows, self.opened = rows, []

    def compose(self):
        yield DiffView()

    def on_mount(self):
        self.query_one(DiffView).show_rows(self.rows)

    def on_diff_view_open_location(self, message):
        self.opened.append((message.path, message.line))


async def test_rows_have_old_and_new_line_numbers_and_a_prefix():
    async with DiffApp().run_test(size=(80, 24)) as pilot:
        view = pilot.app.query_one(DiffView)
        assert view.render_line(6).text.startswith("  1   1  one")
        assert view.render_line(7).text.startswith("  2     -two")
        assert view.render_line(8).text.startswith("      2 +TWO")
        assert view.render_line(5).text.startswith("        @@ -1,3 +1,3 @@")
        assert view.render_line(0).text.startswith("        Subject")
        assert view.render_line(4).text.startswith("        modified a.txt  +1 -1")


async def test_added_and_deleted_lines_have_their_own_backgrounds():
    async with DiffApp().run_test(size=(80, 24)) as pilot:
        view = pilot.app.query_one(DiffView)

        def background(row, word):
            return next(segment.style.bgcolor if segment.style else None
                        for segment in view.render_line(row) if word in segment.text)

        assert len({background(6, "one"), background(7, "two"), background(8, "TWO")}) == 3


async def test_control_characters_in_the_diff_are_never_written_out():
    async with DiffApp().run_test(size=(80, 24)) as pilot:
        text = pilot.app.query_one(DiffView).render_line(13).text
        assert "\x1b" not in text and "new" in text


async def test_the_cursor_moves_by_line_page_and_file():
    async with DiffApp().run_test(size=(80, 12)) as pilot:
        view = pilot.app.query_one(DiffView)
        await pilot.press("down", "j", "down")
        assert view.cursor_row == 3
        await pilot.press("up", "k")
        assert view.cursor_row == 1
        await pilot.press("n")
        assert view.cursor_row == 4
        await pilot.press("n")
        assert view.cursor_row == 11
        await pilot.press("n")
        assert view.cursor_row == 11
        await pilot.press("N")
        assert view.cursor_row == 4
        await pilot.press("end")
        assert view.cursor_row == len(ROWS) - 1
        await pilot.press("home")
        assert view.cursor_row == 0
        await pilot.press("pagedown")
        top, height = view.scroll_offset.y, view.scrollable_content_region.height
        assert top <= view.cursor_row < top + height


async def test_enter_opens_the_line_under_the_cursor():
    app = DiffApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press(*["down"] * 8, "enter")
        await pilot.press("home", "enter")
    assert app.opened == [("a.txt", 2)]


async def test_a_view_without_rows_is_quiet():
    async with DiffApp([]).run_test(size=(80, 24)) as pilot:
        await pilot.press("down", "enter", "n", "end")
        assert pilot.app.query_one(DiffView).cursor_row == 0
