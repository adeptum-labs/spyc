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


from spyc.deps.diagram import DENSE_BOXES, following, neighbour, paint, status_text
from spyc.deps.layout import layout

NODES = ["top", "left", "right", "low"]
EDGES = {"top": {"left": 1, "right": 2}, "left": {"low": 3}, "right": {"low": 4}}
DRAWING = layout(NODES, EDGES, {}, {node: node for node in NODES}, "t")


def styles(drawing, selected):
    return {str(span.style) for line in paint(drawing, selected) for span in line.spans}


def test_painting_keeps_the_text_of_the_drawing():
    assert [line.plain for line in paint(DRAWING, "top")] == ["".join(cell.char for cell in row) for row in DRAWING.rows]


def test_the_selected_box_is_reversed_and_its_wires_stand_out_while_the_others_are_dim():
    assert {"reverse bold", "bold cyan", "dim"} <= styles(DRAWING, "left")


def test_nothing_is_dimmed_without_a_selection_or_when_the_selection_has_no_wires():
    assert "dim" not in styles(DRAWING, None)
    lone = layout(["a", "b", "c"], {"a": {"b": 1}}, {}, {n: n for n in "abc"}, "t")
    assert "dim" not in styles(lone, "c") and "reverse bold" in styles(lone, "c")


def test_the_wires_of_a_cycle_are_yellow():
    group = frozenset("ab")
    drawing = layout(["a", "b"], {"a": {"b": 1}, "b": {"a": 1}}, {"a": group, "b": group}, {n: n for n in "ab"}, "t")
    assert "yellow" in styles(drawing, None) and "bold yellow" in styles(drawing, "a")


def test_the_arrows_move_to_the_nearest_box_in_that_direction():
    assert neighbour(DRAWING.boxes, "top", 1, 0) in {"left", "right"}
    assert neighbour(DRAWING.boxes, "left", -1, 0) == "top" and neighbour(DRAWING.boxes, "left", 1, 0) == "low"
    assert neighbour(DRAWING.boxes, "left", 0, 1) == "right" and neighbour(DRAWING.boxes, "right", 0, -1) == "left"


def test_a_move_with_nowhere_to_go_stays_and_an_unknown_box_stays():
    assert neighbour(DRAWING.boxes, "top", -1, 0) == "top" and neighbour(DRAWING.boxes, "top", 0, 1) == "top"
    assert neighbour(DRAWING.boxes, "nowhere", 1, 0) == "nowhere"


def test_tab_walks_the_boxes_in_reading_order_and_wraps():
    order = [following(DRAWING.boxes, "top", 0)]
    for _ in NODES:
        order.append(following(DRAWING.boxes, order[-1], 1))
    assert order[0] == "top" and order[1] in {"left", "right"} and order[-1] == "top" and set(order) == set(NODES)
    assert following(DRAWING.boxes, "top", -1) == "low" and following([], "x", 1) == "x"


def test_the_status_line_names_the_selection_its_wires_what_is_outside_and_its_cycle():
    text = status_text("package", "com.acme.order", 2, 1, [("java.util", 3), ("a", 2), ("b", 1), ("c", 1)], 3, False)
    assert text.plain == "package com.acme.order · 2 out · 1 in · 4 external (java.util, a, b, ...) · ⟲ cycle with 2"
    assert status_text("file", "A.java", 0, 0, [], 0, False).plain == "file A.java · 0 out · 0 in"


def test_the_status_line_says_when_there_are_too_many_boxes_to_read_at_once():
    assert status_text("package", "p", 0, 0, [], 0, True).plain.endswith("many boxes: / finds one")
    assert DENSE_BOXES == 60
