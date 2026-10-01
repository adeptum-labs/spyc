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


from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass

from spyc.deps.graph import FILE, UNIT, DependencyGraph, Node, components

ROOT_KIND, PACKAGE, DIRECTORY = "root", "package", "directory"
SEPARATORS = {PACKAGE: ".", DIRECTORY: "/"}
OWN_LABEL = "(files)"


# One box of the diagram: a package or directory with everything under it, a file (whose one part is its path), or,
# with `own`, only the files that lie directly in a package or directory that also has subpackages.
@dataclass(frozen=True, order=True)
class Member:
    kind: str
    parts: tuple[str, ...] = ()
    own: bool = False

    @property
    def key(self) -> str:
        return self.parts[0] if self.kind == FILE else SEPARATORS.get(self.kind, "/").join(self.parts)

    @property
    def unit(self) -> Node:
        return Node(UNIT, self.key or ("." if self.kind == DIRECTORY else ""))


ROOT = Member(ROOT_KIND)


def label_of(member: Member, scope: Member) -> str:
    if member.own:
        return OWN_LABEL
    if member.kind == FILE:
        return member.key.rsplit("/", 1)[-1]
    return SEPARATORS[member.kind].join(member.parts[len(scope.parts):])


def title_of(scope: Member, project: str) -> str:
    name = scope.key or project
    return f"{name} {OWN_LABEL}" if scope.own else name


# The packages and directories of a DependencyGraph as a tree that is shown one level at a time: a scope is a
# package or directory, and what it shows are the next parts of the names under it, each rolled up.
class Hierarchy:
    def __init__(self, graph: DependencyGraph) -> None:
        self._graph = graph
        self._places: dict[Node, Member] = {}
        for unit in graph.nodes(UNIT):
            kind = graph.kind_of(unit)
            self._places[unit] = Member(kind, () if unit.key in ("", ".") else tuple(unit.key.split(SEPARATORS[kind])))

    def _holders(self, scope: Member) -> dict[Node, Member]:
        depth, held = len(scope.parts), {}
        for unit, place in self._places.items():
            if scope.kind in (ROOT_KIND, place.kind) and place.parts[:depth] == scope.parts:
                held[unit] = Member(place.kind, place.parts[:depth + 1], own=len(place.parts) == depth)
        return held

    @staticmethod
    def _shows_files(scope: Member, found: set[Member]) -> bool:
        return scope.own or (len(found) == 1 and next(iter(found)).own)

    def members(self, scope: Member) -> list[Member]:
        found = set(self._holders(scope).values())
        if not self._shows_files(scope, found):
            return sorted(found)
        holder = scope if scope.own else next(iter(found))
        return sorted(Member(FILE, (file.key,)) for file in self._graph.children(Member(holder.kind, holder.parts).unit))

    def _units_under(self, member: Member) -> list[Node]:
        return [unit for unit, place in self._places.items() if place.kind == member.kind
                and place.parts[:len(member.parts)] == member.parts and (not member.own or place.parts == member.parts)]

    def _nodes_of(self, member: Member) -> list[Node]:
        return [Node(FILE, member.key)] if member.kind == FILE else self._units_under(member)

    def paths_of(self, member: Member) -> list[str]:
        return sorted({path for node in self._nodes_of(member) for path in self._graph.paths_of(node)})

    def externals(self, member: Member) -> list[tuple[str, int]]:
        total: Counter = Counter()
        for node in self._nodes_of(member):
            total.update(dict(self._graph.externals(node)))
        return sorted(total.items(), key=lambda item: (-item[1], item[0]))

    def edges(self, scope: Member) -> dict[Member, dict[Member, int]]:
        shown = self.members(scope)
        edges: dict[Member, dict[Member, int]] = defaultdict(dict)
        if shown and shown[0].kind == FILE:
            known = {member.key: member for member in shown}
            for member in shown:
                for link in self._graph.outgoing(Node(FILE, member.key)):
                    if link.node.key in known:
                        edges[member][known[link.node.key]] = link.weight
            return edges
        holders = self._holders(scope)
        for unit, source in holders.items():
            for link in self._graph.outgoing(unit):
                target = holders.get(link.node)
                if target is not None and target != source:
                    edges[source][target] = edges[source].get(target, 0) + link.weight
        return edges

    @staticmethod
    def cycles(edges: dict[Member, dict[Member, int]], members: list[Member]) -> dict[Member, frozenset[Member]]:
        return {member: group for member, group in components(edges, members).items() if len(group) > 1}

    # A scope with one box in it would only be a step to click through, so it shows what that box shows.
    def settle(self, scope: Member) -> Member:
        shown = self.members(scope)
        while len(shown) == 1 and shown[0].kind != FILE and not shown[0].own:
            scope = shown[0]
            shown = self.members(scope)
        return scope

    @staticmethod
    def _ancestors(scope: Member) -> Iterator[Member]:
        if scope.own:
            yield Member(scope.kind, scope.parts)
        for length in range(len(scope.parts) - 1, 0, -1):
            yield Member(scope.kind, scope.parts[:length])
        yield ROOT

    def parent(self, scope: Member) -> Member | None:
        for candidate in self._ancestors(scope):
            if (shown := self.settle(candidate)) != scope:
                return shown
        return None

    def containing(self, scope: Member, inner: Member) -> Member | None:
        units = self._units_under(inner)
        return self._holders(scope).get(units[0]) if units else None

    # Where a package, directory or file is on show: the scope that has it as a box, and the box.
    def locate(self, node: Node) -> tuple[Member, Member]:
        unit = node if node.level == UNIT else self._graph.unit_of(node.key)
        place = self._places.get(unit) if unit is not None else None
        scope = self.settle(ROOT)
        while place is not None:
            shown = self.members(scope)
            if shown and shown[0].kind == FILE:
                file = Member(FILE, (node.key,))
                return scope, file if file in shown else shown[0]
            held = self._holders(scope).get(unit)
            if held is None:
                break
            if node.level == UNIT and (held.own or held.parts == place.parts):
                return scope, held
            scope = self.settle(held)
        shown = self.members(scope)
        return scope, shown[0] if shown else scope
