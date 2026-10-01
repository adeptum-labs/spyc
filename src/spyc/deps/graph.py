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
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from spyc.deps.facts import FileFacts, Import
from spyc.deps.golang import GoModules
from spyc.deps.includes import IncludeModules
from spyc.deps.javascript import ScriptModules
from spyc.deps.python import PythonModules
from spyc.deps.rust import RustCrates
from spyc.deps.testfiles import is_test_path

UNIT, FILE = "unit", "file"
LEVELS = (UNIT, FILE)
KIND_NAMES = {FILE: "file"}
JVM = frozenset({"", "java", "kotlin"})
SCRIPTS = frozenset({"javascript", "typescript", "tsx"})
C_FAMILY = frozenset({"c", "cpp"})
# Files that only say what the project calls its packages and crates; they are not nodes.
MANIFESTS = frozenset({"gomod", "cargo"})
DEFAULT_UNIT = "(default)"
EXTERNAL_SEGMENTS = 2


# The caller asked for the build to stop, for instance because the app is being left.
class Stopped(Exception):
    pass


@dataclass(frozen=True, order=True)
class Node:
    level: str
    key: str

    @property
    def name(self) -> str:
        return self.key or DEFAULT_UNIT if self.level == UNIT else self.key


@dataclass(frozen=True)
class Link:
    node: Node
    weight: int


Edges = dict[Node, dict[Node, int]]
Target = tuple[str, str, str]


def _external_name(path: str) -> str:
    return ".".join(path.split(".")[:EXTERNAL_SEGMENTS])


# A Java or Kotlin file is in the package it declares; any other file is in its directory.
def unit_key(path: str, facts: FileFacts) -> str:
    return facts.unit if facts.language in JVM else posixpath.dirname(path) or "."


# Go lets the tests of a package import packages that import it back, which is no cycle of the program;
# so what the tests use is drawn between files but not between directories.
def _is_go_test(path: str, facts: FileFacts) -> bool:
    return facts.language == "go" and path.endswith("_test.go")


# What the project holds, for each language to look its imports up in.
class _Project:
    def __init__(self, files: Mapping[str, FileFacts]) -> None:
        self.files = files
        self.jvm = _Definitions(files)
        self.python = PythonModules(path for path, facts in files.items() if facts.language == "python")
        self.scripts = ScriptModules(path for path, facts in files.items() if facts.language in SCRIPTS)
        self.go = GoModules(files)
        self.rust = RustCrates(files)
        self.includes = IncludeModules(path for path, facts in files.items() if facts.language in C_FAMILY)


# What the project defines, to look imports up in. Where two files define the same
# class of a package (main and test), the first path in order wins.
class _Definitions:
    def __init__(self, files: Mapping[str, FileFacts]) -> None:
        self.classes: dict[tuple[str, str], str] = {}
        self.units: set[str] = set()
        for path, facts in sorted(files.items()):
            if facts.language not in JVM:
                continue
            self.units.add(facts.unit)
            for definition in facts.classes:
                self.classes.setdefault((facts.unit, definition.name), path)

    # The class an import names: the whole path, or the longest start of it, for a
    # nested class (a.B.Inner) or a member (a.B.method).
    def class_of(self, dotted: str) -> Target | None:
        segments = dotted.split(".")
        for length in range(len(segments), 0, -1):
            unit, _, name = ".".join(segments[:length]).rpartition(".")
            if (path := self.classes.get((unit, name))) is not None:
                return path, unit, name
        return None


# What one file depends on: classes (file, unit, name), units reached without naming
# a class, and what is outside the project.
@dataclass
class _Reach:
    targets: set[Target]
    units: set[str]
    external: Counter


def _reach(path: str, facts: FileFacts, project: "_Project") -> _Reach:
    if facts.language not in JVM:
        return _reach_files(path, facts, project)
    reach, wildcards = _Reach(set(), set(), Counter()), set()
    for imported in facts.imports:
        _follow(imported, project.jvm, reach, wildcards)
    for unit in {facts.unit, *wildcards}:
        for name in facts.used:
            if (found := project.jvm.classes.get((unit, name))) is not None:
                reach.targets.add((found, unit, name))
    own = {(facts.unit, definition.name) for definition in facts.classes}
    reach.targets = {target for target in reach.targets if target[0] != path and (target[1], target[2]) not in own}
    return reach


def _add_file(reach: _Reach, project: "_Project", path: str, target: str | None) -> None:
    if target is not None and target != path and target in project.files:
        reach.targets.add((target, unit_key(target, project.files[target]), ""))


def _count_external(reach: _Reach, external: str | None) -> None:
    if external:
        reach.external[external] += 1


def _python(path: str, imported: Import, project: "_Project", reach: _Reach) -> None:
    found, external = project.python.resolve(path, imported)
    for target in found:
        _add_file(reach, project, path, target)
    _count_external(reach, external)


def _script(path: str, imported: Import, project: "_Project", reach: _Reach) -> None:
    target, external = project.scripts.resolve(path, imported.path)
    _add_file(reach, project, path, target)
    _count_external(reach, external)


def _go(path: str, imported: Import, project: "_Project", reach: _Reach) -> None:
    directory, files, external = project.go.resolve(path, imported)
    if directory is not None:
        reach.units.add(directory or ".")
    for target in files:
        _add_file(reach, project, path, target)
    _count_external(reach, external)


def _rust(path: str, imported: Import, project: "_Project", reach: _Reach) -> None:
    target, external = project.rust.resolve(path, imported)
    _add_file(reach, project, path, target)
    _count_external(reach, external)


def _include(path: str, imported: Import, project: "_Project", reach: _Reach) -> None:
    target, external = project.includes.resolve(path, imported.path)
    _add_file(reach, project, path, target)
    _count_external(reach, external)


# A language without a handler is drawn as files without edges rather than read as something it is not.
_RESOLVERS = {"python": _python, "go": _go, "rust": _rust, **dict.fromkeys(SCRIPTS, _script),
              **dict.fromkeys(C_FAMILY, _include)}


# Every language that is not a JVM one is drawn as files in directories, which the resolvers find.
def _reach_files(path: str, facts: FileFacts, project: "_Project") -> _Reach:
    reach = _Reach(set(), set(), Counter())
    if (handler := _RESOLVERS.get(facts.language)) is not None:
        for imported in facts.imports:
            handler(path, imported, project, reach)
    return reach


def _follow(imported: Import, project: _Definitions, reach: _Reach, wildcards: set[str]) -> None:
    if imported.wildcard:
        if imported.static and (found := project.class_of(imported.path)):
            reach.targets.add(found)
        elif imported.path in project.units:
            wildcards.add(imported.path)
            reach.units.add(imported.path)
        else:
            reach.external[_external_name(imported.path)] += 1
    elif (found := project.class_of(imported.path)) is not None:
        reach.targets.add(found)
    elif imported.path.rpartition(".")[0] in project.units:
        reach.units.add(imported.path.rpartition(".")[0])
    else:
        reach.external[_external_name(imported.path)] += 1


# Who depends on whom, at two levels: unit (a package, or a directory) and file. The same graph without the
# test files is `code`, which is the graph itself when the project has no test files.
# Built once and never changed, so another thread may read it.
class DependencyGraph:
    def __init__(self, files: Mapping[str, FileFacts], stop: Callable[[], bool] = lambda: False) -> None:
        self._files = {path: facts for path, facts in files.items() if facts.language not in MANIFESTS}
        self._out: dict[str, Edges] = {level: defaultdict(dict) for level in LEVELS}
        self._in: dict[str, Edges] = {level: defaultdict(dict) for level in LEVELS}
        self._external: dict[Node, Counter] = defaultdict(Counter)
        self._children: dict[Node, list[Node]] = defaultdict(list)
        self._parent: dict[Node, Node] = {}
        self._components: dict[str, dict[Node, frozenset[Node]]] = {}
        self._directory_units: set[str] = set()
        project = _Project(dict(files))
        for path, facts in sorted(self._files.items()):
            self._add_structure(path, facts)
        for path, facts in sorted(self._files.items()):
            if stop():
                raise Stopped
            self._add_dependencies(path, facts, _reach(path, facts, project))
        for level in LEVELS:
            self._components[level] = components(self._out[level], self.nodes(level))
        production = {path: facts for path, facts in self._files.items() if not is_test_path(path)}
        self.code = self if len(production) == len(self._files) else DependencyGraph(production, stop)

    @property
    def has_tests(self) -> bool:
        return self.code is not self

    def _add_structure(self, path: str, facts: FileFacts) -> None:
        unit, file = Node(UNIT, unit_key(path, facts)), Node(FILE, path)
        self._children[unit].append(file)
        self._parent[file] = unit
        if facts.language not in JVM:
            self._directory_units.add(unit.key)

    def _add_dependencies(self, path: str, facts: FileFacts, reach: _Reach) -> None:
        own_unit = unit_key(path, facts)
        unit, file = Node(UNIT, own_unit), Node(FILE, path)
        files_in_unit = Counter(target_unit for target_unit, _ in {(unit_name, found) for found, unit_name, _ in reach.targets})
        units = set() if _is_go_test(path, facts) else reach.units | files_in_unit.keys()
        for target_unit in units:
            if target_unit != own_unit:
                self._link(UNIT, unit, Node(UNIT, target_unit), max(files_in_unit[target_unit], 1))
        for target_path, count in Counter(found for found, _, _ in reach.targets).items():
            self._link(FILE, file, Node(FILE, target_path), count)
        for name, count in reach.external.items():
            self._external[file][name] += count
            if not _is_go_test(path, facts):
                self._external[unit][name] += count

    def _link(self, level: str, source: Node, target: Node, weight: int) -> None:
        self._out[level][source][target] = self._out[level][source].get(target, 0) + weight
        self._in[level][target][source] = self._in[level][target].get(source, 0) + weight

    @property
    def empty(self) -> bool:
        return not self._files

    # What to call a node: a package (Java, Kotlin) or a directory (the other languages), or a file.
    def kind_of(self, node: Node) -> str:
        if node.level != UNIT:
            return KIND_NAMES[node.level]
        return "directory" if node.key in self._directory_units else "package"

    def has(self, node: Node) -> bool:
        return node in self._children or node in self._parent

    def nodes(self, level: str) -> list[Node]:
        if level == UNIT:
            return sorted(node for node in self._children if node.level == UNIT)
        return sorted(Node(FILE, path) for path in self._files)

    def outgoing(self, node: Node) -> list[Link]:
        return _links(self._out[node.level].get(node, {}))

    def incoming(self, node: Node) -> list[Link]:
        return _links(self._in[node.level].get(node, {}))

    def externals(self, node: Node) -> list[tuple[str, int]]:
        return sorted(self._external[node].items(), key=lambda item: (-item[1], item[0]))

    def children(self, node: Node) -> list[Node]:
        return list(self._children.get(node, []))

    def parent(self, node: Node) -> Node | None:
        return self._parent.get(node)

    def paths_of(self, node: Node) -> list[str]:
        if node.level == UNIT:
            return [child.key for child in self._children.get(node, [])]
        return [node.key]

    def unit_of(self, path: str) -> Node | None:
        return self._parent.get(Node(FILE, path))

    def degree(self, node: Node) -> int:
        return sum(link.weight for link in self.outgoing(node) + self.incoming(node))

    def most_connected(self, nodes: Iterable[Node]) -> Node | None:
        return min(nodes, key=lambda node: (-self.degree(node), node.name), default=None)

    # The other nodes of the same level that reach this one and are reached by it, directly or not.
    def cycle_members(self, node: Node) -> frozenset[Node]:
        return self._component_of(node) - {node}

    def cyclic_nodes(self, level: str) -> list[Node]:
        return [node for node in self.nodes(level) if len(self._component_of(node)) > 1]

    def _component_of(self, node: Node) -> frozenset[Node]:
        return self._components[node.level].get(node, frozenset({node}))


def _links(edges: Mapping[Node, int]) -> list[Link]:
    return sorted((Link(node, weight) for node, weight in edges.items()), key=lambda link: (-link.weight, link.node.name))


# Tarjan's algorithm with a stack of its own, since a chain of thousands of files
# would overflow the recursion limit.
def components(edges: Mapping[Node, Mapping[Node, int]], nodes: Iterable[Node]) -> dict[Node, frozenset[Node]]:
    index: dict[Node, int] = {}
    low: dict[Node, int] = {}
    stack: list[Node] = []
    on_stack: set[Node] = set()
    result: dict[Node, frozenset[Node]] = {}
    for root in nodes:
        if root in index:
            continue
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(edges.get(root, ())))]
        while work:
            node, neighbours = work[-1]
            for neighbour in neighbours:
                if neighbour not in index:
                    index[neighbour] = low[neighbour] = len(index)
                    stack.append(neighbour)
                    on_stack.add(neighbour)
                    work.append((neighbour, iter(edges.get(neighbour, ()))))
                    break
                if neighbour in on_stack:
                    low[node] = min(low[node], index[neighbour])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    members = []
                    while (member := stack.pop()) != node:
                        members.append(member)
                    members.append(node)
                    on_stack.difference_update(members)
                    result.update(dict.fromkeys(members, frozenset(members)))
    return result
