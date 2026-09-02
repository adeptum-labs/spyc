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


import logging

from rich.text import Text
from textual import work
from textual.cache import LRUCache
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.strip import Strip

from spyc.cells import line_cells
from spyc.document import Document
from spyc.gutters import Gutter, LineNumberGutter
from spyc.line_text import build_line
from spyc.syntax.factory import make_highlighter
from spyc.syntax.spans import Highlighter, PlainHighlighter
from spyc.widgets.code_theme import code_theme

log = logging.getLogger(__name__)
CACHED_ROWS = 512


class CodeView(ScrollView, can_focus=True):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.document: Document | None = None
        self.display_path = ""
        self.cursor_row = 0
        self.cursor_column = 0
        self._highlighter: Highlighter = PlainHighlighter()
        self._theme = code_theme(dark=True)
        self._gutters: list[Gutter] = []
        self._strips: LRUCache[tuple, Strip] = LRUCache(CACHED_ROWS)

    @property
    def gutter_width(self) -> int:
        return sum(gutter.width for gutter in self._gutters)

    def on_mount(self) -> None:
        self._theme = code_theme(self.app.current_theme.dark)
        self.app.theme_changed_signal.subscribe(self, self._theme_changed)

    def _theme_changed(self, theme) -> None:
        self._theme = code_theme(theme.dark)
        self._repaint()

    def show(self, document: Document, display_path: str = "") -> None:
        self.document, self.display_path = document, display_path
        self.cursor_row = self.cursor_column = 0
        self._highlighter = PlainHighlighter()
        self._gutters = [LineNumberGutter(len(document.lines))]
        widest = max(document.lines, key=len, default="")
        self.virtual_size = Size(line_cells(widest) + 1 + self.gutter_width, max(1, len(document.lines)))
        self.scroll_to(0, 0, animate=False, immediate=True)
        self._repaint()
        if document.language is not None and not document.plain:
            self._highlight(document)

    # The parse runs off the UI thread so a big file shows at once as plain text.
    # A failure only costs the colors, so it must not end the session.
    @work(thread=True, exclusive=True, group="highlight", exit_on_error=False)
    def _highlight(self, document: Document) -> None:
        highlighter = make_highlighter(document.language, document.text)
        self.app.call_from_thread(self._highlighted, document, highlighter)

    def _highlighted(self, document: Document, highlighter: Highlighter) -> None:
        if document is self.document:
            self._highlighter = highlighter
            self._repaint()

    def _repaint(self) -> None:
        self._strips.clear()
        self.refresh()

    def render_line(self, y: int) -> Strip:
        row = y + self.scroll_offset.y
        width = self.scrollable_content_region.width
        document = self.document
        if document is None or row >= max(1, len(document.lines)):
            return Strip.blank(width, self._theme.base)
        if not document.lines:
            return self._notice(document.notice or "", width)
        gutter = Strip([segment for gutter in self._gutters
                        for segment in gutter.render(row, row == self.cursor_row, self._theme).render(self.app.console)],
                       self.gutter_width)
        left = self.scroll_offset.x
        code = self._code_strip(row).crop_extend(left, left + width - self.gutter_width, self._theme.base)
        return Strip.join([gutter, code])

    def _notice(self, notice: str, width: int) -> Strip:
        text = Text(f" {notice}", style=self._theme.gutter, no_wrap=True, end="")
        return Strip(text.render(self.app.console), text.cell_len).extend_cell_length(width, self._theme.base)

    def _code_strip(self, row: int) -> Strip:
        is_cursor_row = row == self.cursor_row
        key = (row, self.cursor_column if is_cursor_row else None)
        strip = self._strips.get(key)
        if strip is None:
            text = build_line(self.document.lines[row], self._spans(row), self._theme, is_cursor_row=is_cursor_row,
                              cursor_column=self.cursor_column if is_cursor_row else None)
            strip = Strip(text.render(self.app.console), text.cell_len)
            self._strips[key] = strip
        return strip

    # A highlighter bug must not take the whole viewer down with it.
    def _spans(self, row: int):
        try:
            return self._highlighter.spans(row, row + 1)[0]
        except Exception:
            log.exception("Highlighting failed, showing plain text")
            self._highlighter = PlainHighlighter()
            return []
