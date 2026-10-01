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


import time

from spyc.deps.facts import ClassDef, FileFacts, Import
from spyc.deps.graph import FILE, UNIT, DependencyGraph, Node


def facts(unit, classes, imports=(), used=()):
    return FileFacts(unit, tuple(ClassDef(name, 1) for name in classes), tuple(imports), frozenset(used))


ORDER, MODEL, BILLING = (Node(UNIT, name) for name in ("com.acme.order", "com.acme.model", "com.acme.billing"))
SERVICE = "src/main/java/com/acme/order/OrderService.java"
SAMPLE = {
    SERVICE: facts("com.acme.order", ["OrderService"],
                   [Import("com.acme.model.Order"), Import("com.acme.model", wildcard=True), Import("java.util.List"),
                    Import("org.slf4j.Logger")], ["Order", "Money", "Repo", "OrderService"]),
    "src/main/java/com/acme/model/Order.java": facts("com.acme.model", ["Order"], used=["Money"]),
    "src/main/java/com/acme/model/Money.java": facts("com.acme.model", ["Money"]),
    "src/main/java/com/acme/order/Repo.java": facts("com.acme.order", ["Repo"], [Import("com.acme.billing.Invoice")]),
    "src/main/java/com/acme/billing/Invoice.java": facts("com.acme.billing", ["Invoice"],
                                                       [Import("com.acme.order.OrderService")]),
    "src/test/java/com/acme/order/OrderServiceTest.java": facts(
        "com.acme.order", ["OrderServiceTest"], [Import("org.junit.Test"), Import("org.junit.Assert", wildcard=True, static=True)],
        ["OrderService"]),
}


def names(links):
    return [(link.node.name.rsplit("/", 1)[-1], link.weight) for link in links]


def test_units_depend_on_units_and_a_wildcard_import_gives_class_edges_only_for_names_that_are_used():
    graph = DependencyGraph(SAMPLE)
    assert names(graph.outgoing(ORDER)) == [("com.acme.model", 2), ("com.acme.billing", 1)]
    assert names(graph.incoming(ORDER)) == [("com.acme.billing", 1)]
    assert names(graph.outgoing(MODEL)) == [] and names(graph.incoming(MODEL)) == [("com.acme.order", 2)]


def test_files_depend_on_the_ones_they_import_or_use_from_their_package():
    graph = DependencyGraph(SAMPLE)
    assert names(graph.outgoing(Node(FILE, SERVICE))) == [("Money.java", 1), ("Order.java", 1), ("Repo.java", 1)]


def test_a_class_used_from_the_same_package_is_a_dependency_without_an_import():
    graph = DependencyGraph(SAMPLE)
    test = Node(FILE, "src/test/java/com/acme/order/OrderServiceTest.java")
    assert names(graph.outgoing(test)) == [("OrderService.java", 1)]
    assert graph.outgoing(ORDER)[0].node != ORDER


def test_what_is_not_in_the_project_is_counted_on_the_file_and_on_its_unit_and_never_drawn():
    graph = DependencyGraph(SAMPLE)
    assert graph.externals(Node(FILE, SERVICE)) == [("java.util", 1), ("org.slf4j", 1)]
    assert graph.externals(ORDER) == [("org.junit", 2), ("java.util", 1), ("org.slf4j", 1)]
    assert all(link.node.level == UNIT for link in graph.outgoing(ORDER))


def test_a_cycle_between_packages_and_the_files_in_it_are_found_and_the_rest_is_not_in_one():
    graph = DependencyGraph(SAMPLE)
    assert graph.cycle_members(ORDER) == {BILLING} and graph.cycle_members(MODEL) == frozenset()
    assert [node.name for node in graph.cyclic_nodes(UNIT)] == ["com.acme.billing", "com.acme.order"]
    assert {node.name.rsplit("/", 1)[-1] for node in graph.cyclic_nodes(FILE)} == {"Invoice.java", "OrderService.java", "Repo.java"}


def test_a_class_that_imports_itself_or_a_member_of_itself_has_no_edge_to_itself():
    files = {"A.java": facts("p", ["A"], [Import("p.A"), Import("p.A.helper", static=True)], ["A"])}
    graph = DependencyGraph(files)
    assert graph.outgoing(Node(FILE, "A.java")) == [] and graph.outgoing(Node(UNIT, "p")) == []
    assert graph.cycle_members(Node(FILE, "A.java")) == frozenset()


def test_a_nested_class_and_a_static_member_resolve_to_the_class_that_holds_them():
    files = {"m/Order.java": facts("com.acme.model", ["Order"]),
             "u/User.java": facts("com.acme.use", ["User"], [Import("com.acme.model.Order.Line"),
                                                             Import("com.acme.model.Order.create", static=True)])}
    graph = DependencyGraph(files)
    assert names(graph.outgoing(Node(FILE, "u/User.java"))) == [("Order.java", 1)]


def test_a_package_reached_without_naming_a_class_is_a_unit_edge_only():
    files = {"u/Helpers.kt": facts("com.acme.util", ["Helpers"]),
             "a/App.kt": facts("com.acme.app", ["App"], [Import("com.acme.util.helper"), Import("com.acme.util", wildcard=True)])}
    graph = DependencyGraph(files)
    assert names(graph.outgoing(Node(UNIT, "com.acme.app"))) == [("com.acme.util", 1)]
    assert graph.outgoing(Node(FILE, "a/App.kt")) == []


def test_files_without_a_package_share_the_default_unit_and_still_depend_on_each_other():
    files = {"m/Main.java": facts("", ["Main"], used=["Helper"]), "m/Helper.java": facts("", ["Helper"], [Import("Helper")])}
    graph = DependencyGraph(files)
    assert Node(UNIT, "").name == "(default)"
    assert names(graph.outgoing(Node(FILE, "m/Main.java"))) == [("Helper.java", 1)]
    assert graph.outgoing(Node(UNIT, "")) == []


def test_two_files_that_define_the_same_class_do_not_break_the_graph_and_the_first_path_wins():
    files = {"main/A.java": facts("p", ["A"]), "test/A.java": facts("p", ["A"]), "x/B.java": facts("q", ["B"], [Import("p.A")])}
    assert names(DependencyGraph(files).outgoing(Node(FILE, "x/B.java"))) == [("A.java", 1)]
    assert DependencyGraph(files).paths_of(Node(FILE, "x/B.java")) == ["x/B.java"]


def test_the_shape_of_the_project_can_be_walked_up_and_down():
    graph = DependencyGraph(SAMPLE)
    assert [child.key.rsplit("/", 1)[-1] for child in graph.children(ORDER)] == [
        "OrderService.java", "Repo.java", "OrderServiceTest.java"]
    service = Node(FILE, SERVICE)
    assert graph.parent(service) == ORDER and graph.parent(ORDER) is None
    assert graph.children(service) == [] and graph.unit_of(SERVICE) == ORDER and graph.unit_of("nope") is None
    assert graph.paths_of(service) == [SERVICE] and len(graph.paths_of(ORDER)) == 3
    assert graph.has(ORDER) and graph.has(service) and not graph.has(Node(UNIT, "nope"))


def test_the_most_connected_node_wins_and_ties_go_to_the_name():
    graph = DependencyGraph(SAMPLE)
    assert graph.most_connected(graph.nodes(UNIT)) == ORDER and graph.most_connected([]) is None
    assert graph.degree(MODEL) == 2 and DependencyGraph({}).empty and not graph.empty


def test_thousands_of_packages_that_share_a_class_name_build_quickly_and_form_one_ring():
    files = {f"p{index}/Index.java": facts(f"p{index}", ["Index"], [Import(f"p{(index + 1) % 3000}.Index")])
             for index in range(3000)}
    started = time.perf_counter()
    graph = DependencyGraph(files)
    assert len(graph.cycle_members(Node(FILE, "p0/Index.java"))) == 2999
    assert time.perf_counter() - started < 3


def test_a_chain_of_thousands_of_files_does_not_overflow_the_stack_finding_cycles():
    files = {f"p/C{index}.java": facts("p", [f"C{index}"], [Import(f"p.C{index + 1}")]) for index in range(5000)}
    started = time.perf_counter()
    assert DependencyGraph(files).cycle_members(Node(FILE, "p/C0.java")) == frozenset()
    assert time.perf_counter() - started < 3


def test_finding_the_nodes_of_a_cycle_of_thousands_of_files_is_fast():
    files = {f"p/C{index}.java": facts("p", [f"C{index}"], [Import(f"p.C{(index + 1) % 12000}")]) for index in range(12000)}
    graph = DependencyGraph(files)
    started = time.perf_counter()
    assert len(graph.cyclic_nodes(FILE)) == 12000
    assert time.perf_counter() - started < 2


def test_two_files_that_declare_the_same_class_have_no_edge_between_the_copies():
    files = {"m1/Foo.java": facts("com.acme", ["Foo"]), "m2/Foo.java": facts("com.acme", ["Foo"], [Import("com.acme.Foo")], ["Foo"])}
    graph = DependencyGraph(files)
    assert graph.outgoing(Node(FILE, "m2/Foo.java")) == []
    assert graph.outgoing(Node(UNIT, "com.acme")) == []


def test_a_build_that_is_asked_to_stop_stops():
    import pytest
    from spyc.deps.graph import Stopped
    files = {f"p/C{index}.java": facts("p", [f"C{index}"]) for index in range(1000)}
    with pytest.raises(Stopped):
        DependencyGraph(files, stop=lambda: True)
    assert not DependencyGraph(files, stop=lambda: False).empty


def python(imports=(), classes=()):
    return FileFacts("", tuple(ClassDef(name, 1) for name in classes), tuple(imports), frozenset(), "python")


def script(imports=(), language="typescript"):
    return FileFacts("", (), tuple(Import(path) for path in imports), frozenset(), language)


PYTHON_PROJECT = {
    "app.py": python([Import("pkg.mod"), Import("requests.adapters"), Import("os")]),
    "pkg/__init__.py": python(),
    "pkg/mod.py": python([Import("", level=1, names=("helper",))]),
    "pkg/helper.py": python([Import("pkg.mod")]),
}


def test_python_files_depend_on_the_files_they_import_and_their_directories_are_the_units():
    graph = DependencyGraph(PYTHON_PROJECT)
    root, pkg = Node(UNIT, "."), Node(UNIT, "pkg")
    assert [node.key for node in graph.nodes(UNIT)] == [".", "pkg"]
    assert names(graph.outgoing(root)) == [("pkg", 1)] and names(graph.incoming(pkg)) == [(".", 1)]
    assert names(graph.outgoing(Node(FILE, "app.py"))) == [("mod.py", 1)]
    assert graph.externals(Node(FILE, "app.py")) == [("requests", 1)] and graph.externals(root) == [("requests", 1)]


def test_python_cycles_between_files_are_found_and_the_directory_has_none_with_itself():
    graph = DependencyGraph(PYTHON_PROJECT)
    mod = Node(FILE, "pkg/mod.py")
    assert graph.cycle_members(mod) == {Node(FILE, "pkg/helper.py")} and graph.cycle_members(Node(UNIT, "pkg")) == frozenset()
    assert graph.outgoing(Node(UNIT, "pkg")) == []


def test_the_file_is_the_lowest_level_and_python_nodes_are_called_directories():
    graph = DependencyGraph(PYTHON_PROJECT)
    assert graph.children(Node(FILE, "app.py")) == []
    assert [graph.kind_of(node) for node in (Node(UNIT, "pkg"), Node(FILE, "app.py"))] == ["directory", "file"]


def test_script_files_depend_on_the_files_they_name_and_json_and_style_sheets_are_no_nodes():
    files = {"web/app.ts": script(["./util", "react", "./data.json", "./style.css"]), "web/util.ts": script(["@scope/pkg/x"]),
             "web/old.js": script(["./util.js"], "javascript")}
    graph = DependencyGraph(files)
    assert names(graph.outgoing(Node(FILE, "web/app.ts"))) == [("util.ts", 1)]
    assert names(graph.incoming(Node(FILE, "web/util.ts"))) == [("app.ts", 1), ("old.js", 1)]
    assert graph.externals(Node(UNIT, "web")) == [("@scope/pkg", 1), ("react", 1)]
    assert graph.outgoing(Node(UNIT, "web")) == []


def test_a_project_of_several_languages_has_package_units_and_directory_units_side_by_side():
    tools = {"tools/a.py": python([Import("b")]), "tools/b.py": python()}
    graph = DependencyGraph({**SAMPLE, **tools, "main.py": python([Import("tools.a")])})
    assert graph.kind_of(ORDER) == "package" and graph.kind_of(Node(UNIT, "tools")) == "directory"
    assert names(graph.outgoing(Node(UNIT, "."))) == [("tools", 1)] and names(graph.outgoing(ORDER))[0] == ("com.acme.model", 2)
    assert graph.outgoing(Node(FILE, "main.py"))[0].node == Node(FILE, "tools/a.py")


def test_a_python_file_that_imports_itself_or_a_module_it_shadows_has_no_edge_to_itself():
    files = {"a.py": python([Import("a"), Import("", level=1, names=("a",))])}
    assert DependencyGraph(files).outgoing(Node(FILE, "a.py")) == []


def test_files_with_control_characters_in_their_directory_names_are_nodes_like_any_other():
    graph = DependencyGraph({"d\x1b[2J/a.py": python([Import("b")]), "d\x1b[2J/b.py": python()})
    assert names(graph.outgoing(Node(FILE, "d\x1b[2J/a.py"))) == [("b.py", 1)]


def test_thousands_of_python_files_and_a_file_with_thousands_of_imports_build_quickly():
    files = {f"p{index // 50}/m{index}.py": python([Import(f"m{(index + 1) % 3000}")]) for index in range(3000)}
    files["big.py"] = python([Import(f"m{index}") for index in range(5000)])
    started = time.perf_counter()
    graph = DependencyGraph(files)
    assert len(graph.outgoing(Node(FILE, "big.py"))) == 3000 and time.perf_counter() - started < 5


def go_file(imports=(), defines=(), language="go"):
    return FileFacts("", (), tuple(imports), frozenset(), language, frozenset(defines))


GO_PROJECT = {
    "go.mod": go_file([Import("example.com/proj")], language="gomod"),
    "cmd/app/main.go": go_file([Import("example.com/proj/pkg/api", names=("Handle",)), Import("example.com/proj/pkg/store"),
                                Import("fmt"), Import("github.com/spf13/cobra")], ["main"]),
    "pkg/api/handler.go": go_file([Import("example.com/proj/pkg/store", names=("Open",))], ["Handle"]),
    "pkg/store/store.go": go_file([], ["Open"]),
}


def test_go_files_reach_the_files_that_define_what_they_use_and_the_directories_of_the_packages_they_import():
    graph = DependencyGraph(GO_PROJECT)
    assert "go.mod" not in [node.key for node in graph.nodes(FILE)]
    assert names(graph.outgoing(Node(FILE, "cmd/app/main.go"))) == [("handler.go", 1)]
    assert [(link.node.key, link.weight) for link in graph.outgoing(Node(UNIT, "cmd/app"))] == [("pkg/api", 1), ("pkg/store", 1)]
    assert names(graph.outgoing(Node(FILE, "pkg/api/handler.go"))) == [("store.go", 1)]
    assert graph.externals(Node(FILE, "cmd/app/main.go")) == [("github.com/spf13/cobra", 1)]
    assert graph.kind_of(Node(UNIT, "pkg/api")) == "directory"


def test_a_project_of_only_a_module_file_has_no_graph_and_a_language_without_a_handler_gives_no_edges():
    assert DependencyGraph({"go.mod": go_file([Import("x")], language="gomod")}).empty
    graph = DependencyGraph({"a.zig": FileFacts("", (), (Import("b"),), frozenset(), "zig"), "b.zig": FileFacts(language="zig")})
    assert graph.outgoing(Node(FILE, "a.zig")) == [] and graph.externals(Node(FILE, "a.zig")) == []


def test_a_go_package_in_the_root_directory_is_the_dot_unit_and_a_package_never_depends_on_itself():
    files = {"go.mod": go_file([Import("x.io/m")], language="gomod"), "main.go": go_file([Import("x.io/m/lib")], ["main"]),
             "lib/lib.go": go_file([Import("x.io/m/lib"), Import("x.io/m")], ["Lib"])}
    graph = DependencyGraph(files)
    assert names(graph.outgoing(Node(UNIT, "."))) == [("lib", 1)] and names(graph.outgoing(Node(UNIT, "lib"))) == [(".", 1)]
    assert graph.cycle_members(Node(UNIT, ".")) == {Node(UNIT, "lib")}


def rust_file(imports=()):
    return FileFacts("", (), tuple(Import(path) for path in imports), frozenset(), "rust")


def test_rust_files_depend_on_the_module_files_their_use_and_mod_lines_name_and_serde_is_external():
    files = {"Cargo.toml": FileFacts(language="cargo", imports=(Import("app"),)),
             "src/lib.rs": rust_file(["self::a", "self::c", "serde::Serialize", "std::io"]),
             "src/a/mod.rs": rust_file(["self::b"]), "src/a/b.rs": rust_file(["crate::c::Thing", "super::super::c"]),
             "src/c.rs": rust_file()}
    graph = DependencyGraph(files)
    assert names(graph.outgoing(Node(FILE, "src/lib.rs"))) == [("mod.rs", 1), ("c.rs", 1)]
    assert names(graph.outgoing(Node(FILE, "src/a/b.rs"))) == [("c.rs", 1)]
    assert graph.externals(Node(FILE, "src/lib.rs")) == [("serde", 1)]
    assert names(graph.outgoing(Node(UNIT, "src/a"))) == [("src", 1)]
    assert "Cargo.toml" not in [node.key for node in graph.nodes(FILE)]


def test_a_project_of_only_manifests_has_no_graph():
    files = {"go.mod": go_file([Import("x")], language="gomod"), "Cargo.toml": FileFacts(language="cargo", imports=(Import("y"),))}
    assert DependencyGraph(files).empty


def c_file(includes=(), language="c"):
    return FileFacts("", (), tuple(Import(text) for text in includes), frozenset(), language)


def test_c_files_depend_on_the_headers_they_include_and_a_library_header_is_external():
    files = {"app/main.c": c_file(['"local.h"', "<stdio.h>", "<boost/asio.hpp>", '"lib/z.h"']), "app/local.h": c_file(),
             "include/lib/z.h": c_file(['"../util.h"']), "include/util.h": c_file(),
             "src/a.cpp": c_file(['"a.hpp"'], "cpp"), "src/a.hpp": c_file(language="cpp")}
    graph = DependencyGraph(files)
    assert names(graph.outgoing(Node(FILE, "app/main.c"))) == [("local.h", 1), ("z.h", 1)]
    assert names(graph.outgoing(Node(FILE, "include/lib/z.h"))) == [("util.h", 1)]
    assert names(graph.outgoing(Node(FILE, "src/a.cpp"))) == [("a.hpp", 1)]
    assert graph.externals(Node(FILE, "app/main.c")) == [("boost", 1)]
    assert [(link.node.key, link.weight) for link in graph.outgoing(Node(UNIT, "app"))] == [("include/lib", 1)]
    assert graph.kind_of(Node(UNIT, "app")) == "directory"


def test_go_test_files_draw_file_edges_but_no_directory_edges_so_an_external_test_package_makes_no_cycle():
    files = {"go.mod": go_file([Import("x.io/m")], language="gomod"),
             "foo/foo.go": go_file([], ["Foo"]),
             "foo/foo_test.go": go_file([Import("x.io/m/testutil", names=("New",)), Import("github.com/stretchr/testify/assert")]),
             "testutil/util.go": go_file([Import("x.io/m/foo", names=("Foo",))], ["New"])}
    graph = DependencyGraph(files)
    assert names(graph.outgoing(Node(FILE, "foo/foo_test.go"))) == [("util.go", 1)]
    assert graph.outgoing(Node(UNIT, "foo")) == [] and graph.cyclic_nodes(UNIT) == []
    assert graph.externals(Node(FILE, "foo/foo_test.go")) == [("github.com/stretchr/testify", 1)]
    assert graph.externals(Node(UNIT, "foo")) == []
    assert [link.node.key for link in graph.incoming(Node(UNIT, "foo"))] == ["testutil"]
