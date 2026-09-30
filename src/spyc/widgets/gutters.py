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


from typing import Protocol

from rich.style import Style
from rich.text import Text

from spyc.cells import fit_cells
from spyc.coverage.model import Lines
from spyc.git.blame import BlameLine
from spyc.git.changes import LineChanges
from spyc.printable import printable
from spyc.syntax.theme import CodeTheme
from spyc.timeago import age

MIN_DIGITS = 3


class Gutter(Protocol):
    width: int

    def render(self, row: int, is_cursor_row: bool, theme: CodeTheme) -> Text: ...


class LineNumberGutter:
    def __init__(self, line_count: int) -> None:
        self._digits = max(MIN_DIGITS, len(str(line_count)))
        self.width = self._digits + 2

    def render(self, row: int, is_cursor_row: bool, theme: CodeTheme) -> Text:
        return Text(f" {row + 1:>{self._digits}} ", style=theme.gutter_cursor if is_cursor_row else theme.gutter)


ADDED_MARK = ("▎ ", Style(color="green"))
MODIFIED_MARK = ("▎ ", Style(color="yellow"))
DELETED_MARK = ("▔ ", Style(color="red"))
NO_MARK = ("  ", Style())


class ChangeGutter:
    width = 2

    def __init__(self, changes: LineChanges) -> None:
        self._changes = changes

    def render(self, row: int, is_cursor_row: bool, theme: CodeTheme) -> Text:
        line = row + 1
        if line in self._changes.added:
            mark = ADDED_MARK
        elif line in self._changes.modified:
            mark = MODIFIED_MARK
        elif line in self._changes.deleted:
            mark = DELETED_MARK
        else:
            mark = NO_MARK
        return Text(mark[0], style=mark[1])


COVERED_MARK = ("● ", Style(color="green"))
PARTIAL_MARK = ("◐ ", Style(color="yellow"))
MISSED_MARK = ("○ ", Style(color="red"))


class CoverageGutter:
    width = 2

    def __init__(self, lines: Lines) -> None:
        self._lines = lines

    def render(self, row: int, is_cursor_row: bool, theme: CodeTheme) -> Text:
        line = self._lines.get(row + 1)
        if line is None:
            return Text(*NO_MARK)
        mark = MISSED_MARK if line.hits == 0 else PARTIAL_MARK if line.partial else COVERED_MARK
        return Text(mark[0], style=mark[1])


WEEK = 7 * 86400
MONTH = 30 * 86400
YEAR = 365 * 86400
BLAME_WIDTH = 22


class BlameGutter:
    width = BLAME_WIDTH

    def __init__(self, lines: list[BlameLine], now: float) -> None:
        self._lines, self._now = lines, now

    def render(self, row: int, is_cursor_row: bool, theme: CodeTheme) -> Text:
        blank = Text(" " * BLAME_WIDTH)
        if row >= len(self._lines) or (row > 0 and self._lines[row - 1].hash == self._lines[row].hash):
            return blank
        line = self._lines[row]
        if line.uncommitted:
            return Text("(uncommitted)".ljust(BLAME_WIDTH), style=Style(color="yellow", italic=True))
        seconds = self._now - line.timestamp
        color = "green" if seconds < WEEK else "cyan" if seconds < MONTH else "yellow" if seconds < YEAR else None
        style = Style(color=color) if color else Style(dim=True)
        return Text(f"{line.hash[:7]} {fit_cells(printable(line.author), 8)} {age(seconds):>4} ", style=style)
