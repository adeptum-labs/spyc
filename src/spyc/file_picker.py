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
from pathlib import Path

from rich.text import Text

from spyc.document import Document, load_document
from spyc.fuzzy import Match, PathMatcher
from spyc.location import split_line_suffix
from spyc.picking import Item
from spyc.printable import printable


class FilePickerSource:
    placeholder = "Find file  (name:line jumps to a line)"

    def __init__(self, root: Path, matcher: PathMatcher, recent: Callable[[], Sequence[str]]) -> None:
        self._root, self._matcher, self._recent = root, matcher, recent

    def search(self, query: str) -> list[Item]:
        text, line = split_line_suffix(query)
        return [Item(match.path, _label(match), line) for match in self._matcher.search(text, self._recent())]

    def preview(self, item: Item) -> Document | None:
        try:
            return load_document(self._root / item.key)
        except OSError:
            return None


def _label(match: Match) -> Text:
    label = Text(printable(match.path), no_wrap=True, overflow="ellipsis")
    label.stylize("dim", 0, match.path.rfind("/") + 1)
    for position in match.positions:
        label.stylize("bold yellow", position, position + 1)
    return label
