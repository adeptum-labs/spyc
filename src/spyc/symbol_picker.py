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
from spyc.core.fuzzy import rank_counted
from spyc.core.picking import Item
from spyc.core.printable import printable
from spyc.core.source import FileSource
from spyc.symbol_index import Located

KIND_WIDTH = 10
LIST_LIMIT = 200
PAUSE = 0.15


# Definitions to pick from: those of one file for the outline, of the whole
# project, or the candidates for a name. `entries` is asked on every search,
# because the index may still be filling. A list that is cut to `limit` says
# how many there are, and is searched in the background, since it may be huge.
# Where the path is shown it is searched too, so "parser src/api" narrows the
# definitions by their directory.
class SymbolSource:
    def __init__(self, source: FileSource | None, entries: Callable[[], Sequence[Located]], placeholder: str,
                 show_path: bool, status: Callable[[], str] = lambda: "", limit: int | None = None) -> None:
        self._source, self._entries, self.placeholder = source, entries, placeholder
        self._show_path, self._status, self._limit = show_path, status, limit
        self.threaded = limit is not None
        self.debounce = PAUSE if self.threaded else 0.0
        self._counts = (0, 0)

    def summary(self) -> str:
        shown, total = self._counts
        cut = f"{shown:,} of {total:,}" if shown < total else ""
        return "  ".join(part for part in (self._status(), cut) if part)

    def search(self, query: str) -> list[Item]:
        entries = list(self._entries())
        ranked, matched = rank_counted([self._searched_text(entry) for entry in entries], query,
                                       self._limit or len(entries))
        self._counts = (len(ranked), matched)
        return [Item(entries[index].path, self._label(entries[index], marked), entries[index].symbol.line,
                     entries[index].symbol.column)
                for index, marked in ranked]

    def _searched_text(self, entry: Located) -> str:
        return f"{entry.symbol.name}  {entry.path}" if self._show_path else entry.symbol.name

    def preview(self, item: Item) -> Document | None:
        try:
            return self._source.document(item.key)
        except OSError:
            return None

    def _label(self, entry: Located, marked: tuple[int, ...]) -> Text:
        label = Text(no_wrap=True, overflow="ellipsis")
        label.append(f"{printable(entry.symbol.kind):<{KIND_WIDTH}}", style="dim")
        label.append(printable(entry.symbol.name))
        for position in marked:
            label.stylize("bold yellow", KIND_WIDTH + position, KIND_WIDTH + position + 1)
        if self._show_path:
            label.append(f"  {printable(entry.path)}:{entry.symbol.line}", style="dim")
        return label
