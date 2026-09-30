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


import posixpath
from collections.abc import Callable, Sequence

from spyc.assist.targets import Facts, Target
from spyc.core.document import Document
from spyc.deps.graph import FILE, UNIT, DependencyGraph, Link, Node
from spyc.symbol_index import SymbolIndex
from spyc.symbols import CLASS_KINDS, enclosing_definition

ROOT_DIRECTORY = "."
MAX_FACTS = 10
MAX_DEFINITIONS = 40


# What Claude can be asked about in the project, and what spyc itself already knows about it. The graph and the
# file list arrive while spyc runs, so they are asked for when needed and may still be missing.
class About:
    def __init__(self, symbols: SymbolIndex, paths: Callable[[], Sequence[str] | None],
                 graph: Callable[[], DependencyGraph | None]) -> None:
        self._symbols, self._paths, self._graph = symbols, paths, graph

    def directory(self, directory: str) -> Target:
        directory = directory.strip("/") or ROOT_DIRECTORY
        prefix = "" if directory == ROOT_DIRECTORY else f"{directory}/"
        return Target("directory", directory, directory, tuple(sorted(path for path in self._paths() or () if path.startswith(prefix))))

    @staticmethod
    def file(path: str) -> Target:
        return Target("file", path, path, (path,))

    @staticmethod
    def class_named(path: str, name: str, line: int) -> Target:
        return Target("class", f"{path}:{name}", name, (path,), line)

    # The class around the cursor, the file, and the package or directory of the file: the smallest first.
    def scopes(self, path: str, document: Document, row: int) -> list[Target]:
        enclosing = None if document.plain else enclosing_definition(document.text, document.language, row + 1)
        scopes = [] if enclosing is None else [self.class_named(path, enclosing.name, enclosing.line)]
        return [*scopes, self.file(path), self._unit_of(path)]

    def _unit_of(self, path: str) -> Target:
        graph = self._graph()
        unit = graph.unit_of(path) if graph is not None else None
        if unit is not None and graph.kind_of(unit) == "package":
            return self.node(unit)
        return self.directory(posixpath.dirname(path))

    def node(self, node: Node) -> Target | None:
        graph = self._graph()
        if graph is None or not graph.has(node):
            return None
        kind = graph.kind_of(node)
        if node.level == UNIT:
            if kind == "directory":
                return self.directory(node.key)
            return Target("package", node.key, node.name, tuple(sorted(graph.paths_of(node))))
        paths = graph.paths_of(node)
        if node.level == FILE:
            return self.file(node.key)
        return self.class_named(paths[0], node.name.rsplit(".", 1)[-1], graph.line_of(node) or 1) if paths else None

    def facts_of(self, target: Target) -> Facts:
        definitions = self._definitions(target)
        graph = self._graph()
        node = self._graph_node(graph, target) if graph is not None else None
        if node is None:
            return Facts(definitions=definitions)
        return Facts(depends_on=_links(graph.outgoing(node)), used_by=_links(graph.incoming(node)),
                     external=tuple(f"{name} ×{count}" for name, count in graph.externals(node)[:MAX_FACTS]),
                     cycles=tuple(sorted(member.name for member in graph.cycle_members(node)))[:MAX_FACTS], definitions=definitions)

    @staticmethod
    def _graph_node(graph: DependencyGraph, target: Target) -> Node | None:
        match target.kind:
            case "directory" | "package":
                node = Node(UNIT, target.key)
            case "file":
                node = Node(FILE, target.key)
            case _:
                file = Node(FILE, target.paths[0])
                node = next((child for child in graph.children(file) if child.name.rsplit(".", 1)[-1] == target.label), None)
        return node if node is not None and graph.has(node) else None

    # A directory or a package is told by its classes; a file or a class by everything it defines.
    def _definitions(self, target: Target) -> tuple[str, ...]:
        wanted = set(target.paths)
        whole = target.kind in ("file", "class")
        found = (f"{item.symbol.kind} {item.symbol.name} ({item.path}:{item.symbol.line})"
                 for item in self._symbols.all()
                 if item.path in wanted and (whole or item.symbol.kind in CLASS_KINDS))
        return tuple(found)[:MAX_DEFINITIONS]


def _links(links: list[Link]) -> tuple[str, ...]:
    return tuple(f"{link.node.name} ×{link.weight}" for link in links[:MAX_FACTS])
