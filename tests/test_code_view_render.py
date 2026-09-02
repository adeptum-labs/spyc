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


async def test_renders_line_numbers_and_text(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"a = 1\nb = 2\n")
        assert view.render_line(0).text.startswith("   1 a = 1")
        assert view.render_line(1).text.startswith("   2 b = 2")


async def test_rows_past_the_end_are_blank(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"only\n")
        assert view.render_line(5).text.strip() == ""


async def test_tabs_are_expanded(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"\tx\n")
        assert view.render_line(0).text.startswith("   1     x")


async def test_a_binary_file_shows_its_notice(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.bin", b"\x00\x01\x02")
        assert "Binary file" in view.render_line(0).text


async def test_highlighting_arrives_after_the_plain_text(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.py", b"x = 1\ndef f(): pass\n")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert any(segment.text == "def" for segment in view.render_line(1))


async def test_long_lines_scroll_sideways_and_keep_the_gutter(tmp_path):
    line = "".join(chr(97 + number % 26) for number in range(5000))
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "min.js", line.encode())
        view.scroll_to(x=30, animate=False)
        await pilot.pause()
        assert view.render_line(0).text[:15] == "   1 " + line[30:40]


async def test_scroll_size_covers_every_line_and_the_widest_one(tmp_path):
    content = ("x" * 20 + "\n") + "\n" * 499
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", content.encode())
        assert view.virtual_size.height == 500
        assert view.virtual_size.width == 20 + 1 + view.gutter_width
