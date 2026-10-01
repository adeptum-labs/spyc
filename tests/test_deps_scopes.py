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


from spyc.deps.facts import ClassDef, FileFacts, Import
from spyc.deps.graph import FILE, UNIT, DependencyGraph, Node
from spyc.deps.scopes import DIRECTORY, PACKAGE, ROOT, Hierarchy, Member, label_of, title_of
from test_deps_graph import PYTHON_PROJECT


def java(unit, classes, imports=()):
    return FileFacts(unit, tuple(ClassDef(name, 1) for name in classes), tuple(imports), frozenset(), "java")


WEB = {
    "a/web/bind/Bind.java": java("org.web.bind", ["Bind"], [Import("org.web.util.Util"), Import("org.web.Web")]),
    "a/web/Web.java": java("org.web", ["Web"], [Import("org.web.util.Util")]),
    "a/web/util/Util.java": java("org.web.util", ["Util"]),
    "a/web/util/Other.java": java("org.web.util", ["Other"]),
    "a/web/ctx/sup/Sup.java": java("org.web.ctx.sup", ["Sup"], [Import("org.web.ctx.Ctx"), Import("org.web.util.Util")]),
    "a/web/ctx/Ctx.java": java("org.web.ctx", ["Ctx"], [Import("org.web.bind.Bind")]),
}
HIERARCHY = Hierarchy(DependencyGraph(WEB))
WEB_SCOPE = Member(PACKAGE, ("org", "web"))
BIND, CTX, UTIL = (Member(PACKAGE, ("org", "web", name)) for name in ("bind", "ctx", "util"))
OWN = Member(PACKAGE, ("org", "web"), own=True)


def labels(scope, members):
    return [label_of(member, scope) for member in members]


def test_a_scope_with_one_box_shows_what_that_box_shows():
    assert HIERARCHY.settle(ROOT) == WEB_SCOPE
    two = Hierarchy(DependencyGraph({"m/A.java": java("com.acme.a", ["A"]), "m/B.java": java("com.acme.b", ["B"])}))
    assert two.settle(ROOT) == Member(PACKAGE, ("com", "acme"))


def test_the_boxes_of_a_scope_are_its_next_names_and_its_own_files_as_one_box():
    assert labels(WEB_SCOPE, HIERARCHY.members(WEB_SCOPE)) == ["(files)", "bind", "ctx", "util"]
    assert HIERARCHY.members(CTX) == [Member(PACKAGE, ("org", "web", "ctx"), own=True), Member(PACKAGE, ("org", "web", "ctx", "sup"))]


def test_a_package_without_subpackages_and_the_own_box_show_their_files():
    files = [Member(FILE, (path,)) for path in ("a/web/util/Other.java", "a/web/util/Util.java")]
    assert HIERARCHY.members(UTIL) == files
    assert HIERARCHY.members(OWN) == [Member(FILE, ("a/web/Web.java",))]
    assert labels(UTIL, files) == ["Other.java", "Util.java"]


def test_edges_are_summed_between_rolled_up_boxes_and_dependencies_inside_a_box_vanish():
    edges = HIERARCHY.edges(WEB_SCOPE)
    named = {label_of(a, WEB_SCOPE): {label_of(b, WEB_SCOPE): w for b, w in targets.items()} for a, targets in edges.items()}
    assert named == {"(files)": {"util": 1}, "bind": {"(files)": 1, "util": 1}, "ctx": {"bind": 1, "util": 1}}


def test_the_edges_of_a_scope_of_files_are_the_file_edges_between_them():
    files = {"p/A.java": java("p", ["A"], [Import("p.B")]), "p/B.java": java("p", ["B"], [Import("p.A")]), "q/C.java": java("q", ["C"], [Import("p.A")])}
    hierarchy = Hierarchy(DependencyGraph(files))
    scope = Member(PACKAGE, ("p",))
    shown = hierarchy.members(scope)
    edges = hierarchy.edges(scope)
    assert [member.key for member in shown] == ["p/A.java", "p/B.java"]
    assert edges[shown[0]] == {shown[1]: 1} and edges[shown[1]] == {shown[0]: 1}
    assert set(hierarchy.cycles(edges, shown)) == set(shown)


def test_a_cycle_between_boxes_is_found_and_boxes_that_are_not_in_one_are_left_out():
    files = {"x/A.java": java("t.x", ["A"], [Import("t.y.B")]), "y/B.java": java("t.y", ["B"], [Import("t.x.A")]),
             "z/C.java": java("t.z", ["C"], [Import("t.x.A")])}
    hierarchy = Hierarchy(DependencyGraph(files))
    scope = hierarchy.settle(ROOT)
    shown = hierarchy.members(scope)
    cycles = hierarchy.cycles(hierarchy.edges(scope), shown)
    assert {member.key for member in cycles} == {"t.x", "t.y"}


def test_going_up_skips_the_scopes_that_would_show_the_same_boxes():
    assert HIERARCHY.parent(WEB_SCOPE) is None
    assert HIERARCHY.parent(CTX) == WEB_SCOPE and HIERARCHY.parent(UTIL) == WEB_SCOPE
    assert HIERARCHY.parent(OWN) == WEB_SCOPE
    assert HIERARCHY.parent(Member(PACKAGE, ("org", "web", "ctx", "sup"))) == CTX


def test_a_box_is_found_from_the_scope_that_was_left():
    assert HIERARCHY.containing(WEB_SCOPE, UTIL) == UTIL
    assert HIERARCHY.containing(WEB_SCOPE, Member(PACKAGE, ("org", "web", "ctx", "sup"))) == CTX
    assert HIERARCHY.containing(CTX, Member(PACKAGE, ("org", "web", "ctx", "sup"))) == Member(PACKAGE, ("org", "web", "ctx", "sup"))


def test_a_package_a_file_and_a_package_with_files_of_its_own_are_located_in_the_scope_that_shows_them():
    assert HIERARCHY.locate(Node(UNIT, "org.web.util")) == (WEB_SCOPE, UTIL)
    assert HIERARCHY.locate(Node(UNIT, "org.web")) == (WEB_SCOPE, OWN)
    util_file = Member(FILE, ("a/web/util/Util.java",))
    assert HIERARCHY.locate(Node(FILE, "a/web/util/Util.java")) == (UTIL, util_file)
    assert HIERARCHY.locate(Node(FILE, "a/web/Web.java")) == (OWN, Member(FILE, ("a/web/Web.java",)))
    assert HIERARCHY.locate(Node(FILE, "nowhere.txt"))[0] == WEB_SCOPE


def test_paths_and_externals_of_a_box_are_those_of_everything_rolled_up_in_it():
    files = {**WEB, "a/web/ctx/Ext.java": java("org.web.ctx", ["Ext"], [Import("com.google.Thing")])}
    hierarchy = Hierarchy(DependencyGraph(files))
    assert hierarchy.paths_of(CTX) == ["a/web/ctx/Ctx.java", "a/web/ctx/Ext.java", "a/web/ctx/sup/Sup.java"]
    assert hierarchy.externals(CTX) == [("com.google", 1)]
    assert hierarchy.paths_of(Member(FILE, ("a/web/Web.java",))) == ["a/web/Web.java"]


def test_directories_are_a_tree_too_and_the_files_of_the_top_directory_are_a_box_of_their_own():
    hierarchy = Hierarchy(DependencyGraph(PYTHON_PROJECT))
    scope = hierarchy.settle(ROOT)
    top, pkg = Member(DIRECTORY, (), own=True), Member(DIRECTORY, ("pkg",))
    assert scope == ROOT and hierarchy.members(scope) == [top, pkg]
    assert labels(scope, [top, pkg]) == ["(files)", "pkg"] and hierarchy.edges(scope) == {top: {pkg: 1}}
    assert hierarchy.locate(Node(FILE, "app.py")) == (top, Member(FILE, ("app.py",)))
    assert hierarchy.parent(pkg) == ROOT and hierarchy.externals(top) == [("requests", 1)]


def test_going_up_from_the_files_at_the_top_goes_to_the_root_and_not_to_a_root_of_one_kind():
    hierarchy = Hierarchy(DependencyGraph(PYTHON_PROJECT))
    assert hierarchy.parent(Member(DIRECTORY, (), own=True)) == ROOT
    mixed = Hierarchy(DependencyGraph({**PYTHON_PROJECT, "A.java": java("", ["A"]), "b/B.java": java("b", ["B"])}))
    assert mixed.parent(Member(PACKAGE, (), own=True)) == ROOT


def test_titles_name_the_scope_and_say_when_it_is_the_files_of_one():
    assert title_of(WEB_SCOPE, "proj") == "org.web" and title_of(ROOT, "proj") == "proj"
    assert title_of(OWN, "proj") == "org.web (files)"


def test_a_package_without_a_name_is_a_box_of_its_own_files():
    files = {"A.java": java("", ["A"]), "b/B.java": java("b", ["B"])}
    hierarchy = Hierarchy(DependencyGraph(files))
    assert hierarchy.members(hierarchy.settle(ROOT)) == [Member(PACKAGE, (), own=True), Member(PACKAGE, ("b",))]
