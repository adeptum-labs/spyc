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


from spyc.core.printable import printable
from spyc.deps.facts import ClassDef, FileFacts, Import
from spyc.deps.graph import CLASS, UNIT, DependencyGraph, Node
from spyc.deps.render import Entry, entries_of, focus_layout, header_text, stacked_layout

LEFT = [Entry("web.api", 3), Entry("web.admin", 1)]
RIGHT = [Entry("core.model", 2), Entry("core.util", 5), Entry("core.billing", 1, True)]


def plain(layout):
    return [line.plain for line in layout.lines]


def test_the_neighbours_are_joined_to_the_selected_node_by_bars_with_weights_and_a_cycle_mark():
    assert plain(focus_layout("com.acme.order", LEFT, RIGHT, 100)) == [
        "web.api     ×3──┐                   ┌─▶ core.model       ×2",
        "web.admin   ×1──┴─▶ com.acme.order ─┼─▶ core.util        ×5",
        "                                    └─▶ core.billing ⟲   ×1"]


def test_the_places_of_the_labels_are_known_for_clicks_and_the_selected_one_is_reversed():
    layout = focus_layout("com.acme.order", LEFT, RIGHT, 100, ("out", 1))
    assert [(place.side, place.index, place.row, place.start, place.end) for place in layout.places] == [
        ("in", 0, 0, 0, 9), ("out", 0, 0, 40, 54), ("in", 1, 1, 0, 9), ("out", 1, 1, 40, 54), ("out", 2, 2, 40, 54)]
    assert [(span.start, span.end) for span in layout.lines[1].spans if span.style == "reverse"] == [(40, 54)]


def test_a_side_without_neighbours_has_no_arrow_and_one_neighbour_sits_beside_the_node():
    assert plain(focus_layout("solo", [], [], 60)) == ["    solo   "]
    assert plain(focus_layout("x", [Entry("a", 1)], [], 60)) == ["a   ×1────▶ x   "]
    assert plain(focus_layout("x", [], [Entry("b", 2)], 60)) == ["    x ───▶ b   ×2"]


def test_long_names_lose_their_start_so_that_the_line_fits_and_the_end_that_tells_them_apart_stays():
    line = plain(focus_layout("com.acme.order", [Entry("a.very.long.package.name.here", 1)],
                              [Entry("another.very.long.package.name.too", 1)], 60))[0]
    assert line == "…name.here   ×1────▶ com.acme.order ───▶ ….name.too   ×1"


def test_a_cut_name_keeps_the_cycle_mark_and_a_column_too_narrow_for_a_name_shows_only_the_mark():
    line = plain(focus_layout("x", [Entry("com.adeptum.docunord.security.mechanism", 1, True)], [], 100))[0]
    assert line.startswith("…eptum.docunord.security.mechanism ⟲")
    assert plain(stacked_layout("x", [Entry("abc", 1, True)], [], 7))[1] == "   ⟲   ×1"


def test_on_a_narrow_terminal_the_three_groups_are_stacked():
    layout = stacked_layout("com.acme.order", LEFT, RIGHT, 40, ("in", 0))
    assert plain(layout) == ["used by (2)", "  web.api     ×3", "  web.admin   ×1", "com.acme.order", "depends on (3)",
                             "  core.model       ×2", "  core.util        ×5", "  core.billing ⟲   ×1"]
    assert [(place.side, place.index, place.row, place.start, place.end) for place in layout.places][:3] == [
        ("in", 0, 1, 2, 11), ("in", 1, 2, 2, 11), ("out", 0, 5, 2, 16)]
    assert [(span.start, span.end) for span in layout.lines[1].spans if span.style == "reverse"] == [(2, 11)]


def facts(unit, classes, imports=(), used=()):
    return FileFacts(unit, tuple(ClassDef(name, 1) for name in classes), tuple(imports), frozenset(used))


GRAPH = DependencyGraph({
    "a/Service.java": facts("com.acme.order", ["Service"], [Import("com.acme.model.Order"), Import("java.util.List"),
                                                          Import("org.slf4j.Logger"), Import("org.junit.X"), Import("com.google.Y")],
                            ["Repo"]),
    "a/Order.java": facts("com.acme.model", ["Order"]),
    "a/Repo.java": facts("com.acme.order", ["Repo"], [Import("com.acme.billing.Invoice")]),
    "a/Invoice.java": facts("com.acme.billing", ["Invoice"], [Import("com.acme.order.Service")])})
ORDER = Node(UNIT, "com.acme.order")


def test_the_header_names_the_node_its_counts_its_externals_and_its_cycle():
    assert header_text(GRAPH, ORDER, printable).plain == (
        "package com.acme.order · 2 out · 1 in · 4 external (com.google, java.util, org.junit, ...) · ⟲ cycle with 1")
    assert header_text(GRAPH, Node(UNIT, "com.acme.model"), printable).plain == "package com.acme.model · 0 out · 1 in"
    assert header_text(GRAPH, Node(CLASS, "com.acme.order.Repo"), printable).plain == (
        "class com.acme.order.Repo · 1 out · 1 in · ⟲ cycle with 2")


def test_entries_carry_the_weight_and_mark_the_members_of_a_cycle_with_the_node():
    entries = entries_of(GRAPH, ORDER, GRAPH.outgoing(ORDER), printable)
    assert entries == [Entry("com.acme.billing", 1, True), Entry("com.acme.model", 1, False)]


def test_control_characters_in_names_never_reach_the_layout():
    graph = DependencyGraph({"a/A.java": facts("p\x1b[2J", ["A"], [Import("q\x1b]0;x\x07.B")]),
                             "b/B.java": facts("q\x1b]0;x\x07", ["B"])})
    node = Node(UNIT, "p\x1b[2J")
    layout = focus_layout(printable(node.name), [], entries_of(graph, node, graph.outgoing(node), printable), 100)
    assert all("\x1b" not in line.plain and "\x07" not in line.plain for line in layout.lines)
    assert "\x1b" not in header_text(graph, node, printable).plain


def test_a_long_selected_name_does_not_take_the_room_of_the_neighbours():
    centre = "src/main/java/com/adeptum/docunord/model/service/UserService.java"
    neighbour = "src/main/java/com/adeptum/docunord/view/BillingCheckoutBean.java"
    layout = focus_layout(centre, [Entry(neighbour, 1)], [Entry(neighbour, 1)], 100)
    assert all(place.end - place.start >= 15 for place in layout.places)
    assert len(layout.lines[0].plain) <= 100


def test_the_header_calls_a_directory_a_directory():
    graph = DependencyGraph({"app.py": FileFacts("", (), (Import("pkg.mod"),), frozenset(), "python"),
                             "pkg/mod.py": FileFacts("", (), (), frozenset(), "python")})
    assert header_text(graph, Node(UNIT, "pkg"), printable).plain == "directory pkg · 0 out · 1 in"
    assert header_text(graph, Node(UNIT, "."), printable).plain == "directory . · 1 out · 0 in"
