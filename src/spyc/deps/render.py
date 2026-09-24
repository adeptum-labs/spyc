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


from dataclasses import dataclass

from rich.text import Text

from spyc.deps.graph import CLASS, FILE, UNIT, DependencyGraph, Link, Node

WEIGHT_WIDTH = 5
ARM = 2
CYCLE_MARK = " ⟲"
EXTERNALS_SHOWN = 3
LEVEL_NAMES = {UNIT: "package", FILE: "file", CLASS: "class"}
# Box-drawing glyph for a junction, by the directions it connects: up, down, left, right.
GLYPHS = {
    (False, False, False, False): " ",
    (False, False, True, True): "─", (False, False, True, False): "─", (False, False, False, True): "─",
    (True, True, False, False): "│",
    (True, True, True, False): "┤", (True, True, False, True): "├", (True, True, True, True): "┼",
    (False, True, True, False): "┐", (False, True, False, True): "┌", (False, True, True, True): "┬",
    (True, False, True, False): "┘", (True, False, False, True): "└", (True, False, True, True): "┴",
}


@dataclass(frozen=True)
class Entry:
    label: str
    weight: int
    cyclic: bool = False


# Where a neighbour's label is on screen: the row and the cells it covers, for clicks.
@dataclass(frozen=True)
class Placed:
    row: int
    start: int
    end: int
    side: str
    index: int


@dataclass(frozen=True)
class FocusLayout:
    lines: list[Text]
    places: list[Placed]


def entries_of(graph: DependencyGraph, centre: Node, links: list[Link], printable) -> list[Entry]:
    members = graph.cycle_members(centre)
    return [Entry(printable(link.node.name), link.weight, link.node in members) for link in links]


def header_text(graph: DependencyGraph, centre: Node, printable) -> Text:
    members = graph.cycle_members(centre)
    externals = graph.externals(centre)
    parts = [f"{LEVEL_NAMES[centre.level]} {printable(centre.name)}", f"{len(graph.outgoing(centre))} out",
             f"{len(graph.incoming(centre))} in"]
    if externals:
        shown = ", ".join(printable(name) for name, _ in externals[:EXTERNALS_SHOWN])
        parts.append(f"{len(externals)} external ({shown}{', ...' if len(externals) > EXTERNALS_SHOWN else ''})")
    if members:
        parts.append(f"⟲ cycle with {len(members)}")
    return Text(" · ".join(parts), style="bold")


# A name that does not fit loses its start, not its end: package names and paths share their start.
def _cell(entry: Entry, width: int) -> str:
    mark = CYCLE_MARK if entry.cyclic else ""
    room = max(width - len(mark), 0)
    label = entry.label if len(entry.label) <= room else ("…" + entry.label[len(entry.label) - room + 1:] if room else "")
    return (label + mark).ljust(width)


def _weight(entry: Entry) -> str:
    return f"×{min(entry.weight, 999)}".rjust(WEIGHT_WIDTH)


# The selected name is cut to a third of the width, so that a long path leaves room for its neighbours.
def _shortened(name: str, width: int) -> str:
    limit = max(width // 3, 12)
    return name if len(name) <= limit else "…" + name[len(name) - limit + 1:]


def _rows_of(count: int, rows: int, middle: int) -> range:
    start = min(max(middle - count // 2, 0), rows - count)
    return range(start, start + count)


# The bar that joins the neighbours of one side to the row of the selected node.
def _junctions(count: int, rows: int, middle: int, items_on_left: bool) -> list[str]:
    occupied = set(_rows_of(count, rows, middle))
    if not occupied:
        return [" "] * rows
    top, bottom = min(min(occupied), middle), max(max(occupied), middle)
    return [GLYPHS[(row > top, row < bottom, row in occupied if items_on_left else row == middle,
                    row == middle if items_on_left else row in occupied)] if top <= row <= bottom else " "
            for row in range(rows)]


def _width_of(entries: list[Entry]) -> int:
    return max((len(entry.label) + (len(CYCLE_MARK) if entry.cyclic else 0) for entry in entries), default=0)


# Used by on the left, the selected node in the middle, depends on on the right.
def focus_layout(centre: str, left: list[Entry], right: list[Entry], width: int,
                 selected: tuple[str, int] | None = None) -> FocusLayout:
    rows = max(len(left), len(right), 1)
    middle = rows // 2
    centre = _shortened(centre, width)
    room = max(width - (2 * WEIGHT_WIDTH + 2 * ARM + 12) - len(centre), 2)
    left_width = min(_width_of(left), room // 2)
    right_width = min(_width_of(right), room - left_width)
    left_rows, right_rows = _rows_of(len(left), rows, middle), _rows_of(len(right), rows, middle)
    left_bar, right_bar = _junctions(len(left), rows, middle, True), _junctions(len(right), rows, middle, False)
    lines, places = [], []
    for row in range(rows):
        line = Text(no_wrap=True)
        if row in left_rows:
            index = row - left_rows.start
            line.append(_cell(left[index], left_width), style="reverse" if selected == ("in", index) else "")
            line.append(_weight(left[index]), style="dim")
            line.append("─" * ARM)
            places.append(Placed(row, 0, left_width, "in", index))
        else:
            line.append(" " * (left_width + WEIGHT_WIDTH + ARM if left else 0))
        line.append(left_bar[row])
        if row == middle:
            line.append(("─▶ " if left else "   ") + centre + (" ─" if right else "  "), style="bold")
        else:
            line.append(" " * (len(centre) + 5))
        line.append(right_bar[row])
        if row in right_rows:
            index = row - right_rows.start
            line.append("─▶ ")
            start = len(line.plain)
            line.append(_cell(right[index], right_width), style="reverse" if selected == ("out", index) else "")
            line.append(_weight(right[index]), style="dim")
            places.append(Placed(row, start, start + right_width, "out", index))
        lines.append(line)
    return FocusLayout(lines, places)


# For a terminal too narrow for three columns: the same three groups, one under the other.
def stacked_layout(centre: str, left: list[Entry], right: list[Entry], width: int,
                   selected: tuple[str, int] | None = None) -> FocusLayout:
    lines, places = [], []
    for title, side, entries in (("used by", "in", left), (None, "", []), ("depends on", "out", right)):
        if title is None:
            lines.append(Text(centre, style="bold"))
            continue
        lines.append(Text(f"{title} ({len(entries)})", style="dim"))
        cell = min(_width_of(entries), max(width - 2 - WEIGHT_WIDTH, 2))
        for index, entry in enumerate(entries):
            line = Text(no_wrap=True)
            line.append("  ")
            line.append(_cell(entry, cell), style="reverse" if selected == (side, index) else "")
            line.append(_weight(entry), style="dim")
            places.append(Placed(len(lines), 2, 2 + cell, side, index))
            lines.append(line)
    return FocusLayout(lines, places)
