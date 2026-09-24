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


from pathlib import Path

from textual.app import App
from textual.widgets import Static

from spyc.deps.facts import ClassDef, FileFacts, Import
from spyc.deps.graph import CLASS, FILE, UNIT, DependencyGraph, Node
from spyc.location import Location
from spyc.screens.graph import GraphScreen
from spyc.screens.picker import Picker
from spyc.widgets.graph_view import GraphView
from waiting import until


def facts(unit, classes, imports=(), used=()):
    return FileFacts(unit, tuple(ClassDef(name, 7) for name in classes), tuple(imports), frozenset(used))


FILES = {
    "src/order/Service.java": facts("com.acme.order", ["Service"], [Import("com.acme.model.Order"), Import("java.util.List")],
                                    ["Repo"]),
    "src/order/Repo.java": facts("com.acme.order", ["Repo"], [Import("com.acme.billing.Invoice")]),
    "src/model/Order.java": facts("com.acme.model", ["Order"]),
    "src/model/Money.java": facts("com.acme.model", ["Money"]),
    "src/billing/Invoice.java": facts("com.acme.billing", ["Invoice"], [Import("com.acme.order.Service")]),
    "src/web/Api.java": facts("com.acme.web", ["Api"], [Import("com.acme.order.Service")]),
}
GRAPH = DependencyGraph(FILES)
ORDER, MODEL, BILLING, WEB = (Node(UNIT, name) for name in ("com.acme.order", "com.acme.model", "com.acme.billing", "com.acme.web"))


class GraphApp(App):
    def __init__(self, graph, path=None, progress=lambda: ""):
        super().__init__()
        self.graph, self.path, self.progress, self.result = graph, path, progress, "unset"

    async def on_mount(self):
        await self.push_screen(GraphScreen(Path("."), self.graph, self.progress, self.path), self.done)

    def done(self, result):
        self.result = result


def screen_text(app):
    return "\n".join(line.plain for line in app.screen.query_one(GraphView).drawing.lines)


def header(app):
    return app.screen.query_one("#graph-header", Static).render().plain


async def test_it_opens_on_the_package_of_the_given_file_and_shows_its_neighbours():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.screen.centre == ORDER
        assert header(app).startswith("package com.acme.order · 2 out · 2 in")
        text = screen_text(app)
        assert "com.acme.model" in text and "com.acme.billing" in text and "com.acme.web" in text


async def test_without_a_file_it_opens_on_the_most_connected_package():
    app = GraphApp(GRAPH)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert app.screen.centre == ORDER


async def test_enter_centres_the_selected_neighbour_and_backspace_goes_back():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("down", "enter")
        assert app.screen.centre in {MODEL, BILLING}
        first = app.screen.centre
        await pilot.press("backspace")
        assert app.screen.centre == ORDER
        await pilot.press("backspace")
        assert app.screen.centre == ORDER and first != ORDER


async def test_left_and_right_choose_the_column_and_up_and_down_the_node():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("left", "down", "enter")
        assert app.screen.centre in {WEB, BILLING}
        await pilot.press("backspace", "right", "enter")
        assert app.screen.centre in {MODEL, BILLING}


async def test_the_bracket_keys_go_down_to_the_most_connected_file_and_class_and_up_again():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("right_square_bracket")
        assert app.screen.centre.level == FILE and app.screen.centre.key.startswith("src/order/")
        await pilot.press("right_square_bracket")
        assert app.screen.centre.level == CLASS
        await pilot.press("left_square_bracket", "left_square_bracket")
        assert app.screen.centre == ORDER


async def test_at_the_top_and_at_the_bottom_it_says_so(monkeypatch):
    notes = []
    monkeypatch.setattr(GraphScreen, "notify", lambda self, message, **options: notes.append(message))
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("left_square_bracket", "right_square_bracket", "right_square_bracket", "right_square_bracket")
        assert notes == ["Already at the top", "Nothing below this"]


async def test_c_walks_the_nodes_that_are_in_a_cycle_and_says_when_there_are_none(monkeypatch):
    notes = []
    monkeypatch.setattr(GraphScreen, "notify", lambda self, message, **options: notes.append(message))
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("c")
        assert app.screen.centre == BILLING
        await pilot.press("c")
        assert app.screen.centre == ORDER
    app = GraphApp(DependencyGraph({"A.java": facts("a", ["A"])}))
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("c")
        assert notes == ["No cycles at this level"]


async def test_o_gives_the_file_and_the_line_of_a_class_and_a_picker_of_the_files_of_a_package():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("o")
        await until(pilot, lambda: isinstance(app.screen, Picker))
        await pilot.press("escape")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        await pilot.press("right_square_bracket", "right_square_bracket", "o")
        await pilot.pause()
    assert isinstance(app.result, Location) and app.result.path.startswith("src/order/") and app.result.line == 7


async def test_escape_closes_the_screen_without_a_location():
    app = GraphApp(GRAPH)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.result is None


async def test_slash_picks_any_node_of_the_level_by_name():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await until(pilot, lambda: isinstance(app.screen, Picker))
        await pilot.press(*"billing")
        await pilot.pause(0.3)
        await pilot.press("enter")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        assert app.screen.centre == BILLING


async def test_a_click_on_a_neighbour_centres_it():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        view = app.screen.query_one(GraphView)
        place = next(place for place in view.drawing.places if place.side == "in")
        await pilot.click(GraphView, offset=(place.start + 1, place.row))
        await pilot.pause()
        assert app.screen.centre in {WEB, BILLING}


async def test_a_narrow_terminal_stacks_the_columns():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        assert screen_text(app).splitlines()[0].startswith("used by (")


async def test_before_the_graph_exists_the_progress_is_shown_and_the_graph_fills_in_when_it_arrives():
    state = {"progress": "indexing 3/9"}
    app = GraphApp(None, "src/order/Repo.java", lambda: state["progress"])
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert "Reading imports (indexing 3/9)" in screen_text(app)
        app.screen.set_graph(GRAPH)
        await pilot.pause()
        assert app.screen.centre == ORDER and "com.acme.model" in screen_text(app)


async def test_a_project_without_java_or_kotlin_says_so():
    app = GraphApp(DependencyGraph({}))
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert "No dependencies found: no file is in a supported language" in screen_text(app)


async def test_a_new_graph_keeps_the_centre_if_it_still_exists_and_starts_over_if_it_does_not():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("down", "enter")
        moved = app.screen.centre
        app.screen.set_graph(DependencyGraph(FILES))
        assert app.screen.centre == moved
        app.screen.set_graph(DependencyGraph({"A.java": facts("a", ["A"])}))
        assert app.screen.centre == Node(UNIT, "a")


async def test_names_with_control_characters_are_shown_as_symbols():
    graph = DependencyGraph({"a/A.java": facts("p\x1b[2J", ["A"], [Import("q.B")]), "b/B.java": facts("q", ["B"])})
    app = GraphApp(graph)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        assert "\x1b" not in screen_text(app) and "\x1b" not in header(app)
