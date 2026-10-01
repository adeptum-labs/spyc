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


from rich.text import Text

from spyc.core.document import Document
from spyc.core.fuzzy import rank_counted
from spyc.core.picking import Item
from spyc.core.printable import printable
from spyc.deps.graph import FILE, UNIT, DependencyGraph

LIST_LIMIT = 200


# The packages, directories and files of the graph, to pick one to look at.
class NodeSource:
    previews = False
    placeholder = "Find a package, directory or file by name"

    def __init__(self, graph: DependencyGraph) -> None:
        self._nodes = [*graph.nodes(UNIT), *graph.nodes(FILE)]

    def search(self, query: str) -> list[Item]:
        ranked, _ = rank_counted([node.name for node in self._nodes], query, LIST_LIMIT)
        return [Item(f"{self._nodes[index].level}:{self._nodes[index].key}", self._label(self._nodes[index].name, marked))
                for index, marked in ranked]

    def preview(self, item: Item) -> Document | None:
        return None

    @staticmethod
    def _label(name: str, marked: tuple[int, ...]) -> Text:
        label = Text(printable(name), no_wrap=True, overflow="ellipsis")
        for position in marked:
            label.stylize("bold yellow", position, position + 1)
        return label
