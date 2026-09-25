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


from repos import write_files
from spyc.deps.graph import FILE, UNIT, DependencyGraph, Node
from spyc.symbol_index import SymbolIndex

FILES = {
    "app/__init__.py": "", "app/main.py": "from app import util\nimport requests\n", "app/util.py": "import os\n",
    "web/index.ts": "import { lib } from './lib';\nimport React from 'react';\n", "web/lib.ts": "export const lib = 1;\n",
    "src/a/A.java": "package com.acme.a;\nimport com.acme.b.B;\nclass A {}\n",
    "src/b/B.java": "package com.acme.b;\nclass B {}\n",
}


def check(graph):
    assert [graph.kind_of(Node(UNIT, key)) for key in ("app", "web", "com.acme.a")] == ["directory", "directory", "package"]
    assert [link.node.key for link in graph.outgoing(Node(FILE, "app/main.py"))] == ["app/util.py"]
    assert [link.node.key for link in graph.outgoing(Node(FILE, "web/index.ts"))] == ["web/lib.ts"]
    assert [link.node.key for link in graph.outgoing(Node(UNIT, "com.acme.a"))] == ["com.acme.b"]
    assert graph.externals(Node(UNIT, "app")) == [("requests", 1)] and graph.externals(Node(UNIT, "web")) == [("react", 1)]


def test_files_of_three_languages_go_from_the_source_through_the_index_and_its_cache_into_the_graph(tmp_path):
    write_files(tmp_path / "project", FILES)
    paths, cache = tuple(sorted(FILES)), tmp_path / "cache.json"
    first = SymbolIndex(tmp_path / "project", cache)
    first.update(paths)
    check(DependencyGraph(first.facts()))
    later = SymbolIndex(tmp_path / "project", cache)
    later.update(paths)
    check(DependencyGraph(later.facts()))
    assert {facts.language for facts in later.facts().values()} == {"python", "typescript", "java"}
