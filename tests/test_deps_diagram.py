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


from spyc.deps.diagram import DENSE_BOXES, Painter, following, neighbour, paint, status_text
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


def test_a_crossing_is_yellow_only_where_every_wire_through_it_is_in_a_cycle():
    nodes = list("abcdefg")
    edges = {"a": {"b": 1}, "b": {"a": 1, "e": 1}, "c": {"a": 1, "b": 1, "e": 1}, "d": {"c": 1, "b": 1, "a": 1},
             "f": {"d": 1, "a": 1, "b": 1, "e": 1}, "g": {"f": 1, "e": 1, "a": 1}}
    group = frozenset("ab")
    drawing = layout(nodes, edges, {"a": group, "b": group}, {n: n for n in nodes}, "t")
    mixed = [(y, x) for y, row in enumerate(drawing.rows) for x, cell in enumerate(row)
             if len({drawing.wires[wire].cyclic for wire in cell.wires}) > 1]
    assert mixed
    for selected in (None, "d", "g"):
        lines = paint(drawing, selected)
        for y, x in mixed:
            assert not any("yellow" in str(span.style) and span.start <= x < span.end for span in lines[y].spans)


def test_with_a_reach_its_boxes_and_the_wires_between_them_stand_out_and_all_else_is_dim():
    assert {"reverse bold", "bold cyan", "dim"} <= styles(DRAWING, "left") and "reverse bold" in styles(DRAWING, "low")
    reached_lines = paint(DRAWING, "low", frozenset({"left", "right", "top"}))
    assert "dim" not in {str(span.style) for line in reached_lines for span in line.spans}
    assert "bold cyan" in {str(span.style) for line in reached_lines for span in line.spans}
    only_left = paint(DRAWING, "low", frozenset({"left"}))
    assert "dim" in {str(span.style) for line in only_left for span in line.spans}


def test_with_a_reach_that_is_empty_the_selected_box_stands_alone_in_a_dim_drawing():
    found = {str(span.style) for line in paint(DRAWING, "low", frozenset()) for span in line.spans}
    assert found == {"reverse bold", "dim"}


def test_a_painter_with_a_reach_gives_the_same_lines_as_painting_from_scratch():
    painter = Painter(DRAWING)
    for selected, reach in [("low", frozenset({"left", "right"})), ("low", frozenset({"left"})), ("left", None),
                            ("top", frozenset({"left", "low"})), ("low", frozenset({"left", "right"}))]:
        assert [line.spans for line in painter.paint(selected, reach)] == [line.spans for line in paint(DRAWING, selected, reach)]


def test_a_painter_gives_the_same_lines_as_painting_and_does_not_paint_a_row_again_that_did_not_change():
    painter = Painter(DRAWING)
    first = painter.paint("left")
    assert [line.plain for line in first] == [line.plain for line in paint(DRAWING, "left")]
    assert [line.spans for line in first] == [line.spans for line in paint(DRAWING, "left")]
    again = painter.paint("left")
    assert all(a is b for a, b in zip(first, again))
    moved = painter.paint("right")
    assert [line.spans for line in moved] == [line.spans for line in paint(DRAWING, "right")]
    assert sum(a is b for a, b in zip(first, moved)) > 0


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


def test_a_name_from_outside_the_project_cannot_send_control_characters_to_the_terminal():
    text = status_text("file", "a.js", 0, 0, [("evil\x1b]52;c;ZXZpbA==\x07", 1)], 0, False)
    assert "\x1b" not in text.plain and "\x07" not in text.plain


def test_the_status_line_says_when_there_are_too_many_boxes_to_read_at_once():
    assert status_text("package", "p", 0, 0, [], 0, True).plain.endswith("many boxes: / finds one")
    assert DENSE_BOXES == 60
