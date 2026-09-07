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


from spyc.document import load_document
from views import ViewApp, open_file


async def test_replacing_keeps_the_cursor_and_the_scroll_position(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"x\n" * 200)
        view.goto(150)
        await pilot.pause()
        top = view.scroll_offset.y
        (tmp_path / "a.txt").write_bytes(b"x\n" * 201)
        view.replace(load_document(tmp_path / "a.txt"))
        await pilot.pause()
        assert view.cursor_row == 149 and view.scroll_offset.y == top
        assert len(view.document.lines) == 201


async def test_replacing_with_a_shorter_file_clamps_the_cursor(tmp_path):
    async with ViewApp().run_test(size=(80, 24)) as pilot:
        view = await open_file(pilot, tmp_path, "a.txt", b"x\n" * 200)
        view.goto(150)
        await pilot.pause()
        (tmp_path / "a.txt").write_bytes(b"x\n" * 10)
        view.replace(load_document(tmp_path / "a.txt"))
        await pilot.pause()
        assert view.cursor_row == 9
