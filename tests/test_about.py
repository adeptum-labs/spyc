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


import pytest

from repos import write_files
from spyc.about import MAX_FACTS, About
from spyc.assist.targets import Target
from spyc.core.document import load_document
from spyc.core.file_index import build_index
from spyc.deps.graph import FILE, UNIT, DependencyGraph, Node
from spyc.symbol_index import SymbolIndex

FILES = {
    "src/a/A.java": "package com.acme.a;\nimport com.acme.b.B;\npublic class A {\n  class Inner {\n    void m() {}\n  }\n}\n",
    "src/b/B.java": "package com.acme.b;\nimport com.acme.a.A;\npublic class B { A a; }\n",
    "tools/one.py": "import two\n\nclass Tool:\n    def run(self):\n        pass\n\ndef helper():\n    pass\n",
    "tools/two.py": "x = 1\n",
    "tools/sub/three.py": "y = 2\n",
    "README.md": "# Project\n",
}


@pytest.fixture
def about(tmp_path):
    root = tmp_path / "proj"
    write_files(root, FILES)
    paths = build_index(root, False, 1000).paths
    symbols = SymbolIndex(root, None)
    symbols.update(paths)
    graph = DependencyGraph(symbols.facts())
    return About(symbols, lambda: paths, lambda: graph), root


def test_a_directory_holds_the_files_below_it(about):
    target = about[0].directory("tools")
    assert target == Target("directory", "tools", "tools", ("tools/one.py", "tools/sub/three.py", "tools/two.py"))


def test_the_root_is_a_directory_of_all_the_files(about):
    target = about[0].directory("")
    assert target.key == "." and "README.md" in target.paths and "src/a/A.java" in target.paths


def test_a_directory_named_like_the_start_of_another_does_not_take_its_files(about):
    assert about[0].directory("src/a").paths == ("src/a/A.java",)
    assert about[0].directory("tool").paths == ()


def test_a_directory_before_the_files_are_known_is_empty():
    assert About(SymbolIndex(None, None), lambda: None, lambda: None).directory("x").paths == ()


def test_the_scopes_of_a_line_in_a_class_are_the_class_the_file_and_the_package(about):
    about, root = about
    scopes = about.scopes("src/a/A.java", load_document(root / "src/a/A.java"), 4)
    assert [(scope.kind, scope.label) for scope in scopes] == [("class", "Inner"), ("file", "src/a/A.java"), ("package", "com.acme.a")]
    assert scopes[0].line == 4 and scopes[2].paths == ("src/a/A.java",)


def test_the_scopes_of_a_line_outside_a_class_are_the_file_and_the_directory(about):
    about, root = about
    scopes = about.scopes("tools/one.py", load_document(root / "tools/one.py"), 6)
    assert [(scope.kind, scope.label) for scope in scopes] == [("file", "tools/one.py"), ("directory", "tools")]


def test_the_scopes_before_the_graph_is_ready_name_the_directory(tmp_path):
    root = tmp_path / "proj"
    write_files(root, FILES)
    about = About(SymbolIndex(root, None), lambda: build_index(root, False, 1000).paths, lambda: None)
    scopes = about.scopes("src/a/A.java", load_document(root / "src/a/A.java"), 0)
    assert [(scope.kind, scope.label) for scope in scopes[-1:]] == [("directory", "src/a")]


def test_a_file_without_a_class_around_the_cursor_is_not_searched_when_it_is_plain(about):
    about, root = about
    document = load_document(root / "README.md")
    assert [scope.kind for scope in about.scopes("README.md", document, 0)] == ["file", "directory"]


def test_nodes_of_the_graph_become_targets(about):
    about = about[0]
    assert about.node(Node(UNIT, "com.acme.a")) == Target("package", "com.acme.a", "com.acme.a", ("src/a/A.java",))
    assert about.node(Node(UNIT, "tools")).kind == "directory" and about.node(Node(UNIT, "tools")) == about.directory("tools")
    assert about.node(Node(FILE, "tools/one.py")) == Target("file", "tools/one.py", "tools/one.py", ("tools/one.py",))


def test_a_member_of_the_diagram_becomes_a_target(about):
    about = about[0]
    assert about.member("package", "com.acme.a", ["src/a/A.java"]) == Target("package", "com.acme.a", "com.acme.a", ("src/a/A.java",))
    assert about.member("directory", "tools", []) == about.directory("tools")
    assert about.member("file", "tools/one.py", []) == about.file("tools/one.py")
    assert about.member("package", "", ["A.java"]).label == "(default)"


def test_a_node_the_graph_does_not_have_is_no_target(about):
    assert about[0].node(Node(UNIT, "nowhere")) is None


def test_the_facts_of_a_package_come_from_the_graph_and_the_symbols(about):
    about = about[0]
    facts = about.facts_of(about.node(Node(UNIT, "com.acme.a")))
    assert facts.depends_on == ("com.acme.b ×1",) and facts.used_by == ("com.acme.b ×1",) and facts.cycles == ("com.acme.b",)
    assert any(line.startswith("class A (src/a/A.java:3)") for line in facts.definitions)


def test_the_facts_of_a_file_and_a_class_name_what_they_define(about):
    about = about[0]
    file_facts = about.facts_of(about.file("tools/one.py"))
    assert file_facts.depends_on == ("tools/two.py ×1",)
    assert {"class Tool (tools/one.py:3)", "function helper (tools/one.py:7)"} <= set(file_facts.definitions)
    class_facts = about.facts_of(about.class_named("tools/one.py", "Tool", 3))
    assert "function helper (tools/one.py:7)" in class_facts.definitions


def test_a_directory_is_told_by_its_classes_only(about):
    facts = about[0].facts_of(about[0].directory("tools"))
    assert "class Tool (tools/one.py:3)" in facts.definitions and not any("helper" in line for line in facts.definitions)


def test_without_a_graph_only_the_definitions_are_known(tmp_path):
    root = tmp_path / "proj"
    write_files(root, FILES)
    symbols = SymbolIndex(root, None)
    symbols.update(("tools/one.py",))
    about = About(symbols, lambda: ("tools/one.py",), lambda: None)
    facts = about.facts_of(about.file("tools/one.py"))
    assert facts.depends_on == () and "class Tool (tools/one.py:3)" in facts.definitions


def test_a_hub_lists_only_the_strongest_links(tmp_path):
    root = tmp_path / "proj"
    files = {"hub.py": "".join(f"import m{number}\n" for number in range(MAX_FACTS + 5))} | {f"m{number}.py": "" for number in range(MAX_FACTS + 5)}
    write_files(root, files)
    paths = build_index(root, False, 1000).paths
    symbols = SymbolIndex(root, None)
    symbols.update(paths)
    graph = DependencyGraph(symbols.facts())
    about = About(symbols, lambda: paths, lambda: graph)
    assert len(about.facts_of(about.file("hub.py")).depends_on) == MAX_FACTS
