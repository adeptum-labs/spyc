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

from spyc.deps.layout import Box, Cell, Drawing

SELECTED, LIVE, CYCLE, LIVE_CYCLE, DIM = "reverse bold", "bold cyan", "yellow", "bold yellow", "dim"
DENSE_BOXES = 60
EXTERNALS_SHOWN = 3


def paint(drawing: Drawing, selected: Hashable | None) -> list[Text]:
    live = {number for number, wire in enumerate(drawing.wires) if selected in (wire.source, wire.target)}
    return [_line(row, drawing, selected, live) for row in drawing.rows]


def _style(cell: Cell, drawing: Drawing, selected: Hashable | None, live: set[int]) -> str:
    if cell.node is not None:
        return SELECTED if cell.node == selected else ""
    if not cell.wires:
        return ""
    cyclic = any(drawing.wires[wire].cyclic for wire in cell.wires)
    if not live:
        return CYCLE if cyclic else ""
    if any(wire in live for wire in cell.wires):
        return LIVE_CYCLE if cyclic else LIVE
    return DIM


# Cells of one style are appended together, as a drawing has thousands of them.
def _line(row: list[Cell], drawing: Drawing, selected: Hashable | None, live: set[int]) -> Text:
    line, run, style = Text(no_wrap=True), [], ""
    for cell in row:
        found = _style(cell, drawing, selected, live)
        if found != style and run:
            line.append("".join(run), style=style)
            run = []
        style = found
        run.append(cell.char)
    line.append("".join(run), style=style)
    return line


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
                dense: bool) -> Text:
    parts = [f"{kind} {name}", f"{outgoing} out", f"{incoming} in"]
    if externals:
        shown = ", ".join(external for external, _ in externals[:EXTERNALS_SHOWN])
        parts.append(f"{len(externals)} external ({shown}{', ...' if len(externals) > EXTERNALS_SHOWN else ''})")
    if cycle:
        parts.append(f"⟲ cycle with {cycle - 1}")
    if dense:
        parts.append("many boxes: / finds one")
    return Text(" · ".join(parts), style="bold")
