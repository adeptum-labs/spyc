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
from textual import events, work
from textual.binding import Binding
from textual.cache import LRUCache
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from spyc.cells import cell_of_char, char_at_cell, widest_cells
from spyc.document import Document
from spyc.gutters import Gutter, LineNumberGutter
from spyc.line_text import build_line
from spyc.matches import find_matches
from spyc.syntax.factory import make_highlighter
from spyc.syntax.spans import Highlighter, PlainHighlighter
from spyc.widgets.code_theme import code_theme

log = logging.getLogger(__name__)
CACHED_ROWS = 512


class CodeView(ScrollView, can_focus=True):
    BINDINGS = [
        Binding("up,k", "move(-1, 0)", show=False),
        Binding("down,j", "move(1, 0)", show=False),
        Binding("left", "move(0, -1)", show=False),
        Binding("right", "move(0, 1)", show=False),
        Binding("home", "line_edge(0)", show=False),
        Binding("end", "line_edge(1)", show=False),
        Binding("pageup", "page(-1)", show=False),
        Binding("pagedown,space", "page(1)", show=False),
        Binding("ctrl+u", "page(-0.5)", show=False),
        Binding("ctrl+d", "page(0.5)", show=False),
        Binding("ctrl+home", "file_edge(0)", show=False),
        Binding("ctrl+end", "file_edge(1)", show=False),
        Binding("n", "match(1)", show=False),
        Binding("N", "match(-1)", show=False),
    ]
    SCROLL_MARGIN = 3

    class CursorMoved(Message):
        def __init__(self, row: int, column: int) -> None:
            super().__init__()
            self.row, self.column = row, column

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.document: Document | None = None
        self.display_path = ""
        self.cursor_row = 0
        self.cursor_column = 0
        self._goal_cell = 0
        self._matches: list[tuple[int, int, int]] = []
        self._matches_by_row: dict[int, list[tuple[int, int]]] = {}
        self._current_match = 0
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
        self._highlighter = PlainHighlighter()
        self._gutters = [LineNumberGutter(len(document.lines))]
        self.virtual_size = Size(widest_cells(document.lines) + 1 + self.gutter_width, max(1, len(document.lines)))
        self.scroll_to(0, 0, animate=False, immediate=True)
        self.clear_search()
        self._move_to(0, 0)
        if document.language is not None and not document.plain:
            self._highlight(document)

    def replace(self, document: Document) -> None:
        row, column, offset = self.cursor_row, self.cursor_column, self.scroll_offset
        self.show(document, self.display_path)
        self.scroll_to(offset.x, offset.y, animate=False, immediate=True)
        self._move_to(row, column)

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

    def _lines(self) -> tuple[str, ...]:
        return self.document.lines if self.document else ()

    def _move_to(self, row: int, column: int | None = None) -> None:
        lines = self._lines()
        row = min(max(row, 0), max(len(lines) - 1, 0))
        line = lines[row] if lines else ""
        if column is None:
            column = char_at_cell(line, self._goal_cell)
        else:
            column = min(max(column, 0), len(line))
            self._goal_cell = cell_of_char(line, column)
        self.cursor_row, self.cursor_column = row, column
        self._reveal(line)
        self.refresh()
        self.post_message(self.CursorMoved(row, column))

    def _reveal(self, line: str) -> None:
        region = self.scrollable_content_region
        margin = max(0, min(self.SCROLL_MARGIN, (region.height - 1) // 2))
        top = self.scroll_offset.y
        if self.cursor_row < top + margin:
            top = max(0, self.cursor_row - margin)
        elif self.cursor_row >= top + region.height - margin:
            top = self.cursor_row - region.height + margin + 1
        left, code_width = self.scroll_offset.x, max(1, region.width - self.gutter_width)
        cell = cell_of_char(line, self.cursor_column)
        if cell < left:
            left = cell
        elif cell + 1 > left + code_width:
            left = cell + 1 - code_width
        self.scroll_to(left, top, animate=False, immediate=True)

    def goto(self, line: int, column: int = 0) -> None:
        row = min(max(line - 1, 0), max(len(self._lines()) - 1, 0))
        height = self.scrollable_content_region.height
        if not self.scroll_offset.y <= row < self.scroll_offset.y + height:
            self.scroll_to(y=max(0, row - height // 2), animate=False, immediate=True)
        self._move_to(row, column)

    def action_move(self, rows: int, columns: int) -> None:
        if rows:
            self._move_to(self.cursor_row + rows)
        if columns:
            self._move_to(self.cursor_row, self.cursor_column + columns)

    def action_line_edge(self, end: int) -> None:
        self._move_to(self.cursor_row, len(self._lines()[self.cursor_row]) if end and self._lines() else 0)

    def action_page(self, fraction: float) -> None:
        rows = max(1, int(self.scrollable_content_region.height * abs(fraction)) - (1 if abs(fraction) >= 1 else 0))
        self._move_to(self.cursor_row + (rows if fraction > 0 else -rows))

    def action_file_edge(self, end: int) -> None:
        self._move_to(len(self._lines()) - 1 if end else 0)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        lines = self._lines()
        row = event.y + self.scroll_offset.y
        if row >= len(lines):
            return
        self.focus()
        cell = max(0, event.x - self.gutter_width + self.scroll_offset.x)
        self._move_to(row, char_at_cell(lines[row], cell))

    def search(self, query: str) -> int:
        self._matches = find_matches(self._lines(), query)
        self._matches_by_row = {}
        for row, start, end in self._matches:
            self._matches_by_row.setdefault(row, []).append((start, end))
        self._current_match = next((index for index, (row, start, _) in enumerate(self._matches)
                                    if (row, start) >= (self.cursor_row, self.cursor_column)), 0)
        self._repaint()
        self._go_to_current_match()
        return len(self._matches)

    def clear_search(self) -> None:
        self._matches, self._matches_by_row, self._current_match = [], {}, 0
        self._repaint()

    @property
    def match_status(self) -> str:
        return f"{self._current_match + 1}/{len(self._matches)}" if self._matches else ""

    def action_match(self, step: int) -> None:
        if self._matches:
            self._current_match = (self._current_match + step) % len(self._matches)
            self._repaint()
            self._go_to_current_match()

    def _go_to_current_match(self) -> None:
        if self._matches:
            row, start, _ = self._matches[self._current_match]
            self.goto(row + 1, start)

    def _current_match_on(self, row: int) -> tuple[int, int] | None:
        if not self._matches:
            return None
        match_row, start, end = self._matches[self._current_match]
        return (start, end) if match_row == row else None

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
                              cursor_column=self.cursor_column if is_cursor_row else None,
                              matches=self._matches_by_row.get(row, ()), current_match=self._current_match_on(row))
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
