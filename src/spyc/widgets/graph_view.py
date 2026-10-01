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
from textual import events
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from spyc.deps.layout import Box
from spyc.widgets.line_text import segments_of


# Draws the lines of a diagram; the screen owns what is selected. It does not take the focus, because a focused
# ScrollView would use the arrow keys to scroll instead of the screen's.
class GraphView(ScrollView, can_focus=False):
    class Clicked(Message):
        def __init__(self, node) -> None:
            super().__init__()
            self.node = node

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.lines: list[Text] = []
        self.boxes: list[Box] = []

    def show(self, lines: list[Text], boxes: list[Box]) -> None:
        self.lines, self.boxes = lines, boxes
        self.virtual_size = Size(max((line.cell_len for line in lines), default=1), max(len(lines), 1))
        self.refresh()

    # Scrolls the least that shows the whole box, as the selection moves through more boxes than the view holds.
    def reveal(self, box: Box) -> None:
        region = self.scrollable_content_region
        if region.width <= 0 or region.height <= 0:
            return
        left, top = self.scroll_offset
        x = min(max(left, box.x + box.width - region.width), box.x)
        y = min(max(top, box.y + box.height - region.height), box.y)
        if (x, y) != (left, top):
            self.scroll_to(x=x, y=y, animate=False, immediate=True)

    def render_line(self, y: int) -> Strip:
        row = y + self.scroll_offset.y
        width = self.scrollable_content_region.width
        if row >= len(self.lines):
            return Strip.blank(width)
        text = self.lines[row]
        left = self.scroll_offset.x
        return Strip(segments_of(text, self.app.console), text.cell_len).crop_extend(left, left + width, Style.null())

    def on_mouse_down(self, event: events.MouseDown) -> None:
        row, cell = event.y + self.scroll_offset.y, event.x + self.scroll_offset.x
        for box in self.boxes:
            if box.y <= row < box.y + box.height and box.x <= cell < box.x + box.width:
                self.post_message(self.Clicked(box.node))
                return
