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
from textual.widgets.text_area import TextAreaTheme

from spyc.syntax.theme import CodeTheme, SyntaxTheme


def code_theme(dark: bool) -> CodeTheme:
    source = TextAreaTheme.get_builtin_theme("monokai" if dark else "github_light")
    return CodeTheme(
        syntax=SyntaxTheme(source.syntax_styles),
        base=source.base_style or Style(),
        cursor_line=source.cursor_line_style or Style(bgcolor="#3e3d32" if dark else "#eeeeee"),
        cursor=source.cursor_style or Style(reverse=True),
        match=Style(bgcolor="#665c00" if dark else "#fff3a3"),
        current_match=Style(bgcolor="#b58900" if dark else "#ffd33d", color="black"),
        gutter=source.gutter_style or Style(dim=True),
        gutter_cursor=source.cursor_line_gutter_style or Style(bold=True),
    )
