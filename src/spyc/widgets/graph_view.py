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
from textual import events
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from spyc.deps.render import FocusLayout
from spyc.line_text import segments_of


# Draws a FocusLayout; the screen owns what is selected.
class GraphView(ScrollView):
    class Clicked(Message):
        def __init__(self, side: str, index: int) -> None:
            super().__init__()
            self.side, self.index = side, index

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.drawing = FocusLayout([], [])

    def show(self, layout: FocusLayout) -> None:
        self.drawing = layout
        self.virtual_size = Size(max((line.cell_len for line in layout.lines), default=1), max(len(layout.lines), 1))
        self.refresh()

    def render_line(self, y: int) -> Strip:
        row = y + self.scroll_offset.y
        width = self.scrollable_content_region.width
        if row >= len(self.drawing.lines):
            return Strip.blank(width)
        text = self.drawing.lines[row]
        left = self.scroll_offset.x
        return Strip(segments_of(text, self.app.console), text.cell_len).crop_extend(left, left + width, Style.null())

    def on_mouse_down(self, event: events.MouseDown) -> None:
        row, cell = event.y + self.scroll_offset.y, event.x + self.scroll_offset.x
        for place in self.drawing.places:
            if place.row == row and place.start <= cell < place.end:
                self.post_message(self.Clicked(place.side, place.index))
                return
