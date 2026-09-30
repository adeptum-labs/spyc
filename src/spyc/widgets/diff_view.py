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
from rich.text import Text
from textual.binding import Binding
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from spyc.core.cells import expand_tabs, widest_cells
from spyc.core.printable import printable
from spyc.git.diff_rows import DiffRow, location_of
from spyc.widgets.line_text import segments_of

MIN_DIGITS = 3
PREFIXES = {"add": "+", "delete": "-", "context": " "}
DARK_STYLES = {
    "add": Style(bgcolor="#1f3d1f"), "delete": Style(bgcolor="#4a2020"), "hunk": Style(color="cyan"),
    "file": Style(bold=True, bgcolor="#2a2a3a"), "note": Style(dim=True, italic=True),
    "info": Style(color="yellow"), "message": Style(), "context": Style(), "blank": Style()}
LIGHT_STYLES = {
    "add": Style(bgcolor="#d6f5d6"), "delete": Style(bgcolor="#f7d4d4"), "hunk": Style(color="dark_cyan"),
    "file": Style(bold=True, bgcolor="#e4e4f0"), "note": Style(dim=True, italic=True),
    "info": Style(color="dark_orange"), "message": Style(), "context": Style(), "blank": Style()}
CURSOR_STYLES = {True: Style(bgcolor="#3a3a3a"), False: Style(bgcolor="#e0e0e0")}


class DiffView(ScrollView, can_focus=True):
    BINDINGS = [
        Binding("up,k", "move(-1)", show=False),
        Binding("down,j", "move(1)", show=False),
        Binding("pageup", "page(-1)", show=False),
        Binding("pagedown,space", "page(1)", show=False),
        Binding("home", "edge(0)", show=False),
        Binding("end", "edge(1)", show=False),
        Binding("n", "file(1)", show=False),
        Binding("N", "file(-1)", show=False),
        Binding("enter", "open", show=False),
    ]
    SCROLL_MARGIN = 3

    class OpenLocation(Message):
        def __init__(self, path: str, line: int) -> None:
            super().__init__()
            self.path, self.line = path, line

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.rows: list[DiffRow] = []
        self.cursor_row = 0
        self._digits = MIN_DIGITS

    def show_rows(self, rows: list[DiffRow]) -> None:
        self.rows, self.cursor_row = rows, 0
        numbers = [number for row in rows for number in (row.old, row.new) if number]
        self._digits = max(MIN_DIGITS, len(str(max(numbers, default=0))))
        text_width = widest_cells(printable(row.text) for row in rows) + 2
        self.virtual_size = Size(text_width + self._gutter_width, max(1, len(rows)))
        self.scroll_to(0, 0, animate=False, immediate=True)
        self.refresh()

    @property
    def _gutter_width(self) -> int:
        return 2 * self._digits + 2

    def render_line(self, y: int) -> Strip:
        row_number = y + self.scroll_offset.y
        width = self.scrollable_content_region.width
        if row_number >= len(self.rows):
            return Strip.blank(width)
        row = self.rows[row_number]
        dark = self.app.current_theme.dark
        style = (DARK_STYLES if dark else LIGHT_STYLES)[row.kind]
        if row_number == self.cursor_row:
            style = style + CURSOR_STYLES[dark] if row.kind not in ("add", "delete") else style + Style(bold=True, underline=True)
        old = "" if row.old is None else str(row.old)
        new = "" if row.new is None or row.kind in ("hunk", "file") else str(row.new)
        gutter = Text(f"{old:>{self._digits}} {new:>{self._digits}} ", style=Style(dim=True))
        expanded, _ = expand_tabs(printable(row.text))
        body = Text(PREFIXES.get(row.kind, "") + expanded, style=style, no_wrap=True, end="")
        console = self.app.console
        left = self.scroll_offset.x
        code = Strip(segments_of(body, console), body.cell_len).crop_extend(left, left + width - self._gutter_width, style)
        return Strip.join([Strip(segments_of(gutter, console), self._gutter_width), code])

    def _move_to(self, row: int) -> None:
        if not self.rows:
            return
        self.cursor_row = min(max(row, 0), len(self.rows) - 1)
        height = self.scrollable_content_region.height
        margin = max(0, min(self.SCROLL_MARGIN, (height - 1) // 2))
        top = self.scroll_offset.y
        if self.cursor_row < top + margin:
            top = max(0, self.cursor_row - margin)
        elif self.cursor_row >= top + height - margin:
            top = self.cursor_row - height + margin + 1
        self.scroll_to(y=top, animate=False, immediate=True)
        self.refresh()

    def action_move(self, rows: int) -> None:
        self._move_to(self.cursor_row + rows)

    def action_page(self, direction: int) -> None:
        self._move_to(self.cursor_row + direction * max(1, self.scrollable_content_region.height - 1))

    def action_edge(self, end: int) -> None:
        self._move_to(len(self.rows) - 1 if end else 0)

    def action_file(self, direction: int) -> None:
        candidates = [index for index, row in enumerate(self.rows) if row.kind == "file"]
        ahead = [index for index in candidates if index > self.cursor_row] if direction > 0 else \
            [index for index in candidates if index < self.cursor_row][::-1]
        if ahead:
            self._move_to(ahead[0])

    def action_open(self) -> None:
        location = location_of(self.rows, self.cursor_row) if self.rows else None
        if location is not None:
            self.post_message(self.OpenLocation(*location))
