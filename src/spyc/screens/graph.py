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


from collections.abc import Callable
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from spyc.deps.graph import UNIT, DependencyGraph, Node
from spyc.deps.picker import NodeSource
from spyc.deps.render import FocusLayout, entries_of, focus_layout, header_text, stacked_layout
from spyc.file_picker import FilePickerSource
from spyc.fuzzy import PathMatcher
from spyc.location import Location
from spyc.picking import Choice
from spyc.printable import printable
from spyc.screens.picker import Picker
from spyc.widgets.graph_view import GraphView

NARROW_WIDTH = 100
PROGRESS_INTERVAL = 0.5
NOTHING_FOUND = "No dependencies found: no file is in a supported language"


# One node in the middle, what depends on it on the left and what it depends on on
# the right. Enter moves the middle to the highlighted node; the bracket keys go a
# level down or up; o gives the code to open.
class GraphScreen(Screen[Location | None]):
    DEFAULT_CSS = """
    GraphScreen #graph-header { height: 1; padding: 0 1; background: $panel; }
    GraphScreen GraphView { height: 1fr; }
    """
    BINDINGS = [
        Binding("escape,q", "close", "Back"),
        Binding("enter", "centre", "Centre"),
        Binding("backspace", "back", "Previous", show=False),
        Binding("right_square_bracket", "deeper", "Deeper"),
        Binding("left_square_bracket", "shallower", "Higher"),
        Binding("slash", "pick", "Find"),
        Binding("o", "open", "Open"),
        Binding("c", "cycle", "Cycles"),
        Binding("left", "side('in')", show=False),
        Binding("right", "side('out')", show=False),
        Binding("tab,shift+tab", "toggle_side", show=False),
        Binding("up,k", "move(-1)", show=False),
        Binding("down,j", "move(1)", show=False),
    ]

    def __init__(self, root: Path, graph: DependencyGraph | None, progress: Callable[[], str],
                 path: str | None = None, failure: str | None = None) -> None:
        super().__init__()
        self._root, self._graph, self._progress, self._path = root, graph, progress, path
        self._failure = failure
        self.centre: Node | None = None
        self._side, self._index = "out", 0
        self._history: list[Node] = []
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="graph-header")
        yield GraphView()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Dependencies"
        if self._graph is not None:
            self.centre = self._initial(self._graph)
            self._select_default()
        elif self._failure is None:
            self._timer = self.set_interval(PROGRESS_INTERVAL, self._redraw)
        self._redraw()

    def on_resize(self) -> None:
        self._redraw()

    # A new graph arrives when the project is read again: the middle stays where it was if that node still exists.
    def set_graph(self, graph: DependencyGraph) -> None:
        self._graph, self._failure = graph, None
        self._stop_waiting()
        if self.centre is None or not graph.has(self.centre):
            self._history.clear()
            self.centre = self._initial(graph)
            self._select_default()
        self._clamp_selection()
        self._redraw()

    # Something went wrong reading the project, so there is no graph to wait for.
    def set_failure(self, message: str) -> None:
        self._failure = message
        self._stop_waiting()
        self._redraw()

    def _stop_waiting(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _initial(self, graph: DependencyGraph) -> Node | None:
        return (graph.unit_of(self._path) if self._path else None) or graph.most_connected(graph.nodes(UNIT))

    def _neighbours(self, side: str):
        if self._graph is None or self.centre is None:
            return []
        return self._graph.incoming(self.centre) if side == "in" else self._graph.outgoing(self.centre)

    def _select_default(self) -> None:
        self._side, self._index = ("out" if self._neighbours("out") or not self._neighbours("in") else "in"), 0

    def _clamp_selection(self) -> None:
        if not self._neighbours(self._side):
            self._side = "in" if self._side == "out" else "out"
        self._index = min(self._index, max(len(self._neighbours(self._side)) - 1, 0))

    def _redraw(self) -> None:
        view, header = self.query_one(GraphView), self.query_one("#graph-header", Static)
        graph = self._graph
        if graph is None or self.centre is None:
            header.update(Text(""))
            view.show(FocusLayout([Text(self._message(graph))], []))
            return
        left = entries_of(graph, self.centre, graph.incoming(self.centre), printable)
        right = entries_of(graph, self.centre, graph.outgoing(self.centre), printable)
        selected = (self._side, self._index) if self._neighbours(self._side) else None
        layout = focus_layout if self.size.width >= NARROW_WIDTH else stacked_layout
        header.update(header_text(graph, self.centre, printable))
        drawing = layout(printable(self.centre.name), left, right, self.size.width, selected)
        view.show(drawing)
        selected_place = next((place for place in drawing.places if (place.side, place.index) == selected), None)
        if selected_place is not None:
            view.reveal(selected_place.row)

    def _message(self, graph: DependencyGraph | None) -> str:
        if self._failure is not None:
            return self._failure
        if graph is not None:
            return NOTHING_FOUND
        progress = self._progress()
        return f"Reading imports ({progress})" if progress else "Reading imports"

    def _go(self, node: Node) -> None:
        if self.centre is not None:
            self._history.append(self.centre)
        self.centre = node
        self._select_default()
        self._redraw()

    def action_side(self, side: str) -> None:
        if self._neighbours(side):
            self._side, self._index = side, min(self._index, len(self._neighbours(side)) - 1)
            self._redraw()

    def action_toggle_side(self) -> None:
        self.action_side("in" if self._side == "out" else "out")

    def action_move(self, delta: int) -> None:
        count = len(self._neighbours(self._side))
        if count:
            self._index = min(max(self._index + delta, 0), count - 1)
            self._redraw()

    def action_centre(self) -> None:
        neighbours = self._neighbours(self._side)
        if self._index < len(neighbours):
            self._go(neighbours[self._index].node)

    def action_back(self) -> None:
        if self._history:
            self.centre = self._history.pop()
            self._select_default()
            self._redraw()

    def action_deeper(self) -> None:
        graph = self._graph
        below = graph.children(self.centre) if graph is not None and self.centre is not None else []
        if below:
            self._go(graph.most_connected(below))
        else:
            self.notify("Nothing below this")

    def action_shallower(self) -> None:
        parent = self._graph.parent(self.centre) if self._graph is not None and self.centre is not None else None
        if parent is not None:
            self._go(parent)
        else:
            self.notify("Already at the top")

    def action_pick(self) -> None:
        if self._graph is not None and self.centre is not None:
            self.app.push_screen(Picker(NodeSource(self._graph, self.centre.level)), self._picked)

    def _picked(self, choice: Choice | None) -> None:
        node = Node(self.centre.level, choice.key) if choice is not None and self.centre is not None else None
        if node is not None and self._graph is not None and self._graph.has(node):
            self._go(node)

    def action_open(self) -> None:
        paths = self._graph.paths_of(self.centre) if self._graph is not None and self.centre is not None else []
        if not paths:
            self.notify("Nothing to open here")
        elif len(paths) == 1:
            self.dismiss(Location(paths[0], self._graph.line_of(self.centre)))
        else:
            self.app.push_screen(Picker(FilePickerSource(self._root, PathMatcher(paths), lambda: [])), self._opened)

    def _opened(self, choice: Choice | None) -> None:
        if choice is not None:
            self.dismiss(Location(choice.key, choice.line))

    def action_cycle(self) -> None:
        cyclic = self._graph.cyclic_nodes(self.centre.level) if self._graph is not None and self.centre is not None else []
        if not cyclic:
            self.notify("No cycles at this level")
            return
        later = [node for node in cyclic if node > self.centre]
        self._go((later or cyclic)[0])

    def on_graph_view_clicked(self, message: GraphView.Clicked) -> None:
        message.stop()
        self._side, self._index = message.side, message.index
        self.action_centre()

    def action_close(self) -> None:
        self.dismiss(None)
