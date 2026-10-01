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


import random

from spyc.deps.layout import Drawing, layout, text_of


def draw(edges, nodes=None, components=None, title="t"):
    nodes = nodes or sorted(set(edges) | {target for targets in edges.values() for target in targets})
    return layout(nodes, edges, components or {}, {node: node for node in nodes}, title)


def box_text(drawing, box):
    return "".join(cell.char for cell in drawing.rows[box.y + 1][box.x:box.x + box.width])


def test_a_dependent_is_drawn_above_what_it_depends_on_with_a_dashed_line_and_the_count():
    assert text_of(draw({"a": {"b": 5}})) == "\n".join([
        "┏ t ━━━━━━┓",
        "┃         ┃",
        "┃  ┌───┐  ┃",
        "┃  │ a │  ┃",
        "┃  └───┘  ┃",
        "┃    ┆    ┃",
        "┃    ┆ 5  ┃",
        "┃    ▼    ┃",
        "┃  ┌───┐  ┃",
        "┃  │ b │  ┃",
        "┃  └───┘  ┃",
        "┃         ┃",
        "┗━━━━━━━━━┛"])


def test_a_wire_that_spans_layers_passes_the_layer_between_and_every_count_is_drawn():
    drawing = draw({"a": {"b": 1, "c": 2}, "b": {"c": 3}})
    ys = {box.node: box.y for box in drawing.boxes}
    assert ys["a"] < ys["b"] < ys["c"]
    text = text_of(drawing)
    assert all(count in text for count in "123") and text.count("▼") == 3


def test_members_of_a_cycle_share_a_layer_and_are_joined_by_arches_over_it():
    nodes = ["a", "b"]
    group = frozenset(nodes)
    drawing = draw({"a": {"b": 2}, "b": {"a": 3}}, nodes, {"a": group, "b": group}, "cycle")
    assert len({box.y for box in drawing.boxes}) == 1 and all(wire.cyclic for wire in drawing.wires)
    assert "\n".join(text_of(drawing).splitlines()[3:6]) == "\n".join([
        "┃   ┌╌╌╌2╌╌╌┐     ┃", "┃   ┆ ┌╌╌╌3╌┼╌┐   ┃", "┃   ┆ ▼     ▼ ┆   ┃"])


def test_a_node_nothing_uses_goes_just_above_what_it_uses():
    drawing = draw({"top": {"mid": 1}, "mid": {"low": 1}, "lone": {"low": 1}})
    ys = {box.node: box.y for box in drawing.boxes}
    assert ys["lone"] == ys["mid"]


def test_nodes_without_edges_and_an_empty_graph_are_drawn():
    assert text_of(draw({}, ["x"], title="one")) == "\n".join(
        ["┏ one ━━━━┓", "┃         ┃", "┃  ┌───┐  ┃", "┃  │ x │  ┃", "┃  └───┘  ┃", "┃         ┃", "┗━━━━━━━━━┛"])
    assert text_of(draw({}, [], title="empty")) == "┏ empty ━━┓\n┃         ┃\n┗━━━━━━━━━┛"


def test_every_box_is_where_its_hit_area_says_and_every_row_is_as_wide_as_the_frame():
    drawing = draw({"a": {"b": 1, "c": 12345}, "b": {"c": 3}, "d": {"c": 1}})
    assert len({len(row) for row in drawing.rows}) == 1
    assert [box_text(drawing, box).strip("│ ") for box in drawing.boxes] == [box.node for box in drawing.boxes]


def test_a_count_wider_than_its_run_does_not_fall_off_the_frame():
    drawing = draw({"a": {"b": 1, "c": 1234567}, "b": {"c": 3}})
    assert "1234567" in text_of(drawing) and drawing.rows[0][-1].char == "┓"


def test_a_long_title_widens_the_frame():
    assert text_of(draw({}, ["x"], title="a.very.long.package.name")).splitlines()[0].startswith("┏ a.very.long.package.name ")


def test_the_same_input_gives_the_same_drawing():
    edges = {"a": {"b": 2, "c": 1}, "b": {"d": 4}, "c": {"d": 1}}
    assert text_of(draw(edges)) == text_of(draw(edges))


def test_the_cells_of_a_wire_say_which_wire_they_belong_to():
    drawing = draw({"a": {"b": 5}})
    owned = {wire for row in drawing.rows for cell in row for wire in cell.wires}
    assert owned == {0} and drawing.wires[0].source == "a" and drawing.wires[0].target == "b"


def test_graphs_of_any_shape_are_drawn_whole():
    generator = random.Random(1)
    for _ in range(60):
        nodes = [f"n{index}" for index in range(generator.randint(1, 14))]
        edges = {a: {b: generator.randint(1, 120) for b in nodes if b != a and generator.random() < 0.25} for a in nodes}
        groups = _groups(nodes, edges)
        drawing = layout(nodes, edges, groups, {node: node for node in nodes}, "r")
        assert isinstance(drawing, Drawing) and len({len(row) for row in drawing.rows}) == 1
        assert [box_text(drawing, box).strip("│ ") for box in drawing.boxes] == [box.node for box in drawing.boxes]
        assert len(drawing.wires) == sum(len(targets) for targets in edges.values())


def _groups(nodes, edges):
    reach = {a: set(edges[a]) for a in nodes}
    for _ in nodes:
        for a in nodes:
            reach[a] |= set().union(*[reach[b] for b in reach[a]])
    return {a: frozenset({a} | {b for b in nodes if a in reach[b] and b in reach[a]}) for a in nodes}
