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

from spyc.core.file_picker import FilePickerSource
from spyc.core.fuzzy import PathMatcher
from spyc.core.location import Location
from spyc.core.picking import Choice
from spyc.core.printable import printable
from spyc.deps.diagram import DENSE_BOXES, following, neighbour, paint, status_text
from spyc.deps.graph import FILE, DependencyGraph, Node
from spyc.deps.layout import Drawing, layout
from spyc.deps.picker import NodeSource
from spyc.deps.scopes import OWN_LABEL, ROOT, Hierarchy, Member, label_of, title_of
from spyc.screens.picker import Picker
from spyc.widgets.graph_view import GraphView

PROGRESS_INTERVAL = 0.5
NOTHING_FOUND = "No dependencies found: no file is in a supported language"


# The packages of one scope as layered boxes, what depends on what above what it depends on. Enter goes into
# the selected box and Backspace out of it; the arrow keys and Tab move the selection; o gives the code to open.
class GraphScreen(Screen[Location | None]):
    DEFAULT_CSS = """
    GraphScreen #graph-header { height: 1; padding: 0 1; background: $panel; }
    GraphScreen GraphView { height: 1fr; }
    """
    BINDINGS = [
        Binding("escape,q", "close", "Back"),
        Binding("enter,right_square_bracket", "deeper", "Into"),
        Binding("backspace,left_square_bracket", "shallower", "Up"),
        Binding("slash", "pick", "Find"),
        Binding("o", "open", "Open"),
        Binding("c", "cycle", "Cycles"),
        Binding("a", "about", "About"),
        Binding("left,h", "move(0,-1)", show=False),
        Binding("right,l", "move(0,1)", show=False),
        Binding("up,k", "move(-1,0)", show=False),
        Binding("down,j", "move(1,0)", show=False),
        Binding("tab", "step(1)", show=False),
        Binding("shift+tab", "step(-1)", show=False),
    ]

    def __init__(self, root: Path, graph: DependencyGraph | None, progress: Callable[[], str],
                 path: str | None = None, failure: str | None = None,
                 explain: Callable[[Member, tuple[str, ...]], None] | None = None) -> None:
        super().__init__()
        self._root, self._graph, self._progress, self._path = root, graph, progress, path
        self._failure, self._explain = failure, explain
        self._hierarchy: Hierarchy | None = None
        self._drawing: Drawing | None = None
        self._edges: dict = {}
        self._cycles: dict = {}
        self.scope: Member = ROOT
        self.selected: Member | None = None
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="graph-header")
        yield GraphView()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = "Dependencies"
        if self._graph is not None:
            self._open(self._graph)
        elif self._failure is None:
            self._timer = self.set_interval(PROGRESS_INTERVAL, self._redraw)
        self._redraw()

    # A new graph arrives when the project is read again: the scope and the selection stay if they still exist.
    def set_graph(self, graph: DependencyGraph) -> None:
        self._graph, self._failure = graph, None
        self._stop_waiting()
        self._open(graph, (self.scope, self.selected) if self._drawing is not None else None)
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

    def _open(self, graph: DependencyGraph, previous: tuple[Member, Member | None] | None = None) -> None:
        self._hierarchy = Hierarchy(graph)
        self._drawing = None
        if graph.empty:
            return
        if previous is not None and self._hierarchy.members(previous[0]):
            self._show(*previous)
            return
        unit = graph.unit_of(self._path) if self._path else None
        self._show(*(self._hierarchy.locate(unit) if unit is not None else (self._hierarchy.settle(ROOT), None)))

    def _show(self, scope: Member, selected: Member | None = None) -> None:
        members = self._hierarchy.members(scope)
        self._edges = self._hierarchy.edges(scope)
        self._cycles = self._hierarchy.cycles(self._edges, members)
        labels = {member: printable(label_of(member, scope)) for member in members}
        self._drawing = layout(members, self._edges, self._cycles, labels, printable(title_of(scope, self._root.resolve().name)))
        self.scope = scope
        self.selected = selected if selected in members else min(members, key=self._busyness, default=None)

    def _busyness(self, member: Member) -> tuple[int, str]:
        degree = len(self._edges.get(member, {})) + sum(member in targets for targets in self._edges.values())
        return -degree, label_of(member, self.scope)

    def _go(self, scope: Member, selected: Member | None = None) -> None:
        self._show(scope, selected)
        self._redraw()

    def _redraw(self) -> None:
        view, header = self.query_one(GraphView), self.query_one("#graph-header", Static)
        drawing = self._drawing
        if drawing is None:
            header.update(Text(""))
            view.show([Text(self._message())], [])
            return
        view.show(paint(drawing, self.selected), drawing.boxes)
        header.update(self._status(len(drawing.boxes)))
        if (box := next((box for box in drawing.boxes if box.node == self.selected), None)) is not None:
            view.reveal(box)

    def _status(self, boxes: int) -> Text:
        member = self.selected
        if member is None:
            return Text("")
        outgoing, incoming = len(self._edges.get(member, {})), sum(member in targets for targets in self._edges.values())
        kind = f"{member.kind} {OWN_LABEL}" if member.own else member.kind
        return status_text(kind, printable(member.key), outgoing, incoming, self._hierarchy.externals(member),
                           len(self._cycles.get(member, ())), boxes >= DENSE_BOXES)

    def _message(self) -> str:
        if self._failure is not None:
            return self._failure
        if self._graph is not None:
            return NOTHING_FOUND
        progress = self._progress()
        return f"Reading imports ({progress})" if progress else "Reading imports"

    def action_move(self, dy: int, dx: int) -> None:
        if self._drawing is not None and self.selected is not None:
            self.selected = neighbour(self._drawing.boxes, self.selected, dy, dx)
            self._redraw()

    def action_step(self, step: int) -> None:
        if self._drawing is not None and self.selected is not None:
            self.selected = following(self._drawing.boxes, self.selected, step)
            self._redraw()

    def action_deeper(self) -> None:
        if self.selected is None:
            return
        if self.selected.kind == FILE:
            self.notify("A file has nothing below it: o opens it")
        else:
            self._go(self._hierarchy.settle(self.selected))

    def action_shallower(self) -> None:
        parent = self._hierarchy.parent(self.scope) if self._drawing is not None else None
        if parent is None:
            self.notify("Already at the top")
        else:
            self._go(parent, self._hierarchy.containing(parent, self.scope))

    def action_pick(self) -> None:
        if self._graph is not None and self._drawing is not None:
            self.app.push_screen(Picker(NodeSource(self._graph)), self._picked)

    def _picked(self, choice: Choice | None) -> None:
        if choice is None or self._graph is None:
            return
        level, _, key = choice.key.partition(":")
        if self._graph.has(node := Node(level, key)):
            self._go(*self._hierarchy.locate(node))

    def _paths(self) -> list[str]:
        return self._hierarchy.paths_of(self.selected) if self._drawing is not None and self.selected is not None else []

    def action_open(self) -> None:
        paths = self._paths()
        if not paths:
            self.notify("Nothing to open here")
        elif len(paths) == 1:
            self.dismiss(Location(paths[0]))
        else:
            self.app.push_screen(Picker(FilePickerSource(self._root, PathMatcher(paths), lambda: [])), self._opened)

    def _opened(self, choice: Choice | None) -> None:
        if choice is not None:
            self.dismiss(Location(choice.key, choice.line))

    def action_cycle(self) -> None:
        members = sorted(self._cycles)
        if not members:
            self.notify("No cycles in this view")
            return
        later = [member for member in members if self.selected is None or member > self.selected]
        self.selected = (later or members)[0]
        self._redraw()

    def on_graph_view_clicked(self, message: GraphView.Clicked) -> None:
        message.stop()
        if message.node == self.selected:
            self.action_deeper()
        else:
            self.selected = message.node
            self._redraw()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return self._explain is not None if action == "about" else True

    def action_about(self) -> None:
        if self._explain is not None and self.selected is not None:
            self._explain(self.selected, tuple(self._paths()))

    def action_close(self) -> None:
        self.dismiss(None)
