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


from collections.abc import Hashable

from rich.text import Text

from spyc.core.printable import printable
from spyc.deps.layout import Box, Cell, Drawing

SELECTED, LIVE, CYCLE, LIVE_CYCLE, DIM = "reverse bold", "bold cyan", "yellow", "bold yellow", "dim"
DENSE_BOXES = 60
CACHED_PAINTS_PER_ROW = 20
EXTERNALS_SHOWN = 3


def paint(drawing: Drawing, selected: Hashable | None, reach: frozenset | None = None) -> list[Text]:
    return Painter(drawing).paint(selected, reach)


# Paints a drawing again and again as the selection moves. A row looks the same as before when the same wires of it
# are live and the same boxes of it are selected or reached, so only the rows a move changes are painted.
class Painter:
    def __init__(self, drawing: Drawing) -> None:
        self._drawing = drawing
        self._runs = [_runs_of(row) for row in drawing.rows]
        self._rows = [(frozenset(wire for _, _, wires in runs for wire in wires),
                       frozenset(node for _, node, _ in runs if node is not None)) for runs in self._runs]
        self._lines: dict[tuple, Text] = {}

    # With `reach`, the boxes it holds and the wires between them and the selected box stand out, and all else is
    # dim, even when nothing is reached. Without it, the wires of the selected box stand out.
    def paint(self, selected: Hashable | None, reach: frozenset | None = None) -> list[Text]:
        wires = self._drawing.wires
        if reach is None:
            live = frozenset(number for number, wire in enumerate(wires) if selected in (wire.source, wire.target))
        else:
            reach = reach | {selected}
            live = frozenset(number for number, wire in enumerate(wires) if wire.source in reach and wire.target in reach)
        if len(self._lines) > CACHED_PAINTS_PER_ROW * len(self._rows):
            self._lines.clear()
        lines = []
        for y, (in_row, nodes) in enumerate(self._rows):
            key = (y, in_row & live, selected if selected in nodes else None, reach & nodes if reach is not None else None,
                   reach is not None or bool(live))
            if key not in self._lines:
                self._lines[key] = self._line(y, selected, live, reach)
            lines.append(self._lines[key])
        return lines

    def _line(self, y: int, selected: Hashable | None, live: frozenset[int], reach: frozenset | None) -> Text:
        line = Text(no_wrap=True)
        for text, node, wires in self._runs[y]:
            line.append(text, style=self._style(node, wires, selected, live, reach))
        return line

    def _style(self, node: Hashable | None, wires: tuple[int, ...], selected: Hashable | None, live: frozenset[int],
               reach: frozenset | None) -> str:
        if node is not None:
            if node == selected:
                return SELECTED
            return "" if reach is None else LIVE if node in reach else DIM
        if not wires:
            return ""
        # Where wires cross, the cell shows the cycle colour only when every wire that decides its colour is in a cycle.
        if reach is None and not live:
            return CYCLE if self._all_cyclic(wires) else ""
        if any(wire in live for wire in wires):
            return LIVE_CYCLE if self._all_cyclic([wire for wire in wires if wire in live]) else LIVE
        return DIM

    def _all_cyclic(self, wires) -> bool:
        return all(self._drawing.wires[wire].cyclic for wire in wires)


# A drawing is mostly empty or made of long runs of one box or wire, so a row is kept as the runs of cells that
# belong together, and not as thousands of cells.
def _runs_of(row: list[Cell]) -> list[tuple[str, Hashable | None, tuple[int, ...]]]:
    runs: list[list] = []
    for cell in row:
        if runs and runs[-1][1] == cell.node and runs[-1][2] == cell.wires:
            runs[-1][0].append(cell.char)
        else:
            runs.append([[cell.char], cell.node, cell.wires])
    return [("".join(chars), node, wires) for chars, node, wires in runs]


def neighbour(boxes: list[Box], current: Hashable, dy: int, dx: int) -> Hashable:
    here = next((box for box in boxes if box.node == current), None)
    if here is None:
        return current

    def centre(box: Box) -> float:
        return box.x + box.width / 2

    if dy:
        beyond = [box for box in boxes if (box.y - here.y) * dy > 0]
        nearest = min((abs(box.y - here.y) for box in beyond), default=0)
        pool = [box for box in beyond if abs(box.y - here.y) == nearest]
    else:
        pool = [box for box in boxes if box.y == here.y and (centre(box) - centre(here)) * dx > 0]
    return min(pool, key=lambda box: abs(centre(box) - centre(here)), default=here).node


def following(boxes: list[Box], current: Hashable, step: int) -> Hashable:
    nodes = [box.node for box in sorted(boxes, key=lambda box: (box.y, box.x))]
    if current not in nodes:
        return nodes[0] if nodes else current
    return nodes[(nodes.index(current) + step) % len(nodes)]


def status_text(kind: str, name: str, outgoing: int, incoming: int, externals: list[tuple[str, int]], cycle: int,
                dense: bool, impact: str = "") -> Text:
    parts = [f"{kind} {name}", f"{outgoing} out", f"{incoming} in"]
    if impact:
        parts.append(impact)
    if externals:
        shown = ", ".join(printable(external) for external, _ in externals[:EXTERNALS_SHOWN])
        parts.append(f"{len(externals)} external ({shown}{', ...' if len(externals) > EXTERNALS_SHOWN else ''})")
    if cycle:
        parts.append(f"⟲ cycle with {cycle - 1}")
    if dense:
        parts.append("many boxes: / finds one")
    return Text(" · ".join(parts), style="bold")
