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


from views import ViewApp, open_file

from spyc.widgets.code_theme import code_theme


async def test_search_counts_matches_and_jumps_to_the_first_one(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"x\nfoo bar\nFoo\nfoo\n")
        assert view.search("foo") == 3
        assert (view.cursor_row, view.cursor_column) == (1, 0)
        assert view.match_status == "1/3"


async def test_n_and_shift_n_walk_the_matches_and_wrap(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"foo\nfoo\nfoo\n")
        view.search("foo")
        await pilot.press("n")
        assert view.cursor_row == 1
        await pilot.press("n", "n")
        assert view.cursor_row == 0 and view.match_status == "1/3"
        await pilot.press("N")
        assert view.cursor_row == 2


async def test_search_starts_at_the_cursor(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"foo\nbar\nfoo\n")
        await pilot.press("down")
        view.search("foo")
        assert view.cursor_row == 2


async def test_no_match_leaves_the_cursor_alone(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"abc\n")
        assert view.search("zzz") == 0
        assert view.match_status == "" and view.cursor_row == 0


async def test_clearing_the_search_removes_the_highlight(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"foo bar\n")
        marked = code_theme(True).current_match.bgcolor
        view.search("bar")
        assert any(segment.style and segment.style.bgcolor == marked for segment in view.render_line(0))
        view.clear_search()
        assert not any(segment.style and segment.style.bgcolor == marked for segment in view.render_line(0))
        assert view.match_status == ""
