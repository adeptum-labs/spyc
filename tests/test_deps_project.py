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


NATIVE_FILES = {
    "go.mod": "module example.com/proj\n\ngo 1.22\n",
    "cmd/main.go": 'package main\nimport "example.com/proj/pkg"\nfunc main() { pkg.Run() }\n',
    "pkg/pkg.go": "package pkg\nfunc Run() {}\n", "pkg/other.go": "package pkg\nfunc Other() {}\n",
    "rust/Cargo.toml": '[package]\nname = "tool-kit"\n', "rust/tests/it.rs": "use tool_kit::util::Tool;\n",
    "rust/src/lib.rs": "mod util;\nuse crate::util::Tool;\nuse serde::Serialize;\n", "rust/src/util.rs": "pub struct Tool;\n",
    "c/main.c": '#include "util.h"\n#include <stdio.h>\nint main(){return 0;}\n', "c/util.h": "int f(void);\n",
}


def check_native(graph):
    assert not {"go.mod", "rust/Cargo.toml"} & {node.key for node in graph.nodes(FILE)}
    assert [link.node.key for link in graph.outgoing(Node(FILE, "rust/tests/it.rs"))] == ["rust/src/util.rs"]
    assert [link.node.key for link in graph.outgoing(Node(FILE, "cmd/main.go"))] == ["pkg/pkg.go"]
    assert [link.node.key for link in graph.outgoing(Node(UNIT, "cmd"))] == ["pkg"]
    assert [link.node.key for link in graph.outgoing(Node(FILE, "rust/src/lib.rs"))] == ["rust/src/util.rs"]
    assert graph.externals(Node(FILE, "rust/src/lib.rs")) == [("serde", 1)]
    assert [link.node.key for link in graph.outgoing(Node(FILE, "c/main.c"))] == ["c/util.h"]


def test_go_rust_and_c_files_go_from_the_source_through_the_index_and_its_cache_into_the_graph(tmp_path):
    write_files(tmp_path / "project", NATIVE_FILES)
    paths, cache = tuple(sorted(NATIVE_FILES)), tmp_path / "cache.json"
    first = SymbolIndex(tmp_path / "project", cache)
    first.update(paths)
    check_native(DependencyGraph(first.facts()))
    later = SymbolIndex(tmp_path / "project", cache)
    later.update(paths)
    check_native(DependencyGraph(later.facts()))
    assert {facts.language for facts in later.facts().values()} == {"gomod", "go", "cargo", "rust", "c"}


def test_a_test_module_that_uses_its_parent_makes_no_cycle_with_the_module_file(tmp_path):
    files = {"Cargo.toml": '[package]\nname = "t"\n', "src/lib.rs": "mod util;\n",
             "src/util.rs": "pub fn f() {}\n#[cfg(test)]\nmod tests { use super::*; use super::f; }\n"}
    write_files(tmp_path / "project", files)
    index = SymbolIndex(tmp_path / "project", tmp_path / "cache.json")
    index.update(tuple(sorted(files)))
    graph = DependencyGraph(index.facts())
    assert [link.node.key for link in graph.outgoing(Node(FILE, "src/lib.rs"))] == ["src/util.rs"]
    assert graph.outgoing(Node(FILE, "src/util.rs")) == [] and graph.cyclic_nodes(FILE) == []
