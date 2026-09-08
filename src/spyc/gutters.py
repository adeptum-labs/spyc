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

from spyc.git.changes import LineChanges
from spyc.syntax.theme import CodeTheme

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
