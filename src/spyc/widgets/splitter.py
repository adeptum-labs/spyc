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


from textual.events import MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.widget import Widget


class Splitter(Widget):
    DEFAULT_CSS = "Splitter { width: 1; background: $primary; } Splitter:hover { background: $accent; }"

    class Moved(Message):
        def __init__(self, x: int) -> None:
            super().__init__()
            self.x = x

    def on_mouse_down(self, event: MouseDown) -> None:
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if self.app.mouse_captured is self:
            self.post_message(self.Moved(event.screen_x))

    def on_mouse_up(self, event: MouseUp) -> None:
        self.release_mouse()
