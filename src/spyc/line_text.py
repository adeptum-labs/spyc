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


from collections.abc import Sequence

from rich.text import Text

from spyc.cells import expand_tabs
from spyc.syntax.spans import Span
from spyc.syntax.theme import CodeTheme


# Styles are applied in this order so that later ones show through: syntax
# colors, then search matches, then the cursor.
def build_line(line: str, spans: Sequence[Span], theme: CodeTheme, *, is_cursor_row: bool = False,
               cursor_column: int | None = None, matches: Sequence[tuple[int, int]] = (),
               current_match: tuple[int, int] | None = None) -> Text:
    expanded, starts = expand_tabs(line)
    text = Text(expanded, style=theme.cursor_line if is_cursor_row else theme.base, no_wrap=True, end="")
    for span in spans:
        style = theme.syntax.style_for(span.capture)
        if style is not None:
            text.stylize(style, starts[span.start], starts[span.end])
    for start, end in matches:
        text.stylize(theme.current_match if (start, end) == current_match else theme.match, starts[start], starts[end])
    if cursor_column is not None and cursor_column >= len(line):
        text.append(" ", theme.cursor)
    elif cursor_column is not None:
        text.stylize(theme.cursor, starts[cursor_column], starts[cursor_column + 1])
    return text
