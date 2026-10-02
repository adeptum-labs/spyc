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


from collections.abc import Callable, Sequence

from rich.text import Text

from spyc.core.document import Document
from spyc.core.fuzzy import Match, PathMatcher
from spyc.core.location import split_line_suffix
from spyc.core.picking import Item
from spyc.core.printable import printable
from spyc.core.source import FileSource


class FilePickerSource:
    placeholder = "Find file  (name:line jumps to a line)"

    def __init__(self, source: FileSource, matcher: PathMatcher, recent: Callable[[], Sequence[str]]) -> None:
        self._source, self._matcher, self._recent = source, matcher, recent

    def search(self, query: str) -> list[Item]:
        text, line = split_line_suffix(query)
        return [Item(match.path, _label(match), line) for match in self._matcher.search(text, self._recent())]

    def preview(self, item: Item) -> Document | None:
        try:
            return self._source.document(item.key)
        except OSError:
            return None


# The file name comes first so that a narrow list cuts the directory, not the
# name; the characters that matched are marked wherever they ended up.
def _label(match: Match) -> Text:
    path = printable(match.path)
    directory_end = path.rfind("/") + 1
    name, directory = path[directory_end:], path[:directory_end].rstrip("/")
    label = Text(name, no_wrap=True, overflow="ellipsis")
    if directory:
        label.append("  ")
        label.append(directory, style="dim")
    for position in match.positions:
        if position >= directory_end:
            marked = position - directory_end
        elif position < len(directory):
            marked = len(name) + 2 + position
        else:
            continue
        label.stylize("bold yellow", marked, marked + 1)
    return label
