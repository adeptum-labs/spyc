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

from spyc.widgets.code_view import CodeView


async def test_down_up_and_the_vi_keys_move_one_line(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a\nb\nc\n")
        await pilot.press("down", "j")
        assert view.cursor_row == 2
        await pilot.press("up", "k", "k")
        assert view.cursor_row == 0


async def test_the_cursor_stops_at_the_first_and_last_line(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a\nb\n")
        await pilot.press("up", "up")
        assert view.cursor_row == 0
        await pilot.press("down", "down", "down")
        assert view.cursor_row == 1


async def test_left_right_home_and_end_stay_on_the_line(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"abc\nd\n")
        await pilot.press("left")
        assert view.cursor_column == 0
        await pilot.press("end")
        assert view.cursor_column == 3
        await pilot.press("right")
        assert (view.cursor_row, view.cursor_column) == (0, 3)
        await pilot.press("home")
        assert view.cursor_column == 0


async def test_vertical_moves_remember_the_wanted_column(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"abcdef\nab\nabcdef\n")
        await pilot.press("right", "right", "right", "right", "down")
        assert (view.cursor_row, view.cursor_column) == (1, 2)
        await pilot.press("down")
        assert (view.cursor_row, view.cursor_column) == (2, 4)


async def test_paging_and_file_edges(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"x\n" * 100)
        height = view.scrollable_content_region.height
        await pilot.press("pagedown")
        assert view.cursor_row == height - 1
        await pilot.press("ctrl+end")
        assert view.cursor_row == 99
        await pilot.press("ctrl+home")
        assert view.cursor_row == 0


async def test_the_cursor_is_kept_on_screen_while_moving_down(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"x\n" * 100)
        await pilot.press(*["down"] * 40)
        top, height = view.scroll_offset.y, view.scrollable_content_region.height
        assert top <= view.cursor_row < top + height


async def test_goto_centres_a_line_that_is_off_screen(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"x\n" * 200)
        view.goto(150, 0)
        await pilot.pause()
        top, height = view.scroll_offset.y, view.scrollable_content_region.height
        assert view.cursor_row == 149 and top <= 149 < top + height


async def test_goto_clamps_out_of_range_positions(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"abc\ndef\n")
        view.goto(99, 99)
        assert (view.cursor_row, view.cursor_column) == (1, 3)
        view.goto(0, 0)
        assert (view.cursor_row, view.cursor_column) == (0, 0)


async def test_clicking_puts_the_cursor_on_the_character_under_it(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", "日本x\n\tz\n".encode())
        gutter = view.gutter_width
        await pilot.click(CodeView, offset=(gutter + 2, 0))
        assert view.cursor_column == 1
        await pilot.click(CodeView, offset=(gutter + 30, 0))
        assert view.cursor_column == 3
        await pilot.click(CodeView, offset=(gutter + 2, 1))
        assert (view.cursor_row, view.cursor_column) == (1, 0)
        await pilot.click(CodeView, offset=(gutter + 4, 1))
        assert view.cursor_column == 1
        await pilot.click(CodeView, offset=(1, 0))
        assert (view.cursor_row, view.cursor_column) == (0, 0)


async def test_clicking_below_the_text_changes_nothing(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a\nb\n")
        await pilot.click(CodeView, offset=(10, 10))
        assert view.cursor_row == 0


async def test_every_cursor_change_is_announced(tmp_path):
    app = ViewApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await open_file(pilot, tmp_path, "a.txt", b"a\nb\n")
        assert app.moves[-1] == (0, 0)
        await pilot.press("down")
        await pilot.pause()
        assert app.moves[-1] == (1, 0)


async def test_the_word_under_the_cursor_is_found_where_it_is_touched(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", "foo_bar = baz.qux(1)\néa = 2\n".encode())
        assert view.word_at_cursor() == "foo_bar"
        view.goto(1, 7)
        assert view.word_at_cursor() == "foo_bar"
        view.goto(1, 8)
        assert view.word_at_cursor() is None
        view.goto(1, 13)
        assert view.word_at_cursor() == "baz"
        view.goto(2, 1)
        assert view.word_at_cursor() == "éa"


async def test_there_is_no_word_in_an_empty_view():
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        assert pilot.app.query_one(CodeView).word_at_cursor() is None
