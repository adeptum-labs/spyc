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


from collections.abc import Mapping
from dataclasses import dataclass

from rich.style import Style

# Queries written for other editors use their own vocabulary; these are the
# names that differ from the ones Textual themes define.
CAPTURE_ALIASES = {
    "conditional": "keyword", "repeat": "keyword", "include": "keyword", "exception": "keyword",
    "storageclass": "keyword", "keyword.control": "keyword", "keyword.directive": "keyword",
    "method": "function.method", "parameter": "variable.parameter", "field": "property",
    "namespace": "type", "label": "constant", "string.regex": "string.special",
    "text.title": "heading", "text.uri": "link", "type.class": "type",
}


class SyntaxTheme:
    def __init__(self, styles: Mapping[str, Style]) -> None:
        self._styles = styles

    def style_for(self, capture: str) -> Style | None:
        return self._lookup(capture) or self._lookup(CAPTURE_ALIASES.get(capture, ""))

    def _lookup(self, capture: str) -> Style | None:
        while capture:
            if capture in self._styles:
                return self._styles[capture]
            capture = capture.rpartition(".")[0]
        return None


@dataclass(frozen=True)
class CodeTheme:
    syntax: SyntaxTheme
    base: Style
    cursor_line: Style
    cursor: Style
    match: Style
    current_match: Style
    gutter: Style
    gutter_cursor: Style
