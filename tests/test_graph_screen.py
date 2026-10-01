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

from spyc.core.location import Location
from spyc.deps.facts import ClassDef, FileFacts, Import
from spyc.deps.graph import DependencyGraph
from spyc.deps.picker import NodeSource
from spyc.deps.scopes import PACKAGE, Member
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
ACME = Member(PACKAGE, ("com", "acme"))
ORDER, MODEL, BILLING, WEB = (Member(PACKAGE, ("com", "acme", name)) for name in ("order", "model", "billing", "web"))
SIZE = (120, 40)


class GraphApp(App):
    def __init__(self, graph, path=None, progress=lambda: ""):
        super().__init__()
        self.graph, self.path, self.progress, self.result = graph, path, progress, "unset"

    async def on_mount(self):
        await self.push_screen(GraphScreen(Path("."), self.graph, self.progress, self.path), self.done)

    def done(self, result):
        self.result = result


def screen_text(app):
    return "\n".join(line.plain for line in app.screen.query_one(GraphView).lines)


def header(app):
    return app.screen.query_one("#graph-header", Static).render().plain


async def test_it_opens_on_the_scope_that_shows_the_package_of_the_given_file():
    app = GraphApp(GRAPH, "src/order/Repo.java")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert app.screen.scope == ACME and app.screen.selected == ORDER
        assert header(app).startswith("package com.acme.order · 2 out · 2 in")
        text = screen_text(app)
        assert "com.acme" in text.splitlines()[0] and all(name in text for name in ("model", "billing", "web"))


async def test_without_a_file_it_opens_on_the_most_connected_package():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert app.screen.scope == ACME and app.screen.selected == ORDER
        assert header(app) == "package com.acme.order · 2 out · 2 in · 1 external (java.util) · ⟲ cycle with 1"


async def test_enter_drills_into_the_selected_box_and_backspace_goes_up_to_the_box_it_came_from():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        assert app.screen.scope == ORDER and "Service.java" in screen_text(app) and "Repo.java" in screen_text(app)
        assert app.screen.selected.kind == "file"
        await pilot.press("backspace")
        assert app.screen.scope == ACME and app.screen.selected == ORDER


async def test_the_bracket_keys_go_down_and_up_and_the_ends_say_so(monkeypatch):
    notes = []
    monkeypatch.setattr(GraphScreen, "notify", lambda self, message, **options: notes.append(message))
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("left_square_bracket")
        await pilot.press("right_square_bracket")
        assert app.screen.scope == ORDER
        await pilot.press("right_square_bracket")
        await pilot.press("left_square_bracket")
        assert app.screen.scope == ACME
        assert notes == ["Already at the top", "A file has nothing below it: o opens it"]


async def test_the_arrow_keys_move_between_the_boxes_by_where_they_are():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("up")
        assert app.screen.selected == WEB
        await pilot.press("down", "down")
        assert app.screen.selected == MODEL
        await pilot.press("up", "left")
        side = app.screen.selected
        await pilot.press("right", "right")
        assert BILLING in {side, app.screen.selected}


async def test_tab_steps_through_the_boxes_in_reading_order():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        seen = []
        for _ in range(4):
            await pilot.press("tab")
            seen.append(app.screen.selected)
        assert set(seen) == {ORDER, MODEL, BILLING, WEB} and seen[-1] == ORDER
        await pilot.press("shift+tab")
        assert app.screen.selected != ORDER


async def test_c_walks_the_boxes_that_are_in_a_cycle_and_says_when_there_are_none(monkeypatch):
    notes = []
    monkeypatch.setattr(GraphScreen, "notify", lambda self, message, **options: notes.append(message))
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("c")
        assert app.screen.selected == BILLING
        await pilot.press("c")
        assert app.screen.selected == ORDER
    app = GraphApp(DependencyGraph({"A.java": facts("a", ["A"])}))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("c")
        assert notes == ["No cycles in this view"]


async def test_o_opens_the_file_and_gives_a_picker_of_the_files_of_a_package():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("o")
        await until(pilot, lambda: isinstance(app.screen, Picker))
        await pilot.press("escape")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        await pilot.press("enter", "o")
        await pilot.pause()
    assert app.result == Location("src/order/Repo.java")


async def test_escape_closes_the_screen_without_a_location():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.result is None


async def test_slash_finds_any_package_or_file_by_name_and_shows_it_in_its_scope():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await until(pilot, lambda: isinstance(app.screen, Picker))
        await pilot.press(*"acme.billing")
        await pilot.pause(0.3)
        await pilot.press("enter")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        assert app.screen.scope == ACME and app.screen.selected == BILLING
        await pilot.press("slash")
        await until(pilot, lambda: isinstance(app.screen, Picker))
        await pilot.press(*"Money")
        await pilot.pause(0.3)
        await pilot.press("enter")
        await until(pilot, lambda: isinstance(app.screen, GraphScreen))
        assert app.screen.scope == MODEL and app.screen.selected.key == "src/model/Money.java"


def box_of(app, member):
    return next(box for box in app.screen.query_one(GraphView).boxes if box.node == member)


async def test_a_click_selects_a_box_and_a_second_click_drills_into_it():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        box = box_of(app, MODEL)
        await pilot.click(GraphView, offset=(box.x + 1, box.y + 1))
        await pilot.pause()
        assert app.screen.selected == MODEL and app.screen.scope == ACME
        await pilot.click(GraphView, offset=(box.x + 1, box.y + 1))
        await pilot.pause()
        assert app.screen.scope == MODEL


async def test_before_the_graph_exists_the_progress_is_shown_and_the_graph_fills_in_when_it_arrives():
    state = {"progress": "indexing 3/9"}
    app = GraphApp(None, "src/order/Repo.java", lambda: state["progress"])
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert "Reading imports (indexing 3/9)" in screen_text(app)
        app.screen.set_graph(GRAPH)
        await pilot.pause()
        assert app.screen.selected == ORDER and "model" in screen_text(app)


async def test_a_project_without_a_supported_language_says_so():
    app = GraphApp(DependencyGraph({}))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert "No dependencies found: no file is in a supported language" in screen_text(app)


async def test_a_new_graph_keeps_the_scope_and_selection_if_they_still_exist_and_starts_over_if_not():
    app = GraphApp(GRAPH)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("up")
        app.screen.set_graph(DependencyGraph(FILES))
        assert app.screen.scope == ACME and app.screen.selected == WEB
        app.screen.set_graph(DependencyGraph({"A.java": facts("a", ["A"])}))
        assert app.screen.selected is not None and app.screen.scope != ACME


async def test_names_with_control_characters_are_shown_as_symbols():
    graph = DependencyGraph({"a/A.java": facts("p\x1b[2J", ["A"], [Import("q.B")]), "b/B.java": facts("q", ["B"])})
    app = GraphApp(graph)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert "\x1b" not in screen_text(app) and "\x1b" not in header(app)


def hub_graph(dependents=60):
    files = {"hub/Hub.java": facts("hub", ["Hub"])}
    files.update({f"u{index:02}/U.java": facts(f"u{index:02}", ["U"], [Import("hub.Hub")]) for index in range(dependents)})
    return DependencyGraph(files)


async def test_a_scope_of_many_boxes_scrolls_to_keep_the_selection_in_view_and_says_it_is_dense():
    app = GraphApp(hub_graph(), "hub/Hub.java")
    async with app.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        assert "many boxes" in header(app)
        await pilot.press(*["tab"] * 45)
        view = app.screen.query_one(GraphView)
        box = box_of(app, app.screen.selected)
        region = view.scrollable_content_region
        assert view.scroll_offset.x <= box.x and box.x + box.width <= view.scroll_offset.x + region.width
        assert view.scroll_offset.y <= box.y and box.y + box.height <= view.scroll_offset.y + region.height


async def test_while_the_graph_does_not_exist_the_screen_never_claims_that_nothing_was_found():
    for progress in ("", "indexing 3/9"):
        app = GraphApp(None, "src/order/Repo.java", lambda progress=progress: progress)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            text = screen_text(app)
            assert "Reading imports" in text and "No dependencies found" not in text


async def test_a_failure_is_shown_instead_of_waiting_for_ever_and_a_graph_that_arrives_later_replaces_it():
    app = GraphApp(None, "src/order/Repo.java")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.screen.set_failure("Could not index the project: boom")
        await pilot.pause()
        assert "Could not index the project: boom" in screen_text(app) and app.screen._timer is None
        app.screen.set_graph(GRAPH)
        await pilot.pause()
        assert "boom" not in screen_text(app) and app.screen.selected == ORDER


def test_the_node_picker_finds_packages_directories_and_files():
    source = NodeSource(GRAPH)
    assert source.placeholder == "Find a package, directory or file by name"
    assert [item.key for item in source.search("acme.billing")] == ["unit:com.acme.billing"]
    assert source.search("Money")[0].key == "file:src/model/Money.java"
