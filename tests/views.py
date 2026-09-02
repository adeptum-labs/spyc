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

from spyc.document import load_document
from spyc.widgets.code_view import CodeView


class ViewApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.moves: list[tuple[int, int]] = []

    def compose(self):
        yield CodeView()

    def on_code_view_cursor_moved(self, message) -> None:
        self.moves.append((message.row, message.column))


async def open_file(pilot, tmp_path, name, content: bytes):
    path = tmp_path / name
    path.write_bytes(content)
    view = pilot.app.query_one(CodeView)
    view.focus()
    view.show(load_document(path))
    await pilot.pause()
    return view
