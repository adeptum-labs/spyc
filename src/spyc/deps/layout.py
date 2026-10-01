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


from collections import defaultdict
from collections.abc import Hashable, Mapping
from dataclasses import dataclass

SWEEPS = 4
GAP = 3
PORT_SPACING = 2
BOX_HEIGHT = 3
MARGIN_X, MARGIN_Y = 2, 1
UP, DOWN, LEFT, RIGHT = 1, 2, 4, 8
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}
STEPS = {(-1, 0): UP, (1, 0): DOWN, (0, -1): LEFT, (0, 1): RIGHT}
# Dashed where a line runs straight, and a solid joint where lines turn or meet.
JOINTS = {
    UP | DOWN: "┆", LEFT | RIGHT: "╌", UP: "┆", DOWN: "┆", LEFT: "╌", RIGHT: "╌",
    DOWN | RIGHT: "┌", DOWN | LEFT: "┐", UP | RIGHT: "└", UP | LEFT: "┘",
    UP | DOWN | RIGHT: "├", UP | DOWN | LEFT: "┤", LEFT | RIGHT | DOWN: "┬", LEFT | RIGHT | UP: "┴",
    UP | DOWN | LEFT | RIGHT: "┼",
}
ARROW = "▼"


@dataclass(frozen=True, slots=True)
class Cell:
    char: str = " "
    wires: tuple[int, ...] = ()
    node: Hashable | None = None


# A dependency of `source` on `target`; `cyclic` when both are in one cycle, which is drawn as an arch over the layer.
@dataclass(frozen=True)
class Wire:
    source: Hashable
    target: Hashable
    weight: int
    cyclic: bool


@dataclass(frozen=True)
class Box:
    node: Hashable
    x: int
    y: int
    width: int
    height: int = BOX_HEIGHT


@dataclass(frozen=True)
class Drawing:
    rows: list[list[Cell]]
    boxes: list[Box]
    wires: list[Wire]


# Stands where a wire that spans several layers passes through one of them.
@dataclass(frozen=True)
class _Dummy:
    wire: int
    layer: int


# One wire between two items of adjacent layers, or, as an `arch`, between two items of one layer.
@dataclass(frozen=True)
class _Hop:
    wire: int
    upper: Hashable
    lower: Hashable
    final: bool
    arch: bool = False


# Dependents above what they depend on: a node goes one layer below the lowest of those that use it, and a
# node nothing uses goes just above what it uses, so that its wires stay short.
def _layers(nodes, edges, components) -> dict:
    group = {node: components.get(node, frozenset({node})) for node in nodes}
    below, waiting = defaultdict(set), defaultdict(int)
    for source, targets in edges.items():
        for target in targets:
            if group[source] != group[target] and group[target] not in below[group[source]]:
                below[group[source]].add(group[target])
                waiting[group[target]] += 1
    layer = dict.fromkeys(group.values(), 0)
    queue = [found for found in layer if not waiting[found]]
    for found in queue:
        for other in below[found]:
            layer[other] = max(layer[other], layer[found] + 1)
            waiting[other] -= 1
            if not waiting[other]:
                queue.append(other)
    result = {node: layer[group[node]] for node in nodes}
    used = {target for targets in edges.values() for target in targets}
    for node in nodes:
        if group[node] == {node} and node not in used and edges.get(node):
            result[node] = min(result[target] for target in edges[node]) - 1
    return result


# Barycenter sweeps down and up: each item moves to the average place of the items it is wired to.
def _order(rows, hops) -> None:
    neighbours = {"up": defaultdict(list), "down": defaultdict(list)}
    for hop in hops:
        neighbours["down"][hop.upper].append(hop.lower)
        neighbours["up"][hop.lower].append(hop.upper)
    sweeps = [(level, "up", level - 1) for level in range(1, len(rows))]
    sweeps += [(level, "down", level + 1) for level in range(len(rows) - 2, -1, -1)]
    for _ in range(SWEEPS):
        for level, side, reference in sweeps:
            place = {item: position for position, item in enumerate(rows[reference])}
            current = {item: position for position, item in enumerate(rows[level])}

            def centre(item):
                found = [place[other] for other in neighbours[side][item]]
                return sum(found) / len(found) if found else current[item]

            rows[level].sort(key=lambda item: (centre(item), current[item]))


# A count goes in the middle of a run that has room for it, otherwise just after the run.
def _label_start(low: int, high: int, text: str) -> int:
    return low + (high - low + 1 - len(text)) // 2 if high - low - 1 >= len(text) + 2 else high + 2


def _sign(number: int) -> int:
    return (number > 0) - (number < 0)


def _frame(rows: list[list[Cell]], title: str) -> list[list[Cell]]:
    width = max(len(rows[0]) if rows else 0, len(title) + 4)
    body = [row + [Cell()] * (width - len(row)) for row in rows]
    head = f"┏ {title} ".ljust(width + 1, "━") + "┓"
    framed = [[Cell(char) for char in head]]
    framed += [[Cell("┃"), *row, Cell("┃")] for row in body]
    framed.append([Cell(char) for char in "┗" + "━" * width + "┛"])
    return framed


def layout(nodes, edges: Mapping, components: Mapping, labels: Mapping, title: str) -> Drawing:
    layer = _layers(nodes, edges, components)
    wires, hops = [], []
    for source in nodes:
        for target, weight in sorted(edges.get(source, {}).items(), key=lambda pair: labels[pair[0]]):
            wire = len(wires)
            wires.append(Wire(source, target, weight, layer[source] == layer[target]))
            if layer[source] == layer[target]:
                hops.append(_Hop(wire, source, target, True, arch=True))
                continue
            chain = [source, *(_Dummy(wire, depth) for depth in range(layer[source] + 1, layer[target])), target]
            hops += [_Hop(wire, upper, lower, lower is target) for upper, lower in zip(chain, chain[1:])]
    rows = [[] for _ in range(max(layer.values(), default=-1) + 1)]
    for node in sorted(nodes, key=labels.__getitem__):
        rows[layer[node]].append(node)
    for hop in hops:
        if isinstance(hop.lower, _Dummy):
            rows[hop.lower.layer].append(hop.lower)
    _order(rows, [hop for hop in hops if not hop.arch])
    index = {item: position for row in rows for position, item in enumerate(row)}
    level_of = {item: depth for depth, row in enumerate(rows) for item in row}

    # Every end of a wire lands on the top or the bottom of an item, in the order of where its other end is.
    slots = defaultdict(list)
    for hop in hops:
        slots[hop.upper, "top" if hop.arch else "bottom"].append((index[hop.lower], hop.wire, hop, "upper"))
        slots[hop.lower, "top"].append((index[hop.upper], hop.wire, hop, "lower"))
    widths = {item: 1 if isinstance(item, _Dummy) else
              max(len(labels[item]) + 4, (max(len(slots[item, "top"]), len(slots[item, "bottom"])) - 1) * PORT_SPACING + 3)
              for row in rows for item in row}
    span = max((sum(widths[item] for item in row) + GAP * (len(row) - 1) for row in rows), default=0)
    x_of = {}
    for row in rows:
        x = (span - sum(widths[item] for item in row) - GAP * (len(row) - 1)) // 2
        for item in row:
            x_of[item] = x
            x += widths[item] + GAP
    column = {}
    for (item, _), entries in slots.items():
        entries.sort(key=lambda entry: entry[:2])
        first = x_of[item] + (widths[item] - ((len(entries) - 1) * PORT_SPACING + 1)) // 2
        for position, (_, _, hop, end) in enumerate(entries):
            column[hop, end] = first + PORT_SPACING * position

    # Each layer has a channel above it for the wires that end there. A wire runs on a track of its own where it
    # would otherwise meet another, and a track is as long as the run and its count.
    hops_into = defaultdict(list)
    for hop in hops:
        hops_into[level_of[hop.lower]].append(hop)
    track_of, track_count = {}, {}
    for level in range(len(rows)):
        taken = []
        for hop in sorted(hops_into[level], key=lambda found: (min(column[found, "upper"], column[found, "lower"]), column[found, "lower"])):
            low, high = sorted((column[hop, "upper"], column[hop, "lower"]))
            if hop.final:
                text = str(wires[hop.wire].weight)
                high = max(high, _label_start(low, high, text) + len(text) - 1)
            track = next((number for number, end in enumerate(taken) if end < low), len(taken))
            taken[track:track + 1] = [high]
            track_of[hop] = track
        track_count[level] = len(taken)
    top_of, y = {}, MARGIN_Y
    for level in range(len(rows)):
        y += (track_count[level] + 2) if track_count[level] else (1 if level else 0)
        top_of[level] = y
        y += BOX_HEIGHT

    masks, owners, letters = defaultdict(int), defaultdict(list), {}

    def trace(path, wire):
        for start, end in zip(path, path[1:]):
            step_y, step_x = _sign(end[0] - start[0]), _sign(end[1] - start[1])
            direction = STEPS[step_y, step_x]
            for step in range(max(abs(end[0] - start[0]), abs(end[1] - start[1])) + 1):
                cell = (start[0] + step_y * step, start[1] + step_x * step)
                masks[cell] |= (direction if cell != end else 0) | (OPPOSITE[direction] if cell != start else 0)
                if wire not in owners[cell]:
                    owners[cell].append(wire)

    for hop in hops:
        level = level_of[hop.lower]
        box_top, upper, lower = top_of[level], column[hop, "upper"], column[hop, "lower"]
        track_y = box_top - track_count[level] - 1 + track_of[hop]
        if hop.arch:
            start_y = box_top - 1
        elif isinstance(hop.upper, _Dummy):
            start_y = top_of[level_of[hop.upper]]
        else:
            start_y = top_of[level_of[hop.upper]] + BOX_HEIGHT
        path = [(start_y, upper), (track_y, upper), (track_y, lower), (box_top - 1, lower)]
        trace([cell for position, cell in enumerate(path) if position == 0 or cell != path[position - 1]], hop.wire)
        if hop.final:
            letters[box_top - 1, lower] = (ARROW, hop.wire)
            text, (low, high) = str(wires[hop.wire].weight), sorted((upper, lower))
            for offset, char in enumerate(text):
                letters[track_y, _label_start(low, high, text) + offset] = (char, hop.wire)

    cells, boxes = {}, []
    for item, x in x_of.items():
        if isinstance(item, _Dummy):
            continue
        width, top = widths[item], top_of[level_of[item]]
        boxes.append(Box(item, x + MARGIN_X + 1, top + 1, width))
        label = f" {labels[item]} ".center(width - 2)
        for row, text in enumerate((f"┌{'─' * (width - 2)}┐", f"│{label}│", f"└{'─' * (width - 2)}┘")):
            for offset, char in enumerate(text):
                cells[top + row, x + offset] = Cell(char, (), item)
    for position, mask in masks.items():
        cells.setdefault(position, Cell(JOINTS.get(mask, "┼"), tuple(owners[position])))
    for position, (char, wire) in letters.items():
        cells[position] = Cell(char, (wire,))
    height = max((y for y, _ in cells), default=-1) + 1 + MARGIN_Y
    width = max(span, max((x + 1 for _, x in cells), default=0)) + 2 * MARGIN_X
    grid = [[Cell() for _ in range(width)] for _ in range(height)]
    for (y, x), cell in cells.items():
        grid[y][x + MARGIN_X] = cell
    return Drawing(_frame(grid, title), boxes, wires)


def text_of(drawing: Drawing) -> str:
    return "\n".join("".join(cell.char for cell in row).rstrip() for row in drawing.rows)
