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
from spyc.fuzzy import rank
from spyc.picking import Item
from spyc.printable import printable
from spyc.symbol_index import Located

KIND_WIDTH = 10
LIST_LIMIT = 200


# Definitions to pick from: those of one file for the outline, of the whole
# project, or the candidates for a name. `entries` is asked on every search,
# because the index may still be filling.
class SymbolSource:
    def __init__(self, root: Path | None, entries: Callable[[], Sequence[Located]], placeholder: str,
                 show_path: bool, status: Callable[[], str] = lambda: "") -> None:
        self._root, self._entries, self.placeholder = root, entries, placeholder
        self._show_path, self._status = show_path, status

    def summary(self) -> str:
        return self._status()

    def search(self, query: str) -> list[Item]:
        entries = list(self._entries())
        ranked = rank([entry.symbol.name for entry in entries], query, LIST_LIMIT)
        return [Item(entries[index].path, self._label(entries[index], marked), entries[index].symbol.line)
                for index, marked in ranked]

    def preview(self, item: Item) -> Document | None:
        try:
            return load_document(self._root / item.key)
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
